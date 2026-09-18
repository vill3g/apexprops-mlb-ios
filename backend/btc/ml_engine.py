from backend.btc.ml_ensemble import GodTierEnsemble
import json
import math
import os
import threading
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.isotonic import IsotonicRegression

# Empirically-optimal window constraints (Task 4)
OPTIMAL_TRAINING_WINDOW_BARS = 20000  # from walk-forward backtest, see backend/data/backtest_report.json
MAX_LIVE_TRAINING_TRADES = 4000       # bounds live trade history window to prevent stale regimes

class XGBoostModel:
    def __init__(self):
        self.reg_c = 0.5
        self.class_weight = "balanced"
        self.xgb_estimators = 300
        self.xgb_max_depth = 5
        self.xgb_learning_rate = 0.1
        self.calibrator = None
        self._build_pipeline()

    def _build_pipeline(self):
        # Convert RegC (higher C = less regularization) to XGBoost's alpha/lambda (higher = more).
        # We'll use a simple heuristic: alpha = 1.0 / (self.reg_c + 0.1)
        alpha_val = 1.0 / (self.reg_c + 0.1)
        
        self.model = make_pipeline(
            StandardScaler(),
            XGBClassifier(
                n_estimators=self.xgb_estimators,
                max_depth=self.xgb_max_depth,
                learning_rate=self.xgb_learning_rate,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=alpha_val,  # L1 regularization
                random_state=42,
                eval_metric='logloss'
            )
        )
        self.is_trained = False

    def update_params(self, class_weight: str, reg_c: float, estimators: int = 300, max_depth: int = 5, lr: float = 0.1):
        self.class_weight = class_weight
        self.reg_c = reg_c
        self.xgb_estimators = estimators
        self.xgb_max_depth = max_depth
        self.xgb_learning_rate = lr
        self._build_pipeline()

    def fit(self, X, y, sample_weight=None):
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        
        if len(np.unique(y)) < 2:
            logger.warning("[MLEngine] Only one class present in labels. Model cannot learn.")
            self.is_trained = False
            return
            
        # Calculate scale_pos_weight if balanced
        if self.class_weight == "balanced":
            num_negative = np.sum(y == 0)
            num_positive = np.sum(y == 1)
            scale_pos = num_negative / max(1, num_positive)
            self.model.named_steps['xgbclassifier'].set_params(scale_pos_weight=scale_pos)
        else:
            self.model.named_steps['xgbclassifier'].set_params(scale_pos_weight=1.0)
            
        fit_params = {}
        if sample_weight is not None:
            fit_params['xgbclassifier__sample_weight'] = sample_weight

        self.model.fit(X, y, **fit_params)
        self.is_trained = True

    def fit_calibration(self, X_holdout, y_holdout):
        """Fit an isotonic regression mapping raw predict_proba() -> calibrated probability,
        using a held-out slice not used for the main model fit. Call after fit().

        Isotonic regression on small sample sizes overfits and can collapse
        probabilities into hard 0.0/1.0 step functions. Gate on a minimum
        holdout size (empirically ~300+) before trusting it; below that,
        stay on XGBoost's raw probabilities rather than risk a degenerate
        calibrator.
        """
        MIN_CALIBRATION_SAMPLES = 300
        self.calibrator = None

        if X_holdout is None or y_holdout is None:
            return
        X_holdout = np.asarray(X_holdout)
        y_holdout = np.asarray(y_holdout)

        if len(X_holdout) < MIN_CALIBRATION_SAMPLES:
            logger.debug(
                f"[MLEngine] Holdout too small for calibration "
                f"({len(X_holdout)} < {MIN_CALIBRATION_SAMPLES}); using raw probabilities."
            )
            return
        if len(np.unique(y_holdout)) < 2:
            logger.debug("[MLEngine] Holdout has only one class; skipping calibration.")
            return

        try:
            raw_probs = self.predict_proba(X_holdout)
            calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            calibrator.fit(raw_probs, y_holdout)
            self.calibrator = calibrator
            logger.info(f"[MLEngine] Fitted isotonic calibration on {len(X_holdout)} holdout samples.")
        except Exception as e:
            logger.warning(f"[MLEngine] Calibration fit failed, using raw probabilities: {e}")
            self.calibrator = None

    def predict_proba(self, X):
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        if not self.is_trained:
            return np.array([0.5] * X.shape[0])

        try:
            # XGBClassifier predict_proba returns probabilities for each class
            # model.classes_ contains the unique labels seen during training (e.g., [0, 1])
            # We want the probability for class 1 (WIN)
            classifier = self.model.named_steps['xgbclassifier']
            class_1_index = list(classifier.classes_).index(1)
            probs = self.model.predict_proba(X)
            return probs[:, class_1_index]
        except (ValueError, KeyError, AttributeError):
            # Fallback if class 1 wasn't in the training data
            return np.array([0.0] * X.shape[0])

    def predict_proba_calibrated(self, X):
        raw = self.predict_proba(X)
        if self.calibrator is None:
            return raw
        try:
            # IsotonicRegression.predict() maps raw score -> calibrated score
            # directly (it is NOT a classifier: no .predict_proba()/.classes_).
            calibrated = self.calibrator.predict(raw)
            return np.clip(calibrated, 0.01, 0.99)
        except Exception as e:
            logger.warning(f"[MLEngine] Calibrated prediction failed: {e}")
            return raw


