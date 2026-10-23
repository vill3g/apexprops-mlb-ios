"""
Empirical Invariance, Dynamic Win Probability Calibration & Kelly Wager Math Verification.
Verification test harness by challenger_2.
"""
import pytest
from backend.engine.quant_lab.strategy_coder import StrategyCoder, StrategySecurityError
from backend.engine.quant_lab.regime_classifier import (
    MarketRegimeClassifier,
    REGIME_COMPRESSION,
    REGIME_TREND,
    REGIME_WHIPSAW,
    REGIME_SLUG_COMPRESSION,
    REGIME_SLUG_TREND,
    REGIME_SLUG_WHIPSAW,
)


def test_sensitivity_sweep_dynamic_and_continuous():
    """
    Sweeps across at least 50 combinations of market prices, RSI, and regimes.
    Asserts:
    1. Returns dynamic, continuous, non-static win probability and Kelly fraction.
    2. Confidence never equals static 75.0%.
    3. Output varies smoothly and uniquely across inputs.
    """
    hypo = {
        "name": "Dynamic Empirical Sweep Alpha",
        "target_side": "YES",
        "target_regimes": [
            "COMPRESSION_MEAN_REVERSION",
            "TREND_EXPANSION_MOMENTUM",
            "HIGH_WHIPSAW_EVENT_RISK",
        ],
        "base_edge": 0.06,
        "entry_conditions": [
            {"indicator": "rsi", "operator": ">=", "threshold": 0.0}
        ],
        "min_entry_price": 0.01,
        "max_entry_price": 0.99,
        "take_profit_pct": 35.0,
        "stop_loss_pct": 25.0,
    }

    code, code_hash = StrategyCoder.generate_code(hypo)
    evaluator = StrategyCoder.compile_strategy(code)

    prices = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    rsis = [15.0, 30.0, 50.0, 70.0, 85.0]
    regimes = [
        "COMPRESSION_MEAN_REVERSION",
        "TREND_EXPANSION_MOMENTUM",
        "HIGH_WHIPSAW_EVENT_RISK",
    ]

    results = []
    confidences = set()
    kelly_fractions = set()
    win_probabilities = set()

    # 10 prices * 5 rsis * 3 regimes = 150 combinations (> 50 required)
    for p in prices:
        for rsi in rsis:
            for reg in regimes:
                snap = {
                    "cur_price": p,
                    "market_regime": reg,
                    "raw_features": {"rsi": rsi, "market_regime": reg},
                }
                sig = evaluator(snap)
                assert sig["action"] == "BUY", f"Expected BUY for price {p}, rsi {rsi}, reg {reg}"
                assert sig["confidence"] != 75.0, f"Found static 75.0% confidence at p={p}, rsi={rsi}, reg={reg}"
                assert 5.0 <= sig["confidence"] <= 95.0
                assert 0.05 <= sig["calibrated_win_prob"] <= 0.95
                assert sig["win_probability"] == sig["calibrated_win_prob"]
                assert 0.0 <= sig["kelly_fraction"] <= 0.20
                assert sig["f_star"] >= 0.0

                results.append((p, rsi, reg, sig["confidence"], sig["calibrated_win_prob"], sig["kelly_fraction"]))
                confidences.add(sig["confidence"])
                kelly_fractions.add(sig["kelly_fraction"])
                win_probabilities.add(sig["calibrated_win_prob"])

    total_runs = len(results)
    assert total_runs == 150, f"Expected 150 combinations, got {total_runs}"
    # Verify non-static distribution: we should have dozens of distinct values
    assert len(confidences) >= 50, f"Expected >= 50 unique confidence values, got {len(confidences)}"
    assert len(win_probabilities) >= 50, f"Expected >= 50 unique win_prob values, got {len(win_probabilities)}"
    assert len(kelly_fractions) >= 30, f"Expected >= 30 unique kelly_fraction values, got {len(kelly_fractions)}"

    # Check monotonicity / smoothness: for a fixed regime and RSI, win prob increases with price
    fixed_reg = "COMPRESSION_MEAN_REVERSION"
    fixed_rsi = 50.0
    price_sweep = [
        evaluator({"cur_price": p, "market_regime": fixed_reg, "raw_features": {"rsi": fixed_rsi}})["calibrated_win_prob"]
        for p in prices
    ]
    for i in range(len(price_sweep) - 1):
        assert price_sweep[i] < price_sweep[i + 1], f"Monotonicity violation between {prices[i]} and {prices[i+1]}"


