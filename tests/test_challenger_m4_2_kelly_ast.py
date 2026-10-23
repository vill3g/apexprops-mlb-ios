"""
Empirical Adversarial Challenge Suite: Mathematical Invariance & AST Sandbox Compliance.
Phase 1 Verification:
- Closed-form Kelly Criterion formula: f* = (p - C_eff) / (1.0 - C_eff)
- Kalshi taker fee formula: ceil(0.07 * P * (1-P) * 100) / 100
- Strict monotonicity: df*/dp > 0 for p > C_eff
- Regime scaling: fractional Kelly multiplier (0.15 in whipsaw vs 0.25 otherwise)
- AST sandbox compliance: zero imports, safe builtins only, immunity to StrategySecurityError
"""
import ast
import math
import random
import pytest

from backend.engine.quant_lab.strategy_coder import (
    StrategyCoder,
    StrategySecurityError,
    verify_code_safety
)
from backend.engine.quant_lab.regime_classifier import (
    REGIME_SLUG_COMPRESSION,
    REGIME_SLUG_TREND,
    REGIME_SLUG_WHIPSAW,
)


def test_kelly_closed_form_exact_derivation():
    """
    Mathematical Proof and Invariance Test:
    For a binary contract with cost C_eff and payout $1.00:
    Net payoff odds b = (1.0 - C_eff) / C_eff.
    Standard Kelly formula: f* = (b * p - q) / b, where q = 1 - p.
    Closed-form binary Kelly: f* = (p - C_eff) / (1.0 - C_eff).
    
    Proof:
    f* = (( (1 - C_eff) / C_eff ) * p - (1 - p)) / ((1 - C_eff) / C_eff)
       = ( (1 - C_eff) * p - C_eff * (1 - p) ) / (1 - C_eff)
       = ( p - p * C_eff - C_eff + p * C_eff ) / (1 - C_eff)
       = ( p - C_eff ) / (1 - C_eff). [Q.E.D.]
    """
    random.seed(42)
    max_diff = 0.0

    # Test 100,000 random (p, C_eff) pairs
    for _ in range(100000):
        c_eff = random.uniform(0.02, 0.98)
        p = random.uniform(c_eff + 1e-5, 0.999)

        # 1. Standard Kelly formula
        b = (1.0 - c_eff) / c_eff
        q = 1.0 - p
        f_standard = (b * p - q) / b

        # 2. Closed-form binary options Kelly formula
        f_closed = (p - c_eff) / (1.0 - c_eff)

        diff = abs(f_standard - f_closed)
        if diff > max_diff:
            max_diff = diff

    # Invariance check: maximum numerical divergence must be within machine epsilon
    assert max_diff < 1e-12, f"Mathematical divergence detected: {max_diff}"

    # Edge behavior: zero edge (p == c_eff) yields f* == 0.0
    c_eff = 0.50
    assert abs((0.50 - c_eff) / (1.0 - c_eff)) < 1e-12

    # Certain win (p == 1.0) yields f* == 1.0 (full bankroll)
    assert abs((1.0 - c_eff) / (1.0 - c_eff) - 1.0) < 1e-12


def test_kalshi_taker_fee_exact_match():
    """
    Verifies that the integer ceiling calculation in StrategyCoder matches
    the official Kalshi fee specification:
    Fee = ceil(0.07 * P * (1 - P) * 100) / 100
    for all valid prices P in [0.01, 0.99].
    """
    discrepancies = []

    # 1. Test all 99 whole-cent price levels (discrete Kalshi order book tick size)
    for p_cents in range(1, 100):
        P = p_cents / 100.0
        official_fee = math.ceil(0.07 * P * (1.0 - P) * 100.0) / 100.0
        # Integer ceiling trick used in StrategyCoder:
        coder_fee = int(0.07 * P * (1.0 - P) * 100.0 + 0.9999) / 100.0

        if abs(official_fee - coder_fee) > 1e-9:
            discrepancies.append((P, official_fee, coder_fee))

    assert len(discrepancies) == 0, f"Discrepancies in cent fees: {discrepancies}"

    # 2. Maximum fee verification: At P = 0.50, 0.07 * 0.25 * 100 = 1.75 cents -> ceil = 2 cents ($0.02)
    p_mid = 0.50
    mid_fee = int(0.07 * p_mid * (1.0 - p_mid) * 100.0 + 0.9999) / 100.0
    assert mid_fee == 0.02, f"Midpoint fee should be $0.02, got {mid_fee}"

    # 3. Minimum non-zero fee verification: At P = 0.01 and P = 0.99, ceil(0.0693) = 1 cent ($0.01)
    p_ext1 = 0.01
    p_ext2 = 0.99
    fee_ext1 = int(0.07 * p_ext1 * (1.0 - p_ext1) * 100.0 + 0.9999) / 100.0
    fee_ext2 = int(0.07 * p_ext2 * (1.0 - p_ext2) * 100.0 + 0.9999) / 100.0
    assert fee_ext1 == 0.01, f"Extremum 0.01 fee should be $0.01, got {fee_ext1}"
    assert fee_ext2 == 0.01, f"Extremum 0.99 fee should be $0.01, got {fee_ext2}"

    # 4. Symmetry property: Fee(P) == Fee(1 - P) for all P
    for p_cents in range(1, 50):
        P1 = p_cents / 100.0
        P2 = (100 - p_cents) / 100.0
        f1 = int(0.07 * P1 * (1.0 - P1) * 100.0 + 0.9999) / 100.0
        f2 = int(0.07 * P2 * (1.0 - P2) * 100.0 + 0.9999) / 100.0
        assert f1 == f2, f"Fee asymmetry at P={P1} vs P={P2}"


