"""
Empirical Adversarial Stress-Testing Suite for Quant Lab Phase 1.
Challenger: challenger_m4_1
Focus Areas:
1. MarketRegimeClassifier resilience under extreme adversarial inputs:
   - Missing features, non-dict objects, partial schemas
   - NaNs and Infinities across all financial and sports indicator keys
   - Extreme numerical outliers (1e308, -1e308, negative prices/spreads)
   - Zero-range candles (doji: high == low == open == close), inverted candles (high < low)
   - Conflicting trend vs volatility metrics (ADX surge + vol surge + wicks)
2. StrategyCoder and evaluate_signal() edge cases:
   - Boundary prices (0.01, 0.50, 0.99, out-of-bounds prices)
   - Inverted probabilities (target_side YES vs NO with opposing model predictions)
   - Kelly sizing under zero and negative edge (strict f_star == 0.0 and kelly_fraction == 0.0)
   - Dynamic Kalshi taker fee bounds and effective cost ceiling
   - Fractional Kelly caps (quarter Kelly, whipsaw reduction, 0.20 hard cap)
   - Regime conditioning guards and string condition parsing
   - AST sandbox security and injection resilience
"""
import math
import pytest
from backend.engine.quant_lab.regime_classifier import (
    MarketRegimeClassifier,
    REGIME_COMPRESSION,
    REGIME_TREND,
    REGIME_WHIPSAW,
    REGIME_SLUG_COMPRESSION,
    REGIME_SLUG_TREND,
    REGIME_SLUG_WHIPSAW,
    REGIME_CODES,
)
from backend.engine.quant_lab.strategy_coder import (
    StrategyCoder,
    StrategySecurityError,
    verify_code_safety,
)


# ==============================================================================
# 1. MarketRegimeClassifier Adversarial Stress Tests
# ==============================================================================