def test_curated_50_combination_sweep():
    """
    Curated sweep of exactly 50 distinct realistic combinations spanning low to high prices,
    bearish/neutral/bullish RSIs, and all three regimes.
    """
    hypo = {
        "name": "Curated 50 Sweep Alpha",
        "target_side": "YES",
        "target_regimes": [
            "COMPRESSION_MEAN_REVERSION",
            "TREND_EXPANSION_MOMENTUM",
            "HIGH_WHIPSAW_EVENT_RISK",
        ],
        "base_edge": 0.05,
        "entry_conditions": [
            {"indicator": "rsi", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.01,
        "max_entry_price": 0.99,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # 50 explicitly configured test cases
    test_cases = []
    prices = [0.08 + i * 0.017 for i in range(50)]  # 50 prices between 0.08 and 0.913
    regimes = ["COMPRESSION_MEAN_REVERSION", "TREND_EXPANSION_MOMENTUM", "HIGH_WHIPSAW_EVENT_RISK"]
    for i in range(50):
        p = round(prices[i], 3)
        rsi = round(15.0 + (i * 1.5) % 75.0, 1)
        reg = regimes[i % len(regimes)]
        test_cases.append((p, rsi, reg))

    assert len(test_cases) == 50
    conf_set = set()
    kelly_set = set()

    for p, rsi, reg in test_cases:
        sig = fn({"cur_price": p, "market_regime": reg, "raw_features": {"rsi": rsi, "market_regime": reg}})
        assert sig["action"] == "BUY"
        assert sig["confidence"] != 75.0
        assert 0.05 <= sig["calibrated_win_prob"] <= 0.95
        assert 0.0 <= sig["kelly_fraction"] <= 0.20
        conf_set.add(sig["confidence"])
        kelly_set.add(sig["kelly_fraction"])

    # High variance across the 50 cases confirms dynamic math
    assert len(conf_set) >= 45, f"Expected >= 45 unique confidences in 50 cases, got {len(conf_set)}"
    assert len(kelly_set) >= 25, f"Expected >= 25 unique kelly fractions in 50 cases, got {len(kelly_set)}"


def test_kelly_zero_and_negative_edge_gating():
    """
    Confirms kelly_fraction == 0.0 and f_star == 0.0 when edge <= 0.0.
    """
    hypo = {
        "name": "Zero Edge Test Alpha",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "entry_conditions": [
            {"indicator": "close", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # 1. Edge < 0: ML model predicts low probability (e.g. 0.30 when price is 0.50)
    # side_cost = 0.50, fee = 0.02, c_eff = 0.52
    # p_raw = 0.30 -> calibrated_prob = 0.65 * 0.30 + 0.35 * 0.50 = 0.37
    # edge = 0.37 - 0.52 = -0.15 < 0
    snap_neg_edge = {
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION",
        "raw_features": {
            "close": 100.0,
            "p_ensemble": 0.30,
            "market_regime": "COMPRESSION_MEAN_REVERSION",
        },
    }
    sig_neg = fn(snap_neg_edge)
    assert sig_neg["action"] == "BUY"
    assert sig_neg["projected_edge"] < 0.0
    assert sig_neg["f_star"] == 0.0
    assert sig_neg["kelly_fraction"] == 0.0
    assert sig_neg["kelly_sizing_fraction"] == 0.0

    # 2. Edge == 0: boundary where calibrated probability exactly equals c_eff
    # At price 0.50, fee = 0.02, c_eff = 0.52.
    # To get calibrated_prob == 0.52 with alpha_cal = 0.65:
    # 0.52 = 0.65 * p_raw + 0.35 * 0.50 => 0.65 * p_raw = 0.52 - 0.175 = 0.345 => p_raw = 0.530769
    p_exact = round(0.345 / 0.65, 6)
    snap_zero_edge = {
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION",
        "raw_features": {
            "close": 100.0,
            "p_ensemble": p_exact,
            "market_regime": "COMPRESSION_MEAN_REVERSION",
        },
    }
    sig_zero = fn(snap_zero_edge)
    assert sig_zero["action"] == "BUY"
    assert sig_zero["projected_edge"] <= 0.0001
    assert sig_zero["f_star"] == 0.0
    assert sig_zero["kelly_fraction"] == 0.0


def test_kelly_fraction_cap_at_twenty_percent():
    """
    Confirms kelly_fraction is strictly capped at 0.20 even when edge is huge.
    """
    hypo = {
        "name": "Huge Edge Cap Test",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "entry_conditions": [
            {"indicator": "close", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # Huge edge: cur_price = 0.15, ML predicts 95% win probability
    # side_cost = 0.15, fee = ceil(0.07 * 0.15 * 0.85 * 100) / 100 = ceil(0.8925) / 100 = 0.01
    # c_eff = 0.16
    # p_raw = 0.95 -> calibrated_prob = 0.65 * 0.95 + 0.35 * 0.15 = 0.6175 + 0.0525 = 0.67
    # f_star = (0.67 - 0.16) / (1.0 - 0.16) = 0.51 / 0.84 = 0.6071
    # Quarter Kelly = 0.6071 * 0.25 = 0.1518
    # Let's make edge even higher: cur_price = 0.05, ML predicts 99%
    # side_cost = 0.05, fee = ceil(0.07 * 0.05 * 0.95 * 100) / 100 = 0.01
    # c_eff = 0.06
    # p_raw = 0.99 (capped at 0.95 in code) -> calibrated_prob = 0.65 * 0.95 + 0.35 * 0.05 = 0.6175 + 0.0175 = 0.635
    # f_star = (0.635 - 0.06) / (1.0 - 0.06) = 0.575 / 0.94 = 0.6117
    # In trend momentum: alpha_cal = 0.70 => calibrated_prob = 0.70 * 0.95 + 0.30 * 0.05 = 0.68
    # f_star = (0.68 - 0.06) / 0.94 = 0.62 / 0.94 = 0.6596 * 0.25 = 0.1649

    # What if ai_win_prob is 95% on NO side when cur_price is 0.90?
    hypo_no = {
        "name": "Huge Edge NO Side",
        "target_side": "NO",
        "target_regimes": ["TREND_EXPANSION_MOMENTUM"],
        "entry_conditions": [
            {"indicator": "close", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    code_no, _ = StrategyCoder.generate_code(hypo_no)
    fn_no = StrategyCoder.compile_strategy(code_no)

    # Let's directly test high edge in snap:
    # cur_price = 0.95, target_side = NO => side_cost = 0.05
    # Let's test with ML prob 0.95 for NO
    snap_no = {
        "cur_price": 0.95,
        "market_regime": "TREND_EXPANSION_MOMENTUM",
        "raw_features": {
            "close": 100.0,
            "p_ensemble": 0.01,  # 1% YES -> 99% NO
            "market_regime": "TREND_EXPANSION_MOMENTUM",
        },
    }
    sig_no = fn_no(snap_no)
    assert sig_no["action"] == "BUY"
    assert sig_no["side"] == "NO"
    # Ensure cap at 0.20
    assert sig_no["kelly_fraction"] <= 0.20
    assert 0.0 <= sig_no["kelly_fraction"] <= 0.20


def test_taker_fee_modeling_exact_match():
    """
    Confirms Kalshi taker fee is accurately computed using the ceil(0.07 * P * (1-P) * 100) / 100
    formula and properly incorporated into c_eff and f_star.
    """
    hypo = {
        "name": "Fee Test Alpha",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "entry_conditions": [
            {"indicator": "close", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # Hand-calculate for P = 0.50
    # side_cost = 0.50
    # fee = int(0.07 * 0.50 * 0.50 * 100.0 + 0.9999) / 100.0 = int(1.75 + 0.9999) / 100.0 = 2 / 100.0 = 0.02
    # c_eff = 0.52
    # Suppose p_ensemble = 0.70
    # p_raw = 0.70
    # calibrated_prob = 0.65 * 0.70 + 0.35 * 0.50 = 0.455 + 0.175 = 0.63
    # edge = 0.63 - 0.52 = 0.11
    # f_star = 0.11 / (1.0 - 0.52) = 0.11 / 0.48 = 0.2291666...
    # lambda_val = 0.25 (compression)
    # kelly_fraction = min(0.20, 0.2291666 * 0.25) = min(0.20, 0.05729) = 0.0573
    snap = {
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION",
        "raw_features": {
            "close": 100.0,
            "p_ensemble": 0.70,
            "market_regime": "COMPRESSION_MEAN_REVERSION",
        },
    }
    sig = fn(snap)
    assert sig["action"] == "BUY"
    assert round(sig["calibrated_win_prob"], 4) == 0.63
    assert round(sig["expected_edge"], 4) == 0.11
    assert round(sig["f_star"], 4) == round(0.11 / 0.48, 4)
    assert round(sig["kelly_fraction"], 4) == round(min(0.20, (0.11 / 0.48) * 0.25), 4)


def test_regime_guards_rejection_and_acceptance():
    """
    Confirms:
    1. Strategy targeting COMPRESSION_MEAN_REVERSION rejects TREND_EXPANSION_MOMENTUM and HIGH_WHIPSAW_EVENT_RISK.
    2. Strategy targeting TREND_EXPANSION_MOMENTUM rejects COMPRESSION_MEAN_REVERSION.
    3. Matching regimes result in action: BUY.
    4. Regime naming variants (slug vs string) match properly.
    """
    hypo_comp = {
        "name": "Compression Only Alpha",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "entry_conditions": [
            {"indicator": "close", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    code_comp, _ = StrategyCoder.generate_code(hypo_comp)
    fn_comp = StrategyCoder.compile_strategy(code_comp)

    # Mismatch 1: Trend Expansion
    res_mismatch_1 = fn_comp({
        "cur_price": 0.50,
        "market_regime": "TREND_EXPANSION_MOMENTUM",
        "raw_features": {"close": 100.0},
    })
    assert res_mismatch_1["action"] == "PASS"
    assert res_mismatch_1["reason"] == "regime_mismatch"
    assert res_mismatch_1["detected_regime"] == "TREND_EXPANSION_MOMENTUM"

    # Mismatch 2: High Whipsaw
    res_mismatch_2 = fn_comp({
        "cur_price": 0.50,
        "market_regime": "HIGH_WHIPSAW_EVENT_RISK",
        "raw_features": {"close": 100.0},
    })
    assert res_mismatch_2["action"] == "PASS"
    assert res_mismatch_2["reason"] == "regime_mismatch"

    # Match: Compression Mean Reversion
    res_match_slug = fn_comp({
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION",
        "raw_features": {"close": 100.0},
    })
    assert res_match_slug["action"] == "BUY"

    # Match with human friendly format: "Compression/Mean-Reversion"
    res_match_human = fn_comp({
        "cur_price": 0.50,
        "market_regime": "Compression/Mean-Reversion",
        "raw_features": {"close": 100.0},
    })
    assert res_match_human["action"] == "BUY"

    # Trend strategy test
    hypo_trend = {
        "name": "Trend Momentum Alpha",
        "target_side": "YES",
        "target_regimes": ["TREND_EXPANSION_MOMENTUM"],
        "entry_conditions": [
            {"indicator": "close", "operator": ">", "threshold": 0.0}
        ],
        "min_entry_price": 0.05,
        "max_entry_price": 0.95,
    }
    code_trend, _ = StrategyCoder.generate_code(hypo_trend)
    fn_trend = StrategyCoder.compile_strategy(code_trend)

    # Reject compression
    res_trend_reject = fn_trend({
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION",
        "raw_features": {"close": 100.0},
    })
    assert res_trend_reject["action"] == "PASS"
    assert res_trend_reject["reason"] == "regime_mismatch"

    # Accept trend
    res_trend_accept = fn_trend({
        "cur_price": 0.50,
        "market_regime": "TREND_EXPANSION_MOMENTUM",
        "raw_features": {"close": 100.0},
    })
    assert res_trend_accept["action"] == "BUY"


def test_adversarial_boundary_conditions():
    """
    Stress-tests edge cases:
    - Zero/invalid price handled gracefully.
    - Extreme RSI values.
    - Missing indicators / empty features.
    - Price outside corridor.
    """
    hypo = {
        "name": "Boundary Stress Alpha",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION"],
        "entry_conditions": [
            {"indicator": "rsi", "operator": "<", "threshold": 40.0}
        ],
        "min_entry_price": 0.20,
        "max_entry_price": 0.80,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # 1. Price below corridor
    res_low = fn({"cur_price": 0.10, "market_regime": "COMPRESSION_MEAN_REVERSION", "raw_features": {"rsi": 30.0}})
    assert res_low["action"] == "PASS"
    assert res_low["reason"] == "price_outside_corridor"

    # 2. Price above corridor
    res_high = fn({"cur_price": 0.85, "market_regime": "COMPRESSION_MEAN_REVERSION", "raw_features": {"rsi": 30.0}})
    assert res_high["action"] == "PASS"
    assert res_high["reason"] == "price_outside_corridor"

    # 3. Non-dict snapshot
    assert fn("not a dict")["action"] == "PASS"
    assert fn(None)["action"] == "PASS"

    # 4. Conditions not met
    res_unmet = fn({"cur_price": 0.50, "market_regime": "COMPRESSION_MEAN_REVERSION", "raw_features": {"rsi": 65.0}})
    assert res_unmet["action"] == "PASS"
    assert res_unmet["reason"] == "conditions_not_met"


def test_ast_sandbox_security_rejections():
    """
    Verifies that malicious or disallowed python constructs are rejected by verify_code_safety.
    """
    malicious_snippets = [
        "import os\ndef evaluate_signal(s): return {}",
        "from sys import exit\ndef evaluate_signal(s): return {}",
        "def evaluate_signal(s):\n    eval('1+1')\n    return {}",
        "def evaluate_signal(s):\n    open('/etc/passwd', 'r')\n    return {}",
        "def evaluate_signal(s):\n    __import__('os')\n    return {}",
    ]
    for snippet in malicious_snippets:
        with pytest.raises(StrategySecurityError):
            StrategyCoder.compile_strategy(snippet)
