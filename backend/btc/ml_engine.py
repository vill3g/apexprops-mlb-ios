import json
import os
import threading
import numpy as np
import logging

logger = logging.getLogger(__name__)

from xgboost import XGBClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

class XGBoostModel:
    def __init__(self):
        self.reg_c = 0.5
        self.class_weight = "balanced"
        self._build_pipeline()

    def _build_pipeline(self):
        # Convert RegC (higher C = less regularization) to XGBoost's alpha/lambda (higher = more).
        # We'll use a simple heuristic: alpha = 1.0 / (self.reg_c + 0.1)
        alpha_val = 1.0 / (self.reg_c + 0.1)
        
        self.model = make_pipeline(
            StandardScaler(),
            XGBClassifier(
                n_estimators=100,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=alpha_val,  # L1 regularization
                random_state=42,
                eval_metric='logloss'
            )
        )
        self.is_trained = False

    def update_params(self, class_weight: str, reg_c: float):
        self.class_weight = class_weight
        self.reg_c = reg_c
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


class MLEngine:
    def __init__(self, data_dir):
        self.history_file = os.path.join(data_dir, "trades_history.json")
        self.model = XGBoostModel()
        self.is_trained = False
        self.last_trained_mtime = 0.0
        self.feature_keys = [
            "rsi", "bb_upper", "bb_lower", "ema_9", "ema_21", "ema_50",
            "atr", "price_vs_vwap", "cvd_value", "delta_to_target", "score",
            "news_sentiment_score",
            # Low-volume / derivatives signals (added 2026-09-12)
            "orderbook_imbalance", "funding_rate", "open_interest",
            "fng_value", "high_24h", "low_24h", "volume_24h",
        ]
        self._lock = threading.Lock()
        self.train_window = 100

    def apply_settings(self, settings: dict):
        with self._lock:
            self.train_window = int(settings.get("trainWindow", 100))
            class_weight = settings.get("classWeight", "balanced")
            reg_c = float(settings.get("regC", 0.5))
            
            # Update the XGBoost parameters
            self.model.update_params(class_weight, reg_c)
            
            logger.info(f"[MLEngine] Applied new settings. Train window: {self.train_window}, Class Weight: {class_weight}, Reg C: {reg_c}")

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

            res = t.get("result", "")
            if "WIN" in res:
                label = 1
            elif "LOSS" in res:
                label = 0
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
                val = raw.get(k, 0.0)
                if val is None or str(val) == "nan":
                    val = 0.0
                feature_vec.append(float(val))
                
            if valid:
                X.append(feature_vec)
                y.append(label)
                
        # Apply the training window to use only the N most recent trades
        if len(X) > self.train_window:
            X = X[-self.train_window:]
            y = y[-self.train_window:]

        if len(X) < 10:
            # Not enough data to train a reliable model
            return None, None, None
            
        X_arr = np.array(X)
        y_arr = np.array(y)
        
        # AUDIT FIX #5: Removed the 1.8x loss penalty that was corrupting predict_proba() calibration.
        # Recency weighting is kept (recent trades matter more than old ones).
        # Class imbalance is already handled by XGBoost's scale_pos_weight parameter.
        n_samples = len(X_arr)
        weights = []
        for i in range(n_samples):
            recency = 1.0 + (i / max(1, n_samples - 1))
            weights.append(recency)
            
        return X_arr, y_arr, np.array(weights)
        
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
                    logger.info(f"[MLEngine] Training custom ML model on {len(X)} historical trades with Loss Recency Weighting (filter={time_filter})...")
                    self.model.fit(X, y, sample_weight=weights)
                    self.is_trained = True
                    self.last_trained_mtime = mtime
                    logger.info("[MLEngine] Training complete.")
                    return len(X)
            except Exception as e:
                logger.error(f"[MLEngine] Training failed: {e}", exc_info=True)
            return 0
            
    def self_train_on_historical_market(self, df_ind, time_filter: str = "all") -> int:
        """
        Self-trains the model on hundreds of historical 15m intervals, removing the dependency 
        on having to wait for 10 live executed trades to be collected.
        """
        X = []
        y = []
        
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        # df_ind is a pandas DataFrame with indicators. Start at 50 to allow EMAs to warm up.
        for i in range(50, len(df_ind) - 1):
            p = df_ind.iloc[i-1] # previous 15m candle (fully closed)
            c = df_ind.iloc[i]   # interval candle
            
            # Time filter logic
            if time_filter != "all" and "datetime" in c:
                try:
                    dt_obj = c["datetime"]
                    if isinstance(dt_obj, str):
                        dt_obj = datetime.fromisoformat(dt_obj.replace('Z', '+00:00'))
                    ny_dt = dt_obj.astimezone(ZoneInfo("America/New_York"))
                    is_night = 0 <= ny_dt.hour < 7
                    if time_filter == "night" and not is_night:
                        continue
                    if time_filter == "day" and is_night:
                        continue
                except Exception as e:
                    logger.warning(f"[ML] Prediction filtering error: {e}")
                    
            target_price = float(p["close"])
            actual_close = float(c["close"])
            
            high_24h_val = float(df_ind["high"].iloc[max(0, i-96):i].max()) if "high" in df_ind.columns and len(df_ind) > 0 else target_price
            low_24h_val = float(df_ind["low"].iloc[max(0, i-96):i].min()) if "low" in df_ind.columns and len(df_ind) > 0 else target_price
            vol_24h_val = float(df_ind["volume"].iloc[max(0, i-96):i].sum()) if "volume" in df_ind.columns and len(df_ind) > 0 else 0.0

            # AUDIT FIX #9: Compute realistic delta_to_target and technical momentum score
            # to match the live inference feature distribution (instead of leaving them at 0.0)
            c_open = float(c.get("open", target_price))
            hist_delta = ((c_open - target_price) / max(target_price, 1e-9)) * 100.0
            
            # Approximate technical score from RSI and EMA trend alignment
            rsi_val = float(p.get("rsi", 50))
            ema9_val = float(p.get("ema_9", target_price))
            ema21_val = float(p.get("ema_21", target_price))
            hist_score = (rsi_val - 50.0) * 0.8 + (10.0 if ema9_val >= ema21_val else -10.0)
            hist_score = max(-50.0, min(50.0, hist_score))

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
                "score": float(hist_score),
                "news_sentiment_score": float(p.get("news_sentiment_score", 0.0)),
                "orderbook_imbalance": float(p.get("orderbook_imbalance", 0.0)),
                "funding_rate": float(p.get("funding_rate", 0.0)),
                "open_interest": float(p.get("open_interest", 0.0)),
                "fng_value": float(p.get("fng_value", 50.0)),
                "high_24h": high_24h_val,
                "low_24h": low_24h_val,
                "volume_24h": vol_24h_val
            }
            
            # If the actual close was higher than target, it's a WIN for UP (1). Otherwise DOWN (0)
            label = 1 if actual_close >= target_price else 0
            
            feature_vec = []
            valid = True
            for k in self.feature_keys:
                val = raw_feat.get(k, 0.0)
                if val is None or str(val) == "nan":
                    val = 0.0
                feature_vec.append(float(val))
                
            if valid:
                X.append(feature_vec)
                y.append(label)
                
        if len(X) > self.train_window:
            X = X[-self.train_window:]
            y = y[-self.train_window:]
            
        if len(X) >= 10:
            with self._lock:
                self.model.fit(np.array(X), np.array(y))
                self.is_trained = True
                logger.info(f"[MLEngine] Self-trained ML model on {len(X)} historical 15m market intervals.")
                return len(X)
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
            val = current_raw_features.get(k, 0.0)
            feature_vec.append(float(val))
            
        X_pred = np.array([feature_vec])
        prob = self.model.predict_proba(X_pred)[0]
        return prob


# =====================================================================
# SINGLETON FACTORY
# =====================================================================
_ml_engine_instance = None
_ml_engine_lock = threading.Lock()

def get_ml_engine(data_dir: str = None):
    global _ml_engine_instance
    if _ml_engine_instance is None:
        with _ml_engine_lock:
            if _ml_engine_instance is None:
                if data_dir is None:
                    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
                from backend.btc.dual_ml_engine import DualMLEngine
                _ml_engine_instance = DualMLEngine(data_dir)
                _ml_engine_instance.train()
    return _ml_engine_instance
