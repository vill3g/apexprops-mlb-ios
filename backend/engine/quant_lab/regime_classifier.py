"""
Market Regime Classifier for ShadowTrader AI Quant Lab.

Classifies financial and sports/prediction market states into distinct structural regimes:
1. Compression/Mean-Reversion (COMPRESSION_MEAN_REVERSION, code 0)
2. Trend-Expansion/Momentum (TREND_EXPANSION_MOMENTUM, code 1)
3. High-Whipsaw/Event-Risk (HIGH_WHIPSAW_EVENT_RISK, code 2)

Provides zero-exception snapshot enrichment across sparse, synthetic, and partial snapshots.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Standard structural regime labels and slugs
REGIME_COMPRESSION = "Compression/Mean-Reversion"
REGIME_TREND = "Trend-Expansion/Momentum"
REGIME_WHIPSAW = "High-Whipsaw/Event-Risk"

REGIME_SLUG_COMPRESSION = "COMPRESSION_MEAN_REVERSION"
REGIME_SLUG_TREND = "TREND_EXPANSION_MOMENTUM"
REGIME_SLUG_WHIPSAW = "HIGH_WHIPSAW_EVENT_RISK"

REGIME_CODES = {
    REGIME_COMPRESSION: 0,
    REGIME_TREND: 1,
    REGIME_WHIPSAW: 2,
    REGIME_SLUG_COMPRESSION: 0,
    REGIME_SLUG_TREND: 1,
    REGIME_SLUG_WHIPSAW: 2,
}

REGIME_SLUGS = {
    REGIME_COMPRESSION: REGIME_SLUG_COMPRESSION,
    REGIME_TREND: REGIME_SLUG_TREND,
    REGIME_WHIPSAW: REGIME_SLUG_WHIPSAW,
}

SPORTS_ASSETS = {
    "SPORTS", "SPORT", "NFL", "MLB", "NBA", "NHL", "NPB", "KBO", "NPB/KBO", "NPB_KBO", "NPB-KBO",
    "SOC", "SOCCER", "UFC", "MMA", "TEN", "TENNIS", "ALL", "WNBA", "NCAAF", "NCAAB",
    "EPL", "MLS", "BUNDESLIGA", "LALIGA", "SERIEA"
}


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Extract a float safely, falling back to default on None, NaN, inf, or error."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default


class MarketRegimeClassifier:
    """
    Autonomous multi-universe market regime classifier.
    Evaluates volatility percentiles, trend alignment, candle dynamics,
    and market microstructure / orderbook signals.
    """

    @classmethod
    def is_sports_universe(cls, asset: str = "BTC", features: Optional[Dict[str, Any]] = None) -> bool:
        """Determines whether asset belongs to sports / prediction markets."""
        asset_norm = str(asset or "").strip().upper()
        if asset_norm in SPORTS_ASSETS:
            return True
        if features and isinstance(features, dict):
            # Check for sports-distinctive market features when ADX/OHLCV indicators are absent
            if ("ai_win_prob" in features or "sim_score" in features) and "adx" not in features:
                return True
        return False

    @classmethod
    def classify_market_state(cls, features: Optional[Dict[str, Any]], asset: str = "BTC") -> Dict[str, Any]:
        """
        Classifies the market state from a dictionary of features or indicators.
        Guaranteed zero-exception execution on empty or sparse dictionaries.
        """
        if not isinstance(features, dict):
            features = {}

        if cls.is_sports_universe(asset, features):
            return cls._classify_sports_state(features, asset)
        else:
            return cls._classify_financial_state(features, asset)

    @classmethod
    def _classify_financial_state(cls, features: Dict[str, Any], asset: str = "BTC") -> Dict[str, Any]:
        """Evaluates financial indicators (OHLCV, ATR, ADX, EMAs, candle wicks/body)."""
        # 1. Volatility Percentile [0.0, 1.0]
        vol_pct_raw = features.get("vol_regime_percentile")
        if vol_pct_raw is None:
            vol_pct_raw = features.get("atr_percentile")
            if vol_pct_raw is not None:
                vol_pct = _safe_float(vol_pct_raw, 50.0) / 100.0
            else:
                vol_pct = 0.50
        else:
            vol_pct_val = _safe_float(vol_pct_raw, 0.50)
            vol_pct = (vol_pct_val / 100.0) if vol_pct_val > 1.0 else vol_pct_val
        vol_pct = max(0.0, min(1.0, vol_pct))

        # 2. Directional Trend Strength
        adx = _safe_float(features.get("adx"), 20.0)
        ema_fast = _safe_float(features.get("ema_fast") or features.get("ema_9"), 0.0)
        ema_slow = _safe_float(features.get("ema_slow") or features.get("ema_21"), 0.0)
        ema_trend = _safe_float(features.get("ema_trend") or features.get("ema_50"), 0.0)

        # Normalized EMA slope / separation
        if ema_slow > 1e-6:
            ema_slope = abs(ema_fast - ema_slow) / ema_slow
        else:
            ema_slope = 0.0

        # Aligned trend hierarchy: fast > slow > trend or fast < slow < trend
        trend_aligned = (
            (ema_fast > ema_slow > ema_trend > 0.0) or
            (0.0 < ema_fast < ema_slow < ema_trend)
        )

        # 3. Candle Dynamics (Price Action Structure)
        close = _safe_float(features.get("close") or features.get("price") or features.get("cur_price"), 0.0)
        open_val = _safe_float(features.get("open"), close)
        high = _safe_float(features.get("high"), max(close, open_val))
        low = _safe_float(features.get("low"), min(close, open_val))
        range_hl = max(1e-6, high - low)

        body_raw = features.get("body_to_range")
        if body_raw is not None:
            body_to_range = max(0.0, min(1.0, _safe_float(body_raw, 0.5)))
        else:
            body_to_range = max(0.0, min(1.0, abs(close - open_val) / range_hl))

        upper_raw = features.get("upper_wick_ratio")
        if upper_raw is not None:
            upper_wick = max(0.0, min(1.0, _safe_float(upper_raw, 0.0)))
        else:
            upper_wick = max(0.0, min(1.0, (high - max(open_val, close)) / range_hl))

        lower_raw = features.get("lower_wick_ratio")
        if lower_raw is not None:
            lower_wick = max(0.0, min(1.0, _safe_float(lower_raw, 0.0)))
        else:
            lower_wick = max(0.0, min(1.0, (min(open_val, close) - low) / range_hl))

        total_wick = upper_wick + lower_wick
        vol_ratio = _safe_float(features.get("vol_ratio") or features.get("volume_15m_ratio"), 1.0)
        is_whipsaw_flag = bool(features.get("is_whipsaw", False))

        # Decision Tree for Financial Regimes:
        # A. High-Whipsaw / Event-Risk
        if (
            is_whipsaw_flag or
            (vol_pct >= 0.85 and (total_wick >= 0.55 or body_to_range <= 0.35)) or
            (upper_wick >= 0.35 and lower_wick >= 0.35 and vol_ratio >= 1.3) or
            (vol_ratio >= 1.7 and body_to_range <= 0.35) or
            (vol_pct >= 0.90)
        ):
            regime = REGIME_WHIPSAW
        # B. Trend-Expansion / Momentum
        elif (
            (adx >= 25.0 and body_to_range >= 0.50 and vol_ratio >= 1.0) or
            (adx >= 22.0 and trend_aligned and ema_slope >= 0.0012) or
            (vol_pct >= 0.50 and body_to_range >= 0.65 and adx >= 20.0) or
            (adx >= 28.0 and vol_pct >= 0.40)
        ):
            regime = REGIME_TREND
        # C. Compression / Mean-Reversion (Consolidation default)
        else:
            regime = REGIME_COMPRESSION

        regime_slug = REGIME_SLUGS[regime]
        regime_code = REGIME_CODES[regime]

        metrics = {
            "vol_percentile": round(vol_pct * 100.0, 1),
            "adx": round(adx, 1),
            "ema_slope": round(ema_slope, 5),
            "trend_aligned": bool(trend_aligned),
            "body_to_range": round(body_to_range, 3),
            "upper_wick": round(upper_wick, 3),
            "lower_wick": round(lower_wick, 3),
            "total_wick": round(total_wick, 3),
            "vol_ratio": round(vol_ratio, 2),
        }

        return {
            "regime": regime,
            "regime_slug": regime_slug,
            "regime_code": regime_code,
            "metrics": metrics
        }

    @classmethod
    def _classify_sports_state(cls, features: Dict[str, Any], asset: str = "SPORTS") -> Dict[str, Any]:
        """Evaluates sports prediction market indicators (spread, drift, model edge)."""
        spread = _safe_float(features.get("spread"), 0.03)
        price_drift = _safe_float(features.get("price_drift"), 0.0)
        ai_edge = _safe_float(features.get("ai_edge"), 0.0)
        market_mid = _safe_float(features.get("market_mid"), 0.50)

        # Decision Tree for Sports Regimes:
        # A. High-Whipsaw / Event-Risk: wide spread, volatile late price drift, or sudden injury/line flip
        if (spread >= 0.07) or (abs(price_drift) >= 0.06 and spread >= 0.05):
            regime = REGIME_WHIPSAW
        # B. Trend-Expansion / Momentum: sustained directional line drift on liquid spread or strong model conviction
        elif (abs(price_drift) >= 0.03 and spread <= 0.05) or (abs(ai_edge) >= 5.0 and abs(price_drift) >= 0.02):
            regime = REGIME_TREND
        # C. Compression / Mean-Reversion: tight spread, minimal drift, balanced market
        else:
            regime = REGIME_COMPRESSION

        regime_slug = REGIME_SLUGS[regime]
        regime_code = REGIME_CODES[regime]

        metrics = {
            "spread": round(spread, 4),
            "price_drift": round(price_drift, 4),
            "ai_edge": round(ai_edge, 2),
            "market_mid": round(market_mid, 4),
        }

        return {
            "regime": regime,
            "regime_slug": regime_slug,
            "regime_code": regime_code,
            "metrics": metrics
        }

    @classmethod
    def classify_snapshot(cls, snapshot: Optional[Dict[str, Any]], asset: str = "BTC") -> Dict[str, Any]:
        """
        Safely classifies and injects regime attributes directly into a snapshot dictionary.
        Guarantees zero exceptions on None, empty, or sparse snapshot objects.
        Enriches top-level snapshot, raw_features, and indicators dictionaries.
        """
        if not isinstance(snapshot, dict):
            snapshot = {}

        # Safely locate feature dictionary
        features = snapshot.get("raw_features")
        if not isinstance(features, dict):
            features = snapshot.get("indicators")
        if not isinstance(features, dict):
            features = snapshot

        state = cls.classify_market_state(features, asset=asset)
        regime_label = state["regime"]
        regime_slug = state["regime_slug"]
        regime_code = state["regime_code"]

        # 1. Top-level snapshot enrichment
        snapshot["market_regime"] = regime_label
        snapshot["regime"] = regime_label
        snapshot["regime_code"] = regime_code
        snapshot["regime_slug"] = regime_slug
        snapshot["regime_metrics"] = state["metrics"]

        # 2. Inner raw_features enrichment
        if "raw_features" not in snapshot or not isinstance(snapshot["raw_features"], dict):
            snapshot["raw_features"] = {}
        snapshot["raw_features"]["market_regime"] = regime_label
        snapshot["raw_features"]["regime"] = regime_label
        snapshot["raw_features"]["regime_code"] = regime_code
        snapshot["raw_features"]["regime_slug"] = regime_slug

        # 3. Inner indicators enrichment (if present)
        if "indicators" in snapshot and isinstance(snapshot["indicators"], dict):
            snapshot["indicators"]["market_regime"] = regime_label
            snapshot["indicators"]["regime"] = regime_label
            snapshot["indicators"]["regime_code"] = regime_code
            snapshot["indicators"]["regime_slug"] = regime_slug

        return snapshot