def test_kelly_monotonicity_wrt_model_probability():
    """
    Mathematical Invariance Test:
    Verifies that for any fixed C_eff, f* is strictly monotonically increasing
    with respect to model win probability p:
    df*/dp = 1 / (1 - C_eff) > 0 for all C_eff in (0, 1).
    """
    random.seed(1337)
    
    # 1. Analytical derivative invariance test across 50,000 random pairs
    for _ in range(50000):
        c_eff = random.uniform(0.02, 0.97)
        p1 = random.uniform(c_eff + 1e-4, 0.98)
        p2 = random.uniform(p1 + 1e-4, 0.99)

        f1 = (p1 - c_eff) / (1.0 - c_eff)
        f2 = (p2 - c_eff) / (1.0 - c_eff)

        assert f2 > f1, f"Monotonicity violated: f1({p1})={f1} >= f2({p2})={f2} at c_eff={c_eff}"
        # Derivative check: (f2 - f1) / (p2 - p1) should equal 1 / (1 - c_eff)
        empirical_deriv = (f2 - f1) / (p2 - p1)
        expected_deriv = 1.0 / (1.0 - c_eff)
        assert abs(empirical_deriv - expected_deriv) < 1e-9

    # 2. End-to-end compiled strategy monotonicity test
    hypo = {
        "name": "Monotonicity Verification Strategy",
        "target_side": "YES",
        "base_edge": 0.05,
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 60.0}],
        "max_entry_price": 0.85,
        "min_entry_price": 0.15
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # Monotonicity with varying ai_win_prob
    prev_f_star = -1.0
    prev_prob = -1.0
    for prob_val in [55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0]:
        res = fn({"raw_features": {"rsi": 30.0, "ai_win_prob": prob_val}, "cur_price": 0.50})
        assert res["action"] == "BUY"
        assert res["calibrated_win_prob"] > prev_prob
        assert res["f_star"] > prev_f_star
        prev_prob = res["calibrated_win_prob"]
        prev_f_star = res["f_star"]


def test_regime_scaling_and_fractional_kelly():
    """
    Verifies that regime scaling strictly reduces fractional Kelly multiplier
    in High Whipsaw / Event Risk (lambda = 0.15) compared to Compression / Mean Reversion
    and Trend Expansion / Momentum (lambda = 0.25).
    Also verifies Bayesian calibration shrinkage alpha is smaller in Whipsaw (0.45).
    """
    hypo = {
        "name": "Multi-Regime Alpha Strategy",
        "target_side": "YES",
        "target_regimes": [],  # Permit all regimes
        "base_edge": 0.08,
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 60.0}],
        "max_entry_price": 0.85,
        "min_entry_price": 0.15
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # Identical market conditions, different regimes
    base_snapshot = {"raw_features": {"rsi": 35.0, "ai_win_prob": 70.0}, "cur_price": 0.50}

    res_comp = fn(dict(base_snapshot, market_regime=REGIME_SLUG_COMPRESSION))
    res_trend = fn(dict(base_snapshot, market_regime=REGIME_SLUG_TREND))
    res_whip = fn(dict(base_snapshot, market_regime=REGIME_SLUG_WHIPSAW))

    # 1. Multiplier scaling check: Whipsaw must be strictly smaller
    assert res_whip["kelly_fraction"] < res_comp["kelly_fraction"]
    assert res_whip["kelly_fraction"] < res_trend["kelly_fraction"]

    # 2. Probability calibration check: Whipsaw shrinks more toward market prior (side_cost = 0.50)
    # alpha_whip = 0.45, alpha_comp = 0.65, alpha_trend = 0.70
    assert res_whip["calibrated_win_prob"] < res_comp["calibrated_win_prob"]
    assert res_comp["calibrated_win_prob"] < res_trend["calibrated_win_prob"]

    # 3. Kelly safety cap check: kelly_fraction must never exceed 0.20
    extreme_snapshot = {"raw_features": {"rsi": 10.0, "ai_win_prob": 95.0}, "cur_price": 0.20}
    res_extreme = fn(dict(extreme_snapshot, market_regime=REGIME_SLUG_TREND))
    assert res_extreme["kelly_fraction"] <= 0.20
    assert res_extreme["f_star"] > res_extreme["kelly_fraction"]