def test_adversarial_missing_and_malformed_inputs():
    """Verify MarketRegimeClassifier handles missing, None, and malformed inputs with zero crashes."""
    pathological_inputs = [
        None,
        {},
        {"raw_features": None},
        {"raw_features": {}},
        {"indicators": None},
        {"indicators": {}},
        {"raw_features": "invalid_string"},
        {"raw_features": 42},
        {"raw_features": [1, 2, 3]},
        {"indicators": "invalid_indicators"},
        "plain_string_snapshot",
        12345,
        3.14159,
        True,
        False,
        [{"nested": "list"}],
    ]

    for inp in pathological_inputs:
        # Test financial asset
        state_fin = MarketRegimeClassifier.classify_market_state(inp, asset="BTC")
        assert state_fin["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
        assert state_fin["regime_code"] in (0, 1, 2)
        assert state_fin["regime_slug"] in (REGIME_SLUG_COMPRESSION, REGIME_SLUG_TREND, REGIME_SLUG_WHIPSAW)
        assert isinstance(state_fin["metrics"], dict)

        # Test sports asset
        state_sp = MarketRegimeClassifier.classify_market_state(inp, asset="TEN")
        assert state_sp["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
        assert state_sp["regime_code"] in (0, 1, 2)
        assert isinstance(state_sp["metrics"], dict)

        # Test classify_snapshot
        snap_res = MarketRegimeClassifier.classify_snapshot(inp, asset="BTC")
        assert isinstance(snap_res, dict)
        assert snap_res["market_regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
        assert snap_res["regime_code"] in (0, 1, 2)
        assert "raw_features" in snap_res and isinstance(snap_res["raw_features"], dict)


def test_adversarial_nan_and_infinity_inputs():
    """Verify that NaNs and Infinities across all indicator fields are sanitized without crashes."""
    nan = float("nan")
    inf = float("inf")
    ninf = float("-inf")

    # Pathological financial indicators with mixed NaNs and Infinities
    corrupted_fin = {
        "vol_regime_percentile": nan,
        "atr_percentile": inf,
        "adx": ninf,
        "ema_fast": nan,
        "ema_slow": inf,
        "ema_trend": ninf,
        "close": nan,
        "open": inf,
        "high": nan,
        "low": ninf,
        "body_to_range": nan,
        "upper_wick_ratio": inf,
        "lower_wick_ratio": ninf,
        "vol_ratio": nan,
        "cur_price": "NaN",
        "is_whipsaw": nan,
    }

    res_fin = MarketRegimeClassifier.classify_market_state(corrupted_fin, asset="BTC")
    assert res_fin["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
    assert res_fin["regime_code"] in (0, 1, 2)

    # All exported metrics must be finite numbers (no NaN or Inf leakage)
    for k, v in res_fin["metrics"].items():
        if isinstance(v, (int, float)):
            assert not math.isnan(v), f"Metric {k} leaked NaN: {v}"
            assert not math.isinf(v), f"Metric {k} leaked Inf: {v}"

    # Pathological sports indicators with mixed NaNs and Infinities
    corrupted_sp = {
        "spread": nan,
        "price_drift": inf,
        "ai_edge": ninf,
        "market_mid": nan,
    }

    res_sp = MarketRegimeClassifier.classify_market_state(corrupted_sp, asset="MLB")
    assert res_sp["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
    for k, v in res_sp["metrics"].items():
        if isinstance(v, (int, float)):
            assert not math.isnan(v), f"Sports metric {k} leaked NaN: {v}"
            assert not math.isinf(v), f"Sports metric {k} leaked Inf: {v}"


def test_adversarial_extreme_outliers():
    """Verify extreme numerical outliers (astronomical values, negative magnitudes)."""
    # Astronomical positive values
    huge_feats = {
        "adx": 1e20,
        "vol_regime_percentile": 1e10,
        "atr_percentile": 1e12,
        "ema_fast": 1e300,
        "ema_slow": 1e299,
        "ema_trend": 1e298,
        "close": 1e200,
        "open": 1e199,
        "high": 1e201,
        "low": 0.0,
        "vol_ratio": 1e5,
    }
    res_huge = MarketRegimeClassifier.classify_market_state(huge_feats, asset="BTC")
    assert res_huge["regime"] == REGIME_WHIPSAW  # Extreme volatility and volume trigger whipsaw
    assert res_huge["regime_code"] == 2

    # Negative values where positive usually expected
    neg_feats = {
        "adx": -50.0,
        "vol_regime_percentile": -100.0,
        "atr_percentile": -50.0,
        "ema_fast": -1000.0,
        "ema_slow": -2000.0,
        "ema_trend": -3000.0,
        "vol_ratio": -5.0,
    }
    res_neg = MarketRegimeClassifier.classify_market_state(neg_feats, asset="BTC")
    assert res_neg["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)

    # Extremely small near-zero values
    tiny_feats = {
        "adx": 1e-12,
        "ema_fast": 1e-12,
        "ema_slow": 1e-12,
        "ema_trend": 1e-12,
        "close": 1e-10,
        "open": 1e-10,
        "high": 1e-10,
        "low": 1e-10,
        "vol_ratio": 1e-6,
    }
    res_tiny = MarketRegimeClassifier.classify_market_state(tiny_feats, asset="BTC")
    assert res_tiny["regime"] == REGIME_COMPRESSION
    assert res_tiny["regime_code"] == 0


def test_adversarial_zero_range_and_inverted_candles():
    """Verify zero-range flat candles (doji) and inverted candles (high < low)."""
    # 1. Zero-range Doji (high == low == open == close)
    doji = {
        "high": 60000.0,
        "low": 60000.0,
        "open": 60000.0,
        "close": 60000.0,
        "vol_regime_percentile": 0.20,
    }
    res_doji = MarketRegimeClassifier.classify_market_state(doji, asset="BTC")
    assert res_doji["regime"] == REGIME_COMPRESSION
    assert res_doji["metrics"]["body_to_range"] >= 0.0

    # 2. Inverted candle (high < low)
    inverted = {
        "high": 1000.0,
        "low": 2000.0,
        "open": 1500.0,
        "close": 1200.0,
    }
    res_inv = MarketRegimeClassifier.classify_market_state(inverted, asset="BTC")
    assert res_inv["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)

    # 3. Pure wick candle (open == close, massive range)
    pure_wick = {
        "high": 10000.0,
        "low": 0.0,
        "open": 5000.0,
        "close": 5000.0,
        "vol_regime_percentile": 0.88,
        "vol_ratio": 1.5,
    }
    res_wick = MarketRegimeClassifier.classify_market_state(pure_wick, asset="BTC")
    assert res_wick["regime"] == REGIME_WHIPSAW
    assert res_wick["metrics"]["total_wick"] >= 0.55


def test_adversarial_conflicting_trend_and_volatility():
    """Verify decision tree precedence when trend strength conflicts with event-risk whipsaw."""
    # Scenario: Massive trend strength (ADX = 50.0, aligned EMAs) BUT extreme whipsaw risk (vol percentile = 0.96, long wicks)
    # Whipsaw / Event-Risk MUST take priority over Trend-Expansion to protect capital
    conflict_feats = {
        "adx": 50.0,
        "vol_regime_percentile": 0.96,
        "ema_fast": 68000.0,
        "ema_slow": 66000.0,
        "ema_trend": 64000.0,
        "body_to_range": 0.20,
        "upper_wick_ratio": 0.40,
        "lower_wick_ratio": 0.40,
        "vol_ratio": 1.8,
    }
    res = MarketRegimeClassifier.classify_market_state(conflict_feats, asset="BTC")
    assert res["regime"] == REGIME_WHIPSAW, f"Expected WHIPSAW to take precedence over trend, got {res['regime']}"
    assert res["regime_code"] == 2

    # Scenario: High ADX (30.0) but low volume ratio (0.50) and tiny body (0.20) -> should NOT falsely classify as Trend
    weak_trend = {
        "adx": 30.0,
        "vol_ratio": 0.50,
        "body_to_range": 0.20,
        "vol_regime_percentile": 0.30,
    }
    res_weak = MarketRegimeClassifier.classify_market_state(weak_trend, asset="BTC")
    assert res_weak["regime"] == REGIME_COMPRESSION

    # Scenario: Strong directional trend with proper confirmation (ADX = 35.0, body = 0.70, vol_ratio = 1.3, aligned EMAs)
    valid_trend = {
        "adx": 35.0,
        "vol_ratio": 1.3,
        "body_to_range": 0.70,
        "vol_regime_percentile": 0.60,
        "ema_fast": 68000.0,
        "ema_slow": 66000.0,
        "ema_trend": 64000.0,
    }
    res_trend = MarketRegimeClassifier.classify_market_state(valid_trend, asset="BTC")
    assert res_trend["regime"] == REGIME_TREND
    assert res_trend["regime_code"] == 1


def test_adversarial_sports_regimes_and_outliers():
    """Verify sports prediction markets under extreme spreads, drift, and edge values."""
    # 1. Extreme wide spread ($0.12) -> WHIPSAW
    res_wide = MarketRegimeClassifier.classify_market_state({"spread": 0.12, "price_drift": 0.01}, asset="NFL")
    assert res_wide["regime"] == REGIME_WHIPSAW

    # 2. Strong liquid drift (spread = 0.03, drift = 0.05) -> TREND_EXPANSION
    res_trend = MarketRegimeClassifier.classify_market_state({"spread": 0.03, "price_drift": 0.05}, asset="NBA")
    assert res_trend["regime"] == REGIME_TREND

    # 3. High model edge (ai_edge = 8.0) with drift (0.025) -> TREND_EXPANSION
    res_edge = MarketRegimeClassifier.classify_market_state({"ai_edge": 8.0, "price_drift": 0.025, "spread": 0.04}, asset="TEN")
    assert res_trend["regime"] == REGIME_TREND

    # 4. Out-of-bounds inputs (negative spread, market mid = 2.50)
    res_oob = MarketRegimeClassifier.classify_market_state({"spread": -0.05, "market_mid": 2.50, "price_drift": 0.0}, asset="UFC")
    assert res_oob["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
    assert not math.isnan(res_oob["metrics"]["spread"])


# ==============================================================================
# 2. StrategyCoder and evaluate_signal() Adversarial Stress Tests
# ==============================================================================

def test_adversarial_boundary_prices():
    """Verify evaluate_signal() behavior at boundary prices 0.01, 0.50, and 0.99."""
    hypo = {
        "name": "Boundary Price Strategy",
        "target_side": "YES",
        "entry_conditions": [
            {"indicator": "rsi", "operator": "<", "threshold": 50.0}
        ],
        "min_entry_price": 0.01,
        "max_entry_price": 0.99,
        "base_edge": 0.05,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # 1. Lower boundary price: cur_price = 0.01
    snap_001 = {"raw_features": {"rsi": 30.0}, "cur_price": 0.01}
    res_001 = fn(snap_001)
    assert res_001["action"] == "BUY"
    assert 0.05 <= res_001["calibrated_win_prob"] <= 0.95
    assert not math.isnan(res_001["f_star"])
    assert not math.isnan(res_001["kelly_fraction"])
    assert res_001["f_star"] >= 0.0

    # 2. Midpoint boundary price: cur_price = 0.50
    snap_050 = {"raw_features": {"rsi": 30.0}, "cur_price": 0.50}
    res_050 = fn(snap_050)
    assert res_050["action"] == "BUY"
    assert res_050["win_probability"] > 0.50
    assert res_050["f_star"] > 0.0
    assert res_050["kelly_fraction"] > 0.0

    # 3. Upper boundary price: cur_price = 0.99
    snap_099 = {"raw_features": {"rsi": 30.0}, "cur_price": 0.99}
    res_099 = fn(snap_099)
    assert res_099["action"] == "BUY"
    assert not math.isnan(res_099["f_star"])
    assert not math.isnan(res_099["kelly_fraction"])
    # Denominator in Kelly formula at c_eff close to 0.98 must never cause ZeroDivisionError
    assert res_099["kelly_fraction"] >= 0.0

    # 4. Out-of-bounds prices: 0.00, -0.50, 1.50
    # Code clamps cur_price to max(0.01, min(0.99, cur_price)), so 0.00 becomes 0.01, 1.50 becomes 0.99
    snap_zero = {"raw_features": {"rsi": 30.0}, "cur_price": 0.00}
    res_zero = fn(snap_zero)
    assert res_zero["action"] == "BUY"  # Clamped to 0.01, passes corridor [0.01, 0.99]

    # Test corridor rejection when prices exceed specified min/max corridor
    hypo_narrow = {
        "name": "Narrow Corridor Strategy",
        "target_side": "YES",
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 50.0}],
        "min_entry_price": 0.20,
        "max_entry_price": 0.80,
    }
    code_narrow, _ = StrategyCoder.generate_code(hypo_narrow)
    fn_narrow = StrategyCoder.compile_strategy(code_narrow)
    res_rejected_low = fn_narrow({"raw_features": {"rsi": 30.0}, "cur_price": 0.10})
    assert res_rejected_low["action"] == "PASS"
    assert res_rejected_low["reason"] == "price_outside_corridor"

    res_rejected_high = fn_narrow({"raw_features": {"rsi": 30.0}, "cur_price": 0.90})
    assert res_rejected_high["action"] == "PASS"
    assert res_rejected_high["reason"] == "price_outside_corridor"


def test_adversarial_inverted_probabilities():
    """Verify correct probability inversion for NO contracts vs YES contracts."""
    # Strategy 1: Target side YES
    hypo_yes = {
        "name": "Target YES Alpha",
        "target_side": "YES",
        "entry_conditions": [{"indicator": "signal", "operator": "==", "threshold": "GO"}],
        "min_entry_price": 0.10,
        "max_entry_price": 0.90,
    }
    fn_yes = StrategyCoder.compile_strategy(StrategyCoder.generate_code(hypo_yes)[0])

    # Strategy 2: Target side NO
    hypo_no = {
        "name": "Target NO Alpha",
        "target_side": "NO",
        "entry_conditions": [{"indicator": "signal", "operator": "==", "threshold": "GO"}],
        "min_entry_price": 0.10,
        "max_entry_price": 0.90,
    }
    fn_no = StrategyCoder.compile_strategy(StrategyCoder.generate_code(hypo_no)[0])

    # Scenario A: AI model predicts YES wins with 80% probability (ai_win_prob = 80.0)
    # YES trade should have positive edge; NO trade should have negative edge
    snap_high_yes = {
        "raw_features": {"signal": "GO", "ai_win_prob": 80.0},
        "cur_price": 0.60  # YES costs $0.60, NO costs $0.40
    }
    sig_yes = fn_yes(snap_high_yes)
    sig_no = fn_no(snap_high_yes)

    assert sig_yes["action"] == "BUY"
    assert sig_yes["side"] == "YES"
    assert sig_yes["calibrated_win_prob"] > 0.60  # Model says 80% -> calibrated > 60%
    assert sig_yes["expected_edge"] > 0.0
    assert sig_yes["kelly_fraction"] > 0.0

    assert sig_no["action"] == "BUY"
    assert sig_no["side"] == "NO"
    # For NO, model probability is inverted: 1.0 - 0.80 = 0.20
    # Cost of NO contract is 1.0 - 0.60 = 0.40
    # Calibrated probability (~0.27) < cost (0.40) -> Negative Edge!
    assert sig_no["calibrated_win_prob"] < 0.40
    assert sig_no["expected_edge"] < 0.0
    assert sig_no["f_star"] == 0.0
    assert sig_no["kelly_fraction"] == 0.0, "NO wager must have zero Kelly sizing under negative edge!"

    # Scenario B: AI model predicts YES wins with only 20% probability (ai_win_prob = 20.0)
    # NO trade should now have positive edge; YES trade should have negative edge
    snap_low_yes = {
        "raw_features": {"signal": "GO", "ai_win_prob": 20.0},
        "cur_price": 0.50  # YES costs $0.50, NO costs $0.50
    }
    sig_yes_b = fn_yes(snap_low_yes)
    sig_no_b = fn_no(snap_low_yes)

    # YES has negative edge (model prob 20% vs cost 50%) -> Kelly must be 0.0
    assert sig_yes_b["expected_edge"] < 0.0
    assert sig_yes_b["f_star"] == 0.0
    assert sig_yes_b["kelly_fraction"] == 0.0

    # NO has positive edge (model prob 80% vs cost 50%) -> Kelly must be > 0.0
    assert sig_no_b["calibrated_win_prob"] > 0.50
    assert sig_no_b["expected_edge"] > 0.0
    assert sig_no_b["f_star"] > 0.0
    assert sig_no_b["kelly_fraction"] > 0.0


def test_adversarial_kelly_zero_and_negative_edge():
    """Verify Kelly sizing returns strictly 0.0 under zero or negative edge."""
    # Construct hypothesis with deliberately negative base_edge
    hypo_neg = {
        "name": "Negative Edge Strategy",
        "target_side": "YES",
        "base_edge": -0.15,
        "entry_conditions": [{"indicator": "active", "operator": "==", "threshold": "TRUE"}],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    fn_neg = StrategyCoder.compile_strategy(StrategyCoder.generate_code(hypo_neg)[0])

    # Various price levels where edge is guaranteed to be negative
    test_prices = [0.10, 0.25, 0.50, 0.75, 0.90]
    for p in test_prices:
        res = fn_neg({"raw_features": {"active": "TRUE"}, "cur_price": p})
        assert res["action"] == "BUY"
        assert res["expected_edge"] <= 0.0, f"Expected non-positive edge at price {p}, got {res['expected_edge']}"
        assert res["f_star"] == 0.0, f"Expected f_star == 0.0 at price {p}, got {res['f_star']}"
        assert res["kelly_fraction"] == 0.0, f"Expected kelly_fraction == 0.0 at price {p}, got {res['kelly_fraction']}"
        assert res["kelly_sizing_fraction"] == 0.0


def test_adversarial_taker_fee_bounds():
    """Verify Kalshi taker fee bounds and effective cost calculation."""
    # Dynamic taker fee formula in strategy_coder.py:
    # fee = int(0.07 * side_cost * (1.0 - side_cost) * 100.0 + 0.9999) / 100.0
    # c_eff = min(0.98, side_cost + fee)
    for price_cents in range(1, 100):
        side_cost = price_cents / 100.0
        clamped_cost = max(0.02, min(0.98, side_cost))
        fee = int(0.07 * clamped_cost * (1.0 - clamped_cost) * 100.0 + 0.9999) / 100.0
        c_eff = min(0.98, clamped_cost + fee)

        # 1. Fee must be between $0.01 and $0.02
        assert 0.01 <= fee <= 0.02, f"Fee {fee} out of bounds for cost {side_cost}"

        # 2. Maximum fee occurs near 50 cents ($0.02)
        if 0.40 <= side_cost <= 0.60:
            assert fee == 0.02

        # 3. c_eff must never reach 1.0 (prevents division by zero)
        assert c_eff <= 0.98
        assert (1.0 - c_eff) >= 0.02


def test_adversarial_fractional_kelly_caps():
    """Verify fractional Kelly multiplier and hard cap (0.20) under maximum possible edge."""
    # Test strategy targeting WHIPSAW vs COMPRESSION
    hypo_whip = {
        "name": "Whipsaw Strat",
        "target_side": "YES",
        "target_regimes": ["HIGH_WHIPSAW_EVENT_RISK"],
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 50.0}],
    }
    hypo_comp = {
        "name": "Compression Strat",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 50.0}],
    }

    fn_whip = StrategyCoder.compile_strategy(StrategyCoder.generate_code(hypo_whip)[0])
    fn_comp = StrategyCoder.compile_strategy(StrategyCoder.generate_code(hypo_comp)[0])

    # Extreme model conviction: ai_win_prob = 100%
    snap_whip = {
        "raw_features": {"rsi": 30.0, "ai_win_prob": 100.0},
        "cur_price": 0.30,
        "market_regime": "HIGH_WHIPSAW_EVENT_RISK"
    }
    snap_comp = {
        "raw_features": {"rsi": 30.0, "ai_win_prob": 100.0},
        "cur_price": 0.30,
        "market_regime": "COMPRESSION_MEAN_REVERSION"
    }

    res_whip = fn_whip(snap_whip)
    res_comp = fn_comp(snap_comp)

    # 1. Both fractions must never exceed the 0.20 hard cap (20% bankroll limit)
    assert res_whip["kelly_fraction"] <= 0.20
    assert res_comp["kelly_fraction"] <= 0.20

    # 2. In whipsaw, lambda is 0.15 vs 0.25 in compression -> whipsaw fraction must be strictly smaller
    assert res_whip["kelly_fraction"] <= 0.15
    assert res_whip["kelly_fraction"] < res_comp["kelly_fraction"], (
        f"Whipsaw Kelly ({res_whip['kelly_fraction']}) should be smaller than Compression ({res_comp['kelly_fraction']})"
    )


def test_adversarial_regime_conditioning_guards():
    """Verify strategy execution conditioned on specific market regimes."""
    hypo = {
        "name": "Momentum Breakout",
        "target_side": "YES",
        "target_regimes": ["TREND_EXPANSION_MOMENTUM"],
        "entry_conditions": [{"indicator": "adx", "operator": ">", "threshold": 25.0}],
    }
    fn = StrategyCoder.compile_strategy(StrategyCoder.generate_code(hypo)[0])

    # Case 1: Matching regime -> BUY
    res_match = fn({
        "raw_features": {"adx": 30.0},
        "cur_price": 0.50,
        "market_regime": "TREND_EXPANSION_MOMENTUM"
    })
    assert res_match["action"] == "BUY"

    # Case 2: Conflicting regime -> PASS with regime_mismatch reason
    res_conflict = fn({
        "raw_features": {"adx": 30.0},
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION"
    })
    assert res_conflict["action"] == "PASS"
    assert res_conflict["reason"] == "regime_mismatch"

    # Case 3: Conflicting regime in whipsaw -> PASS
    res_whip = fn({
        "raw_features": {"adx": 30.0},
        "cur_price": 0.50,
        "market_regime": "HIGH_WHIPSAW_EVENT_RISK"
    })
    assert res_whip["action"] == "PASS"
    assert res_whip["reason"] == "regime_mismatch"

    # Case 4: Snapshot with no regime specified -> Gracefully executes rule evaluation
    res_no_reg = fn({
        "raw_features": {"adx": 30.0},
        "cur_price": 0.50
    })
    assert res_no_reg["action"] == "BUY"


def test_adversarial_string_conditions_and_feature_comparisons():
    """Verify string literal conditions and indicator-to-indicator comparisons."""
    # 1. Categorical string equality (market_regime == "COMPRESSION_MEAN_REVERSION")
    hypo_str = {
        "name": "Regime Guard String Condition",
        "target_side": "YES",
        "entry_conditions": [
            {"indicator": "market_regime", "operator": "==", "threshold": "COMPRESSION_MEAN_REVERSION"}
        ],
    }
    code_str, _ = StrategyCoder.generate_code(hypo_str)
    fn_str = StrategyCoder.compile_strategy(code_str)

    res_pass = fn_str({"raw_features": {"market_regime": "TREND_EXPANSION_MOMENTUM"}, "cur_price": 0.50})
    assert res_pass["action"] == "PASS"

    res_buy = fn_str({"raw_features": {"market_regime": "COMPRESSION_MEAN_REVERSION"}, "cur_price": 0.50})
    assert res_buy["action"] == "BUY"

    # 2. Indicator comparison against another indicator (ema_fast > ema_slow)
    hypo_feat = {
        "name": "EMA Crossover Feature Comparison",
        "target_side": "YES",
        "entry_conditions": [
            {"indicator": "ema_fast", "operator": ">", "threshold": "ema_slow"}
        ],
    }
    code_feat, _ = StrategyCoder.generate_code(hypo_feat)
    fn_feat = StrategyCoder.compile_strategy(code_feat)

    # Fast <= Slow -> PASS
    res_f_low = fn_feat({"raw_features": {"ema_fast": 65000.0, "ema_slow": 66000.0}, "cur_price": 0.50})
    assert res_f_low["action"] == "PASS"

    # Fast > Slow -> BUY
    res_f_high = fn_feat({"raw_features": {"ema_fast": 67000.0, "ema_slow": 66000.0}, "cur_price": 0.50})
    assert res_f_high["action"] == "BUY"


def test_adversarial_ast_sandbox_security():
    """Verify strict AST safety against malicious code injection and forbidden calls."""
    # Attempting to call system commands or forbidden functions
    dangerous_payloads = [
        "import os",
        "import sys",
        "from os import system",
        "open('test.txt', 'w')",
        "eval('2+2')",
        "exec('a = 1')",
        "__import__('os')",
        "getattr(object, '__class__')",
        "setattr(object, 'attr', 1)",
        "delattr(object, 'attr')",
        "globals()",
        "locals()",
        "subprocess()",
        "os()",
        "sys()",
        "socket()",
        "urllib()",
        "requests()",
    ]

    for p in dangerous_payloads:
        # verify_code_safety must reject
        with pytest.raises(StrategySecurityError):
            verify_code_safety(f"def evaluate_signal(snap):\n    {p}\n    return {{'action': 'BUY'}}")

        # StrategyCoder.compile_strategy must reject
        with pytest.raises(StrategySecurityError):
            StrategyCoder.compile_strategy(f"def evaluate_signal(snap):\n    {p}\n    return {{'action': 'BUY'}}")


def test_adversarial_ast_sandbox_subclasses_introspection():
    """
    Adversarial Challenge Finding:
    Empirically tests AST sandbox boundary regarding Python MRO / subclass introspection.
    verify_code_safety blocks direct forbidden calls and explicit imports,
    but does not currently block dunder attribute traversal via ().__class__.__base__.__subclasses__().
    """
    payload = '''
def evaluate_signal(snapshot):
    importers = [c for c in ().__class__.__base__.__subclasses__() if c.__name__ == "BuiltinImporter"]
    if importers:
        sys = importers[0]().load_module("sys")
        os = sys.modules.get("os")
        if os is not None:
            return {"action": "CRITICAL_ESCAPE", "os_module_found": True}
    return {"action": "SAFE"}
'''
    fn = StrategyCoder.compile_strategy(payload)
    res = fn({})
    # Empirically proves that without dunder blocking, MRO traversal reaches BuiltinImporter and frozen os module
    assert res["action"] == "CRITICAL_ESCAPE"
    assert res["os_module_found"] is True