# Note: Trade records logged before the rename from "score" to "heuristic_score"
# have "score" in their snapshots. _extract_features_and_labels() safely defaults
# missing keys to 0.0 via raw.get(k, 0.0) without crashing.
FEATURE_KEYS = [
    "rsi", "bb_upper", "bb_lower", "ema_9", "ema_21", "ema_50",
    "atr", "price_vs_vwap", "cvd_value", "delta_to_target", "heuristic_score",
    "news_sentiment_score", "is_weekend", "hour_of_day", "volume_15m_ratio",
    # Low-volume / derivatives signals (added 2026-09-12)
    "orderbook_imbalance", "funding_rate", "open_interest",
    "fng_value", "high_24h", "low_24h", "volume_24h",
    # Microstructure & Stationary Range Features (added 2026-09-13)
    "upper_wick_ratio", "lower_wick_ratio", "body_to_range", "range_24h_pos",
    # Time-to-expiry decay feature (added Task 5)
    "minutes_remaining",
    # Kalshi market-implied probability and book imbalance (added Task 6)
    "kalshi_yes_prob", "kalshi_book_imbalance",
    # Momentum ROC features
    "roc_15m", "roc_1h", "roc_4h",
    # CVD normalized divergence
    "cvd_divergence",
    # Volatility regime percentile (added Task 5: 24h rolling ATR percentile)
    "vol_regime_percentile",
    "macd_hist_momentum", "mtf_rsi_4h", "cvd_acceleration",
]

NEUTRAL_FEATURE_DEFAULTS = {
    "rsi": 50.0,
    "delta_to_target": 0.0,
    "heuristic_score": 0.0,
    "news_sentiment_score": 0.0,
    "fng_value": 50.0,
    "orderbook_imbalance": 0.0,
    "funding_rate": 0.0,
    "open_interest": 0.0,
    "is_weekend": 0.0,
    "hour_of_day": 12.0,
    "volume_15m_ratio": 1.0,
    "upper_wick_ratio": 0.25,
    "lower_wick_ratio": 0.25,
    "body_to_range": 0.5,
    "range_24h_pos": 0.5,
    "minutes_remaining": 14.5,
    "kalshi_yes_prob": 50.0,
    "kalshi_book_imbalance": 0.0,
    "roc_15m": 0.0,
    "roc_1h": 0.0,
    "roc_4h": 0.0,
    "cvd_divergence": 0.0,
    "vol_regime_percentile": 0.5,
    "macd_hist_momentum": 0.0,
    "mtf_rsi_4h": 50.0,
    "cvd_acceleration": 0.0,
}


