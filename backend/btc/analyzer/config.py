
import logging

logger = logging.getLogger(__name__)
try:

    pass
except ImportError:
    pass


# -------------------------------------------------------------------
THRESHOLDS = {
    # evaluate_next_15m_contract blending (tuned via walk-forward grid search, see backend/data/backtest_report.json)
    "heuristic_weight": 0.40,
    "ml_weight": 0.60,
    "model_conflict_threshold": 15.0,
    "model_conflict_cap": 58.0,

    # analyze_btc rules vs ML blend
    "analyze_rules_weight": 0.70,
    "analyze_ml_weight": 0.30,

    # Kalshi market-structure thresholds
    "kalshi_override_yes": 62.0,
    "kalshi_override_no": 62.0,
    "kalshi_imbalance_threshold": 25.0,
    "kalshi_whales_extreme_yes": 75.0,
    "kalshi_whales_extreme_no": 25.0,

    # Strike pin risk & dead zone
    "pin_delta_dollars": 15.0,
    "pin_atr_max": 45.0,

    # Setup detection thresholds
    "bollinger_wick_min": 0.35,
    "bollinger_rsi_bear": 62.0,
    "bollinger_rsi_bull": 38.0,
    "climax_rsi_bear": 64.0,
    "climax_rsi_bull": 36.0,
    "ribbon_wick_min": 0.28,
    "b_setup_rsi_bear": 58.0,
    "b_setup_rsi_bull": 42.0,
    "thrust_range_closure_bull": 0.80,
    "thrust_range_closure_bear": 0.20,
    "thrust_body_range_min": 0.55,
    "rsi_bb_momentum_bull": 65.0,
    "rsi_bb_flush_bear": 35.0,

    # Order flow / CVD & Imbalance gates
    "cvd_gate_bear_limit": -2.0,
    "cvd_gate_bull_limit": 2.0,
    "imbalance_gate_bear_wall": -30.0,
    "imbalance_gate_bid_wall": 30.0,
}

HEURISTIC_WEIGHT = THRESHOLDS['heuristic_weight']
ML_WEIGHT = THRESHOLDS['ml_weight']
_ANALYZER_EXECUTOR = None