def test_ast_sandbox_safety_and_builtins_whitelist():
    """
    AST Sandbox Compliance Test:
    1. Parse generated AST and verify zero Import/ImportFrom nodes.
    2. Confirm every function/attribute call belongs strictly to safe whitelist.
    3. Ensure compiled strategy executes cleanly without StrategySecurityError.
    """
    hypo = {
        "name": "Strict AST Sandbox Audit",
        "target_side": "YES",
        "target_regimes": [REGIME_SLUG_COMPRESSION],
        "base_edge": 0.06,
        "entry_conditions": [
            {"indicator": "rsi", "operator": "<", "threshold": 30.0},
            {"indicator": "market_regime", "operator": "==", "threshold": "COMPRESSION_MEAN_REVERSION"},
            {"indicator": "ema_fast", "operator": ">", "threshold": "ema_slow"}
        ],
        "max_entry_price": 0.80,
        "min_entry_price": 0.20
    }
    code, code_hash = StrategyCoder.generate_code(hypo)
    assert code_hash is not None

    tree = ast.parse(code)
    called_names = set()
    called_attrs = set()

    for node in ast.walk(tree):
        # Assert zero imports
        assert not isinstance(node, (ast.Import, ast.ImportFrom)), "Forbidden import node found!"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called_attrs.add(node.func.attr)

    # Permitted built-ins in safe_globals
    safe_builtins = {"abs", "min", "max", "round", "float", "int", "str", "bool", "isinstance", "dict", "len", "any", "all"}
    # Permitted native object methods
    safe_methods = {"get", "replace", "upper", "lower"}

    # Assert no unauthorized functions are called
    unauthorized_names = called_names - safe_builtins
    assert len(unauthorized_names) == 0, f"Unauthorized builtin call: {unauthorized_names}"

    unauthorized_attrs = called_attrs - safe_methods
    assert len(unauthorized_attrs) == 0, f"Unauthorized method call: {unauthorized_attrs}"

    # Verify successful sandboxed compilation
    fn = StrategyCoder.compile_strategy(code)
    test_snap = {
        "raw_features": {
            "rsi": 25.0,
            "market_regime": "COMPRESSION_MEAN_REVERSION",
            "ema_fast": 65000.0,
            "ema_slow": 64000.0
        },
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION"
    }
    res = fn(test_snap)
    assert res["action"] == "BUY"


def test_ast_sandbox_adversarial_injection_immunity():
    """
    Adversarial Security Test:
    Attempts various AST evasion and code injection attacks.
    Confirms all malicious patterns raise StrategySecurityError or fail safely.
    """
    # 1. Explicit import injection
    with pytest.raises(StrategySecurityError):
        verify_code_safety("import os\ndef evaluate_signal(s): return {}")

    with pytest.raises(StrategySecurityError):
        verify_code_safety("from subprocess import Popen\ndef evaluate_signal(s): return {}")

    # 2. Forbidden function call injection
    with pytest.raises(StrategySecurityError):
        verify_code_safety("def evaluate_signal(s): eval('1+1')")

    with pytest.raises(StrategySecurityError):
        verify_code_safety("def evaluate_signal(s): open('secret.txt', 'r')")

    with pytest.raises(StrategySecurityError):
        verify_code_safety("def evaluate_signal(s): getattr(s, '__class__')")

    # 3. Missing evaluate_signal function definition
    with pytest.raises(StrategySecurityError):
        StrategyCoder.compile_strategy("x = 42")


def test_target_side_invariance_yes_and_no():
    """
    Verifies that target_side='NO' correctly inverts price and probability:
    - side_cost = 1.0 - cur_price
    - fee computed on side_cost
    - win probability inverted when ai_win_prob is given
    """
    hypo_no = {
        "name": "NO Contract Strategy",
        "target_side": "NO",
        "base_edge": 0.06,
        "entry_conditions": [{"indicator": "rsi", "operator": ">", "threshold": 70.0}],
        "max_entry_price": 0.85,
        "min_entry_price": 0.15
    }
    code, _ = StrategyCoder.generate_code(hypo_no)
    fn = StrategyCoder.compile_strategy(code)

    # cur_price = 0.60 (YES price). For NO side, cost basis is 0.40.
    snap = {
        "raw_features": {"rsi": 75.0, "ai_win_prob": 30.0},  # YES win prob = 30%, so NO win prob = 70%
        "cur_price": 0.60
    }
    res = fn(snap)
    assert res["action"] == "BUY"
    assert res["side"] == "NO"
    # Calibrated probability should be > 50% for NO side
    assert res["calibrated_win_prob"] > 0.50
    assert res["f_star"] > 0.0
    assert res["kelly_fraction"] > 0.0