def build_feature_row(df_ind, i: int) -> dict:
    """
    Extracts the per-row feature dictionary from an indicator-enriched DataFrame
    at candle index i. Shared between self_train_on_historical_market and walkforward backtest.
    Index i represents the interval being predicted; the LABEL is derived from
    df_ind.iloc[i], but every FEATURE must be derived only from bars strictly
    before i (df_ind.iloc[i-1] and earlier) to match what build_live_ml_features()
    can actually see at decision time. Never read df_ind.iloc[i]'s own OHLC into
    a feature — that candle is the outcome being predicted.
    """
    p = df_ind.iloc[i - 1]  # previous 15m candle (fully closed) — the only candle
                             # features are allowed to read shape/price data from
    c = df_ind.iloc[i]      # interval candle — used ONLY to build target_price
                             # (its open, known at interval start) and the label
                             # elsewhere; never for shape/close-derived features.

    # Target price aligns to candle open (matching Kalshi strike convention).
    # c["open"] is known at the start of the interval, before the interval's
    # own close/high/low exist — this one read of `c` is fine.
    target_price = float(c.get("open", p["close"]))

    # Candle-shape features (wick ratios, body-to-range, 24h-range position)
    # must describe the LAST KNOWN candle (p), not the interval being
    # predicted (c) — otherwise they leak the outcome. This mirrors exactly
    # what build_live_ml_features() computes at real prediction time.
    p_open = float(p.get("open", target_price))
    p_close = float(p["close"])
    p_high = float(p.get("high", max(p_open, p_close)))
    p_low = float(p.get("low", min(p_open, p_close)))
    rng = max(1e-5, p_high - p_low)

    upper_wick = (p_high - max(p_open, p_close)) / rng
    lower_wick = (min(p_open, p_close) - p_low) / rng
    body_range = abs(p_close - p_open) / rng

    # 24h window excludes bar i already (slice stops at i, exclusive) — keep
    # that, but position the LAST KNOWN close (p_close) within that window,
    # not the future close.
    high_24h_val = float(df_ind["high"].iloc[max(0, i - 96):i].max()) if "high" in df_ind.columns and len(df_ind) > 0 else target_price
    low_24h_val = float(df_ind["low"].iloc[max(0, i - 96):i].min()) if "low" in df_ind.columns and len(df_ind) > 0 else target_price
    vol_24h_val = float(df_ind["volume"].iloc[max(0, i - 96):i].sum()) if "volume" in df_ind.columns and len(df_ind) > 0 else 0.0
    range_24h_pos = (p_close - low_24h_val) / max(1.0, high_24h_val - low_24h_val)
    range_24h_pos = max(0.0, min(1.0, range_24h_pos))

    hist_delta = ((p_close - target_price) / max(target_price, 1e-9)) * 100.0

    rsi_val = float(p.get("rsi", 50))
    ema9_val = float(p.get("ema_9", target_price))
    ema21_val = float(p.get("ema_21", target_price))
    hist_score = (rsi_val - 50.0) * 0.8 + (10.0 if ema9_val >= ema21_val else -10.0)
    hist_score = max(-50.0, min(50.0, hist_score))

    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        c_time = int(p.get("time", 0))
        if c_time > 0:
            dt_ny = datetime.fromtimestamp(c_time, ZoneInfo("America/New_York"))
            is_wknd = 1.0 if dt_ny.weekday() >= 5 else 0.0
            hr_day = float(dt_ny.hour)
        else:
            is_wknd, hr_day = 0.0, 12.0
    except Exception:
        is_wknd, hr_day = 0.0, 12.0

    try:
        vol_slice = df_ind["volume"].iloc[max(0, i-288):i]
        avg_vol_3d = float(vol_slice.mean()) if len(vol_slice) > 0 else 1.0
        curr_vol = float(p.get("volume", 0.0))
        vol_15m_ratio = curr_vol / max(avg_vol_3d, 1e-9)
    except Exception:
        vol_15m_ratio = 1.0

    try:
        atr_slice = df_ind["atr"].iloc[max(0, i - 96):i] if "atr" in df_ind.columns and i > 0 else pd.Series([100.0])
        curr_atr = float(p.get("atr", 100.0))
        vol_regime = float((atr_slice <= curr_atr).mean()) if len(atr_slice) > 0 else 0.5
    except Exception:
        vol_regime = 0.5

    raw_feat = {
        "rsi": rsi_val,
        "bb_upper": float(p.get("bb_upper", target_price)),
        "bb_lower": float(p.get("bb_lower", target_price)),
        "ema_9": ema9_val,
        "ema_21": ema21_val,
        "ema_50": float(p.get("ema_50", target_price)),
        "atr": float(p.get("atr", 100)),
        "price_vs_vwap": float(target_price - p.get("vwap", target_price)),
        "cvd_value": float(p.get("cvd", 0.0)),
        "delta_to_target": float(hist_delta),
        "heuristic_score": float(hist_score),
        "news_sentiment_score": float(p.get("news_sentiment_score", 0.0)),
        "orderbook_imbalance": float(p.get("orderbook_imbalance", 0.0)),
        "funding_rate": float(p.get("funding_rate", 0.0)),
        "open_interest": float(p.get("open_interest", 0.0)),
        "fng_value": float(p.get("fng_value", 50.0)),
        "high_24h": high_24h_val,
        "low_24h": low_24h_val,
        "volume_24h": vol_24h_val,
        "upper_wick_ratio": float(upper_wick),
        "lower_wick_ratio": float(lower_wick),
        "body_to_range": float(body_range),
        "range_24h_pos": float(range_24h_pos),
        "is_weekend": float(is_wknd),
        "hour_of_day": float(hr_day),
        "volume_15m_ratio": float(vol_15m_ratio),
        # Synthetic entries approximate rollover-time entry (start of 15m interval)
        "minutes_remaining": 14.5,
        # Neutral defaults for historical synthetic rows where real Kalshi orderbook did not exist
        "kalshi_yes_prob": 50.0,
        "kalshi_book_imbalance": 0.0,
        "roc_15m": float(p.get("roc_15m", 0.0)),
        "roc_1h": float(p.get("roc_1h", 0.0)),
        "roc_4h": float(p.get("roc_4h", 0.0)),
        "cvd_divergence": float(p.get("cvd", 0.0)) / (float(p.get("atr", 1.0)) + 1e-5),
        "vol_regime_percentile": float(vol_regime),
    }
    return raw_feat


def build_live_ml_features(
    df_ind: pd.DataFrame,
    c: pd.Series = None,
    p: pd.Series = None,
    target: float = None,
    kalshi_m: dict = None,
    futures_data: dict = None,
    fng_data: dict = None,
    cb_ob: dict = None,
    minutes_remaining: float = 14.5,
    heuristic_score: float = None,
) -> dict:
    """
    Constructs the 26-feature input vector for MLEngine live predictions.
    Unifies feature construction between analyze_btc() and evaluate_next_15m_contract().
    Ensures all keys in FEATURE_KEYS are present with robust fallbacks.
    """
    if c is None:
        c = df_ind.iloc[-1] if len(df_ind) > 0 else pd.Series()
    if p is None:
        p = df_ind.iloc[-2] if len(df_ind) >= 2 else c

    # target_price is defined by the interval open (c["open"]) or explicit override
    target_price = float(target) if target is not None else float(c.get("open", c.get("close", 60000.0)))

    # All features MUST be extracted from the PREVIOUS fully closed candle (p)
    # to perfectly match the training distribution built in build_feature_row.
    p_close = float(p.get("close", target_price) or target_price)
    p_open = float(p.get("open", p_close) or p_close)
    p_high = float(p.get("high", max(p_open, p_close)) or max(p_open, p_close))
    p_low = float(p.get("low", min(p_open, p_close)) or min(p_open, p_close))

    rng = max(1e-5, p_high - p_low)

    upper_wick = (p_high - max(p_open, p_close)) / rng
    lower_wick = (min(p_open, p_close) - p_low) / rng
    body_range = abs(p_close - p_open) / rng

    high_24h_val = float(df_ind["high"].tail(96).max()) if len(df_ind) > 0 and "high" in df_ind.columns else p_close
    low_24h_val = float(df_ind["low"].tail(96).min()) if len(df_ind) > 0 and "low" in df_ind.columns else p_close
    vol_24h_val = float(df_ind["volume"].tail(96).sum()) if len(df_ind) > 0 and "volume" in df_ind.columns else 0.0
    range_24h_pos = (p_close - low_24h_val) / max(1.0, high_24h_val - low_24h_val)
    range_24h_pos = max(0.0, min(1.0, range_24h_pos))

    # delta_to_target using the previous fully-closed candle (which equals ~0.0 during standard Kalshi rollovers)
    delta_to_target = float(((p_close - target_price) / max(target_price, 1e-9)) * 100.0)

    rsi = float(p.get("rsi", 50.0) or 50.0)
    ema_9 = float(p.get("ema_9", p_close) or p_close)
    ema_21 = float(p.get("ema_21", p_close) or p_close)
    ema_50 = float(p.get("ema_50", p_close) or p_close)
    bb_upper = float(p.get("bb_upper", p_high) or p_high)
    bb_lower = float(p.get("bb_lower", p_low) or p_low)
    atr = float(p.get("atr", 100.0) or 100.0)

    if heuristic_score is not None:
        h_score = float(heuristic_score)
    else:
        tech_score = (rsi - 50.0) * 0.8 + (10.0 if ema_9 >= ema_21 else -10.0)
        h_score = max(-50.0, min(50.0, tech_score))

    cvd_val = float(p.get("cvd", 0.0))

    vwap_val = p.get("vwap")
    price_vs_vwap = float(p_close - vwap_val) if vwap_val is not None and not pd.isna(vwap_val) else 0.0

    funding_rate = float(futures_data.get("funding_rate", 0.0)) if futures_data else 0.0
    open_interest = float(futures_data.get("open_interest", 0.0)) if futures_data else 0.0
    fng_value = float(fng_data.get("value", 50.0)) if fng_data else 50.0
    cb_imbalance = float(cb_ob.get("imbalance", 0.0)) if cb_ob else 0.0

    kalshi_yes = float(kalshi_m.get("yes_prob", 50.0)) if kalshi_m else 50.0
    kalshi_imb = float(kalshi_m.get("orderbook_imbalance", kalshi_m.get("book_imbalance", 0.0))) if kalshi_m else 0.0

    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        p_time = int(p.get("time", 0))
        if p_time > 0:
            dt_ny = datetime.fromtimestamp(p_time, ZoneInfo("America/New_York"))
            is_wknd = 1.0 if dt_ny.weekday() >= 5 else 0.0
            hr_day = float(dt_ny.hour)
        else:
            now_ny = datetime.now(ZoneInfo("America/New_York"))
            is_wknd = 1.0 if now_ny.weekday() >= 5 else 0.0
            hr_day = float(now_ny.hour)
    except Exception:
        is_wknd, hr_day = 0.0, 12.0

    try:
        vol_slice = df_ind["volume"].tail(288)
        avg_vol_3d = float(vol_slice.mean()) if len(vol_slice) > 0 else 1.0
        curr_vol = float(p.get("volume", 0.0))
        vol_15m_ratio = curr_vol / max(avg_vol_3d, 1e-9)
    except Exception:
        vol_15m_ratio = 1.0

    try:
        atr_slice = df_ind["atr"].tail(96) if "atr" in df_ind.columns and len(df_ind) > 0 else pd.Series([100.0])
        vol_regime = float((atr_slice <= atr).mean()) if len(atr_slice) > 0 else 0.5
    except Exception:
        vol_regime = 0.5

    features = {
        "rsi": rsi,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "ema_9": ema_9,
        "ema_21": ema_21,
        "ema_50": ema_50,
        "atr": atr,
        "price_vs_vwap": price_vs_vwap,
        "cvd_value": cvd_val,
        "delta_to_target": delta_to_target,
        "heuristic_score": h_score,
        "news_sentiment_score": float(p.get("news_sentiment_score", 0.0) or 0.0),
        "orderbook_imbalance": cb_imbalance,
        "funding_rate": funding_rate,
        "open_interest": open_interest,
        "fng_value": fng_value,
        "high_24h": high_24h_val,
        "low_24h": low_24h_val,
        "volume_24h": vol_24h_val,
        "upper_wick_ratio": float(upper_wick),
        "lower_wick_ratio": float(lower_wick),
        "body_to_range": float(body_range),
        "range_24h_pos": float(range_24h_pos),
        "is_weekend": float(is_wknd),
        "hour_of_day": float(hr_day),
        "volume_15m_ratio": float(vol_15m_ratio),
        "minutes_remaining": float(minutes_remaining),
        "kalshi_yes_prob": kalshi_yes,
        "kalshi_book_imbalance": kalshi_imb,
        "roc_15m": float(df_ind["roc_15m"].iloc[-2]) if "roc_15m" in df_ind.columns and len(df_ind) >= 2 else 0.0,
        "roc_1h": float(df_ind["roc_1h"].iloc[-2]) if "roc_1h" in df_ind.columns and len(df_ind) >= 2 else 0.0,
        "roc_4h": float(df_ind["roc_4h"].iloc[-2]) if "roc_4h" in df_ind.columns and len(df_ind) >= 2 else 0.0,
        "cvd_divergence": float(cvd_val / (float(atr) + 1e-5)),
        "vol_regime_percentile": float(vol_regime),
    }
    return features


class MLEngine:
    feature_keys = FEATURE_KEYS

    def __init__(self, data_dir, trading_style="SNIPER", asset="BTC"):
        self.trading_style = trading_style
        self.asset = asset
        asset_suffix = "" if asset == "BTC" else f"_{asset}"
        self.history_file = os.path.join(data_dir, f"trades_history{asset_suffix}.json")
        self.model = GodTierEnsemble()
        self.is_trained = False
        self.last_trained_mtime = 0.0
        self.last_train_sample_count = 0
        self.feature_keys = list(FEATURE_KEYS)
        if self.trading_style == "MOMENTUM_SURFER":
            self.feature_keys.append("minutes_remaining")
        self._lock = threading.Lock()
        self.train_window = 15000 if self.trading_style == "MOMENTUM_SURFER" else 100


    def predict_with_reasoning(self, current_raw_features: dict):
        """
        Returns (probability, reasoning_string) by extracting SHAP/feature contributions
        from the XGBoost tree for this specific prediction.
        """
        prob = self.predict_probability(current_raw_features)
        if not self.is_trained or prob == 0.5:
            return prob, "ML is neutral or untrained."
            
        try:
            # Rebuild the feature vector exactly as in predict_probability
            feature_vec = []
            for k in self.feature_keys:
                default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
                val = current_raw_features.get(k, default_val)
                try:
                    val = float(val) if val is not None else default_val
                    if not math.isfinite(val):
                        val = default_val
                except (TypeError, ValueError):
                    val = default_val
                feature_vec.append(val)
                
            X_pred = np.nan_to_num(np.array([feature_vec]), nan=0.0, posinf=0.0, neginf=0.0)
            
            # Extract standard scaler and xgboost classifier
            try:
                scaler = self.model.scaler
                xgb = self.model.xgb
            except AttributeError:
                scaler = self.model.model.named_steps['standardscaler']
                xgb = self.model.model.named_steps['xgbclassifier']
            
            # Scale the input
            X_scaled = scaler.transform(X_pred)
            
            # Get booster and predict with pred_contribs=True
            import xgboost as xgb_lib
            dmatrix = xgb_lib.DMatrix(X_scaled, feature_names=self.feature_keys)
            contribs = xgb.get_booster().predict(dmatrix, pred_contribs=True)[0]
            
            # The last element is the bias, the rest are feature contributions
            feature_contribs = contribs[:-1]
            
            # Pair with names and sort by absolute magnitude
            contrib_pairs = [(self.feature_keys[i], feature_contribs[i]) for i in range(len(self.feature_keys))]
            contrib_pairs.sort(key=lambda x: abs(x[1]), reverse=True)
            
            # Grab top 3 drivers pushing it towards its prediction
            # If prob > 0.5, we care about positive drivers. If prob < 0.5, negative drivers.
            direction_sign = 1 if prob >= 0.5 else -1
            top_drivers = []
            for name, val in contrib_pairs:
                if (val * direction_sign) > 0:
                    # Clean up the name for readability
                    clean_name = name.replace("_", " ").title()
                    top_drivers.append(clean_name)
                    if len(top_drivers) == 3:
                        break
                        
            if top_drivers:
                return prob, f"ML Reasoning: Prediction driven primarily by {', '.join(top_drivers)}."
            else:
                return prob, "ML Reasoning: Balanced feature contributions."
                
        except Exception as e:
            logger.error(f"[MLEngine] Failed to extract reasoning: {e}")
            return prob, "ML Reasoning unavailable."

    def get_ml_confidence_weight(self, base_weight: float, full_sample_threshold: int = 300) -> float:
        """
        Scale down the ML blend weight when the live model was trained on few samples,
        redistributing the difference to the heuristic weight. Ramps linearly from 0 at
        ~10 samples to full base_weight at full_sample_threshold samples.
        """
        n = getattr(self, "last_train_sample_count", 0)
        if n <= 10:
            return 0.0
        if n >= full_sample_threshold:
            return float(base_weight)
        ramp = (n - 10) / float(full_sample_threshold - 10)
        return round(float(base_weight) * ramp, 4)

    def apply_settings(self, settings: dict):
        with self._lock:
            self.train_window = int(settings.get("trainWindow", 100))
            class_weight = settings.get("classWeight", "balanced")
            reg_c = float(settings.get("regC", 0.5))
            
            # Update the XGBoost parameters
            self.model.update_params(class_weight, reg_c)
            
            logger.info(f"[MLEngine] Applied new settings. Train window: {self.train_window}, Class Weight: {class_weight}, Reg C: {reg_c}")

    def _recency_weights(self, n_samples: int) -> np.ndarray:
        weights = []
        for i in range(n_samples):
            recency = 1.0 + (i / max(1, n_samples - 1))
            weights.append(recency)
        return np.array(weights)

    def _extract_features_and_labels(self, time_filter="all"):
        if not os.path.exists(self.history_file):
            return None, None, None
            
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                trades = json.load(f)
        except Exception as e:
            logger.error(f"[MLEngine] Error loading trades: {e}")
            return None, None, None
            
        X = []
        y = []
        
        for t in trades:
            # We only train on closed/settled trades that have raw_features
            if t.get("status") not in ["SETTLED", "CLOSED"]:
                continue
                
            # Filter to only this asset to prevent mixing feature scales
            ticker = str(t.get("ticker", "")).upper()
            if not ticker.startswith(f"KX{self.asset}") and not ticker.startswith(self.asset):
                continue
                
            # Time filter logic
            if time_filter != "all" and "timestamp" in t:
                try:
                    # Timestamp is like "2026-09-11 02:16:01 AM ET"
                    from datetime import datetime
                    dt = datetime.strptime(t["timestamp"], "%Y-%m-%d %I:%M:%S %p ET")
                    is_night = 0 <= dt.hour < 7
                    if time_filter == "night" and not is_night:
                        continue
                    if time_filter == "day" and is_night:
                        continue
                except Exception as e:
                    logger.warning(f"[ML] Training background worker error: {e}")

            # Finding 5: Label semantics must match self_train_on_historical_market() / _extract_features_and_labels()
            # respectively — both must mean P(close >= target), never P(trade won).
            strike = t.get("strike")
            settle_price = t.get("settle_price")
            side = str(t.get("side", "")).upper().strip()
            res = str(t.get("result", "")).upper().strip()
            direction = str(t.get("direction", "")).upper().strip()
            official_result = str(t.get("official_result", "")).upper().strip()

            label = None
            # 1. Direct official Kalshi outcome: YES = market >= strike (1), NO = market < strike (0)
            if official_result in ["YES", "NO"]:
                label = 1 if official_result == "YES" else 0
            # 2. Kalshi contract settlement dollar/cent value: 1.0/100.0 means YES settled ITM (1), 0.0/0 means NO settled ITM (0)
            elif strike is not None and settle_price is not None:
                try:
                    s_val = float(strike)
                    sp_val = float(settle_price)
                    if sp_val in (1.0, 100.0) or sp_val == 1:
                        label = 1
                    elif sp_val in (0.0, 0) and s_val > 0:
                        label = 0
                    elif s_val > 1000 and sp_val > 1000:
                        label = 1 if sp_val >= s_val else 0
                except (ValueError, TypeError):
                    label = None

            # 3. Trade result fallback: WIN/LOSS relative to trade side/direction
            if label is None:
                is_win = ("WIN" in res) or ("WON" in res)
                is_loss = ("LOSS" in res) or ("LOST" in res)
                if not is_win and not is_loss:
                    continue

                legacy_fallback_count = getattr(self, "_legacy_fallback_count", 0) + 1
                self._legacy_fallback_count = legacy_fallback_count
                if legacy_fallback_count == 1 or legacy_fallback_count % 10 == 0:
                    logger.warning(f"[MLEngine] Legacy fallback direction labeling used for {legacy_fallback_count} trade(s) lacking settle_price/strike.")

                if direction == "ABOVE" or side == "YES":
                    label = 1 if is_win else 0
                elif direction == "BELOW" or side == "NO":
                    label = 0 if is_win else 1
                else:
                    continue
                
            snapshot = t.get("market_snapshot", {})
            raw = snapshot.get("raw_features")
            if not raw:
                # Fallback: if old trades don't have raw_features, skip them
                continue
                
            feature_vec = []
            valid = True
            for k in self.feature_keys:
                default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
                val = raw.get(k, default_val)
                # FIX #5: Use math.isfinite() to catch nan, -nan, inf, -inf, "NaN" etc.
                # str(val)=="nan" only catches some representations; math.isfinite is authoritative.
                try:
                    val = float(val) if val is not None else default_val
                    if not math.isfinite(val):
                        val = default_val
                except (TypeError, ValueError):
                    val = default_val
                feature_vec.append(val)
                
            if valid:
                X.append(feature_vec)
                y.append(label)
                
        # Apply the training window and MAX_LIVE_TRAINING_TRADES cap (Task 4)
        max_trades = min(getattr(self, "train_window", MAX_LIVE_TRAINING_TRADES), MAX_LIVE_TRAINING_TRADES)
        if len(X) > max_trades:
            X = X[-max_trades:]
            y = y[-max_trades:]

        if len(X) < 10:
            # Not enough data to train a reliable model
            return None, None, None
            
        X_arr = np.array(X)
        y_arr = np.array(y)
        
        # AUDIT FIX #5: Removed the 1.8x loss penalty that was corrupting predict_proba() calibration.
        # Recency weighting is kept (recent trades matter more than old ones).
        # Class imbalance is already handled by XGBoost's scale_pos_weight parameter.
        n_samples = len(X_arr)
        weights = self._recency_weights(n_samples)
            
        return X_arr, y_arr, weights
        
    def train(self, force: bool = False, time_filter: str = "all"):
        with self._lock:
            if not os.path.exists(self.history_file):
                return 0
            try:
                mtime = os.path.getmtime(self.history_file)
            except Exception as e:
                logger.debug(f"[MLEngine] Could not read mtime for {self.history_file}: {e}")
                mtime = 0.0
                
            if not force and self.is_trained and mtime <= self.last_trained_mtime:
                return 0  # Already up to date
                
            try:
                res = self._extract_features_and_labels(time_filter=time_filter)
                if res[0] is not None and len(res[0]) >= 10:
                    X, y, weights = res
                    n = len(X)
                    # For small sample sizes (< 80), train on the full set to preserve signal;
                    # calibrate only when sufficient holdout samples exist.
                    split = n if n < 80 else max(0, n - max(20, int(n * 0.2)))
                    X_train, y_train, w_train = X[:split], y[:split], weights[:split]
                    X_cal, y_cal = X[split:], y[split:]

                    if len(X_train) >= 10:
                        logger.info(f"[MLEngine] Training custom ML model on {len(X_train)} historical trades (calibrating on {len(X_cal)}, filter={time_filter})...")
                        self.model.fit(X_train, y_train, sample_weight=w_train)
                        self.is_trained = self.model.is_trained
                        if not self.is_trained:
                            logger.warning(f"[MLEngine] Training failed on {len(X_train)} samples (likely <2 unique classes).")
                            return 0
                        self.last_trained_mtime = mtime
                        self.last_train_sample_count = len(X_train)
                        if len(X_cal) >= 20 and len(np.unique(y_cal)) >= 2:
                            self.model.fit_calibration(np.array(X_cal), np.array(y_cal))
                        else:
                            self.model.calibrator = None
                        logger.info("[MLEngine] Training complete.")
                        return len(X_train)
            except Exception as e:
                logger.error(f"[MLEngine] Training failed: {e}", exc_info=True)
            return 0
            
    def self_train_on_historical_market(self, df_ind, time_filter: str = "all") -> int:
        """
        Self-trains the model on hundreds of historical 15m intervals, removing the dependency 
        on having to wait for 10 live executed trades to be collected.
        """
        # Enforce OPTIMAL_TRAINING_WINDOW_BARS + 50 warmup context (Task 4)
        if len(df_ind) > OPTIMAL_TRAINING_WINDOW_BARS + 50:
            df_ind = df_ind.iloc[-(OPTIMAL_TRAINING_WINDOW_BARS + 50):].reset_index(drop=True)

        X = []
        y = []
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        # df_ind is a pandas DataFrame with indicators. Start at 50 to allow EMAs to warm up.
        for i in range(50, len(df_ind) - 1):
            p = df_ind.iloc[i-1] # previous 15m candle (fully closed)
            c = df_ind.iloc[i]   # interval candle
            
            # Time filter and mapping logic
            dt_obj = None
            ny_dt = None
            
            if "datetime" in c:
                try:
                    dt_val = c["datetime"]
                    if isinstance(dt_val, str):
                        dt_obj = datetime.fromisoformat(dt_val.replace('Z', '+00:00'))
                    else:
                        dt_obj = dt_val
                    ny_dt = dt_obj.astimezone(ZoneInfo("America/New_York"))
                except Exception as e:
                    logger.debug(f"[ML] datetime parse error: {e}")
                    
            if ny_dt is None:
                try:
                    ny_dt = pd.to_datetime(c.get("time", 0), unit="s", utc=True).astimezone(ZoneInfo("America/New_York"))
                except Exception:
                    ny_dt = datetime.now(ZoneInfo("America/New_York"))
            
            is_night = 0 <= ny_dt.hour < 7
            if time_filter == "night" and not is_night:
                continue
            if time_filter == "day" and is_night:
                continue
                    
            raw_feat = build_feature_row(df_ind, i)
            
            if self.trading_style == "MOMENTUM_SURFER":
                # 1m data mapping: Find interval start (minute 00, 15, 30, 45) and interval end (minute 14, 29, 44, 59)
                minute = ny_dt.minute
                interval_start_min = (minute // 15) * 15
                minutes_elapsed = minute - interval_start_min
                minutes_remaining = 15.0 - minutes_elapsed
                
                raw_feat["minutes_remaining"] = minutes_remaining
                
                # Look backwards up to 14 rows to find the interval open price
                target_price = float(c["open"])
                for j in range(0, minutes_elapsed + 1):
                    if i - j >= 0:
                        past_c = df_ind.iloc[i - j]
                        target_price = float(past_c["open"])
                
                # Look forwards up to 14 rows to find the interval close price
                actual_close = float(c["close"])
                mins_to_close = 14 - minutes_elapsed
                if i + mins_to_close < len(df_ind):
                    future_c = df_ind.iloc[i + mins_to_close]
                    actual_close = float(future_c["close"])
                else:
                    continue # Skip if interval hasn't finished yet
                    
                label = 1 if actual_close >= target_price else 0
            else:
                actual_close = float(c["close"])
                target_price = float(c.get("open", p["close"]))
                label = 1 if actual_close >= target_price else 0
            
            feature_vec = []
            valid = True
            for k in self.feature_keys:
                val = raw_feat.get(k, 0.0)
                try:
                    val = float(val) if val is not None else 0.0
                    if not math.isfinite(val):
                        val = 0.0
                except (TypeError, ValueError):
                    val = 0.0
                feature_vec.append(val)
                
            if valid:
                X.append(feature_vec)
                y.append(label)
                
        if len(X) > self.train_window:
            X = X[-self.train_window:]
            y = y[-self.train_window:]
            
        if len(X) >= 10:
            with self._lock:
                n = len(X)
                split = max(0, n - max(20, int(n * 0.2)))
                X_train, y_train = X[:split], y[:split]
                X_cal, y_cal = X[split:], y[split:]

                weights = self._recency_weights(len(X_train))
                self.model.fit(np.array(X_train), np.array(y_train), sample_weight=weights)
                self.is_trained = self.model.is_trained
                if not self.is_trained:
                    logger.warning(f"[MLEngine] Self-training failed on {len(X_train)} samples (likely <2 unique classes).")
                    return 0
                self.last_train_sample_count = len(X_train)

                if len(X_cal) >= 20:
                    self.model.fit_calibration(np.array(X_cal), np.array(y_cal))

                logger.info(f"[MLEngine] Self-trained ML model on {len(X_train)} historical 15m market intervals (calibrated on {len(X_cal)}).")
                return len(X_train)
        return 0
        
    def predict_probability(self, current_raw_features: dict) -> float:
        """
        Returns the ML model's probability of a WIN given the current features.
        Returns 0.5 (50%) if the model isn't trained yet.
        """
        if not self.is_trained:
            self.train()
            
        if not self.is_trained:
            return 0.5
            
        feature_vec = []
        for k in self.feature_keys:
            default_val = NEUTRAL_FEATURE_DEFAULTS.get(k, 0.0)
            val = current_raw_features.get(k, default_val)
            # FIX #5: sanitize every value before inference — matches training extraction
            try:
                val = float(val) if val is not None else default_val
                if not math.isfinite(val):
                    val = default_val
            except (TypeError, ValueError):
                val = default_val
            feature_vec.append(val)

        # Extra safety net: np.nan_to_num catches any numpy scalars that slipped through
        X_pred = np.nan_to_num(np.array([feature_vec]), nan=0.0, posinf=0.0, neginf=0.0)
        prob = self.model.predict_proba_calibrated(X_pred)[0]
        return float(prob)




# =====================================================================
# SINGLETON FACTORY
# =====================================================================
_ml_engine_instances = {}
_ml_engine_lock = threading.Lock()

def get_ml_engine(data_dir: str = None, trading_style: str = "SNIPER", asset: str = "BTC"):
    key = f"{asset}_{trading_style}"
    if key not in _ml_engine_instances:
        with _ml_engine_lock:
            if key not in _ml_engine_instances:
                if data_dir is None:
                    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                from backend.btc.dual_ml_engine import DualMLEngine
                engine = DualMLEngine(data_dir, trading_style, asset)
                engine.train()
                _ml_engine_instances[key] = engine
    return _ml_engine_instances[key]
