"""
Adversarial Stress-Testing Suite for Quant Lab Phase 1.
Challenger: challenger_1
Target modules:
- backend.engine.quant_lab.regime_classifier (MarketRegimeClassifier)
- backend.engine.quant_lab.strategy_coder (StrategyCoder, verify_code_safety)
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
)
from backend.engine.quant_lab.strategy_coder import (
    StrategyCoder,
    StrategySecurityError,
    verify_code_safety,
    FORBIDDEN_CALLS,
)


# ==============================================================================
# 1. MarketRegimeClassifier Adversarial Edge Case Suite
# ==============================================================================

def test_regime_none_empty_and_degenerate_snapshots():
    """Verify MarketRegimeClassifier handles None, empty, and degenerate types with zero exceptions."""
    degenerate_inputs = [
        None,
        {},
        {"raw_features": None},
        {"raw_features": {}},
        {"indicators": None},
        {"indicators": {}},
        {"raw_features": "not_a_dict"},
        {"raw_features": [1, 2, 3]},
        {"indicators": 12345},
        [],
        "unexpected_string",
        12345,
        3.14159,
        True,
    ]

    for item in degenerate_inputs:
        # 1. classify_snapshot
        res_snap = MarketRegimeClassifier.classify_snapshot(item, asset="BTC")
        assert isinstance(res_snap, dict), f"Failed dict output for input: {item}"
        assert res_snap["market_regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
        assert res_snap["regime_code"] in (0, 1, 2)
        assert res_snap["regime_slug"] in (REGIME_SLUG_COMPRESSION, REGIME_SLUG_TREND, REGIME_SLUG_WHIPSAW)
        assert isinstance(res_snap["regime_metrics"], dict)

        # 2. sports asset snapshot
        res_sport = MarketRegimeClassifier.classify_snapshot(item, asset="TEN")
        assert isinstance(res_sport, dict)
        assert res_sport["market_regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
        assert res_sport["regime_code"] in (0, 1, 2)

        # 3. classify_market_state directly
        res_state = MarketRegimeClassifier.classify_market_state(item, asset="BTC")
        assert isinstance(res_state, dict)
        assert res_state["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
        assert res_state["regime_code"] in (0, 1, 2)


def test_regime_sparse_and_asymmetric_feature_keys():
    """Verify classifier resilience when only 1 or 2 arbitrary keys are present."""
    sparse_cases = [
        {"adx": 30.0},
        {"close": 68000.0},
        {"open": 68000.0},
        {"high": 68500.0},
        {"low": 67500.0},
        {"atr_percentile": 88.0},
        {"vol_regime_percentile": 0.45},
        {"ema_fast": 68000.0},
        {"ema_slow": 67000.0},
        {"ema_trend": 66000.0},
        {"vol_ratio": 2.5},
        {"body_to_range": 0.8},
        {"upper_wick_ratio": 0.4},
        {"lower_wick_ratio": 0.4},
        {"spread": 0.04},
        {"price_drift": -0.05},
        {"ai_edge": 6.0},
        {"market_mid": 0.55},
        {"unknown_random_metric_123": 999.99},
    ]

    for feats in sparse_cases:
        # Financial
        res_fin = MarketRegimeClassifier.classify_market_state(feats, asset="BTC")
        assert res_fin["regime_code"] in (0, 1, 2)
        assert isinstance(res_fin["metrics"], dict)

        # Sports
        res_sp = MarketRegimeClassifier.classify_market_state(feats, asset="NHL")
        assert res_sp["regime_code"] in (0, 1, 2)
        assert isinstance(res_sp["metrics"], dict)


def test_regime_nan_and_inf_mathematical_resilience():
    """Verify that NaNs, positive/negative Infs, and unparseable strings are safely sanitized."""
    nan = float("nan")
    inf = float("inf")
    ninf = float("-inf")

    pathological_financial = {
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
        "cur_price": "NOT_A_NUMBER",
        "price": "NaN",
    }

    res_fin = MarketRegimeClassifier.classify_market_state(pathological_financial, asset="BTC")
    assert res_fin["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
    assert res_fin["regime_code"] in (0, 1, 2)
    # Ensure all metric outputs are finite
    for k, v in res_fin["metrics"].items():
        if isinstance(v, (int, float)):
            assert not math.isnan(v), f"Metric {k} was NaN!"
            assert not math.isinf(v), f"Metric {k} was Inf!"

    pathological_sports = {
        "spread": nan,
        "price_drift": inf,
        "ai_edge": ninf,
        "market_mid": "INVALID_MID",
    }
    res_sp = MarketRegimeClassifier.classify_market_state(pathological_sports, asset="TEN")
    assert res_sp["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
    for k, v in res_sp["metrics"].items():
        if isinstance(v, (int, float)):
            assert not math.isnan(v), f"Sports metric {k} was NaN!"
            assert not math.isinf(v), f"Sports metric {k} was Inf!"


def test_regime_doji_and_degenerate_candle_dynamics():
    """Verify edge-case candles: zero range, inverted range (high < low), negative prices."""
    # 1. Perfectly flat zero-range doji
    doji_flat = {"high": 65000.0, "low": 65000.0, "open": 65000.0, "close": 65000.0}
    res_flat = MarketRegimeClassifier.classify_market_state(doji_flat, asset="BTC")
    assert res_flat["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)
    assert res_flat["metrics"]["body_to_range"] >= 0.0

    # 2. Inverted candle (high < low)
    inverted = {"high": 50000.0, "low": 60000.0, "open": 55000.0, "close": 52000.0}
    res_inv = MarketRegimeClassifier.classify_market_state(inverted, asset="BTC")
    assert res_inv["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)

    # 3. Negative prices
    negative = {"high": -10.0, "low": -50.0, "open": -20.0, "close": -30.0}
    res_neg = MarketRegimeClassifier.classify_market_state(negative, asset="BTC")
    assert res_neg["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)

    # 4. Zero prices
    zeros = {"high": 0.0, "low": 0.0, "open": 0.0, "close": 0.0}
    res_zero = MarketRegimeClassifier.classify_market_state(zeros, asset="BTC")
    assert res_zero["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)

    # 5. Extreme wick doji (open == close in the middle of a massive range)
    wick_doji = {
        "high": 100.0, "low": 0.0, "open": 50.0, "close": 50.0,
        "vol_regime_percentile": 0.90, "vol_ratio": 1.5
    }
    res_wick = MarketRegimeClassifier.classify_market_state(wick_doji, asset="BTC")
    # Body is 0.0, wicks are 0.5 each -> total wick 1.0 -> should classify as WHIPSAW
    assert res_wick["regime"] == REGIME_WHIPSAW
    assert res_wick["regime_code"] == 2


def test_regime_extreme_volatility_spikes():
    """Verify 99.9th percentile volatility spikes and high volume surges."""
    # 99.9th percentile as float [0, 1]
    res_999_dec = MarketRegimeClassifier.classify_market_state(
        {"vol_regime_percentile": 0.999}, asset="BTC"
    )
    assert res_999_dec["regime"] == REGIME_WHIPSAW
    assert res_999_dec["regime_code"] == 2

    # 99.9th percentile as percentage [0, 100]
    res_999_pct = MarketRegimeClassifier.classify_market_state(
        {"vol_regime_percentile": 99.9}, asset="BTC"
    )
    assert res_999_pct["regime"] == REGIME_WHIPSAW

    # Extreme ATR percentile
    res_atr_99 = MarketRegimeClassifier.classify_market_state(
        {"atr_percentile": 99.5}, asset="BTC"
    )
    assert res_atr_99["regime"] == REGIME_WHIPSAW

    # Extreme volume ratio surge (vol_ratio >= 1.7 with small body)
    res_vol_surge = MarketRegimeClassifier.classify_market_state(
        {"vol_ratio": 5.0, "body_to_range": 0.15, "vol_regime_percentile": 0.50}, asset="BTC"
    )
    assert res_vol_surge["regime"] == REGIME_WHIPSAW


def test_regime_sports_extreme_spread_and_drift():
    """Verify sports prediction regime transitions under extreme spreads and price drifts."""
    # 1. Extreme wide spread ($0.15 on $1 contract) -> HIGH_WHIPSAW
    res_wide_spread = MarketRegimeClassifier.classify_market_state(
        {"spread": 0.15, "price_drift": 0.01}, asset="TEN"
    )
    assert res_wide_spread["regime"] == REGIME_WHIPSAW
    assert res_wide_spread["regime_slug"] == REGIME_SLUG_WHIPSAW

    # 2. Extreme sports drift ($0.25) with moderate spread ($0.06) -> HIGH_WHIPSAW (chaotic repricing)
    res_chaotic_drift = MarketRegimeClassifier.classify_market_state(
        {"spread": 0.06, "price_drift": 0.25}, asset="SOC"
    )
    assert res_chaotic_drift["regime"] == REGIME_WHIPSAW

    # 3. Extreme sports drift ($0.25) with tight spread ($0.02) -> TREND_EXPANSION (strong liquid trend)
    res_liquid_trend = MarketRegimeClassifier.classify_market_state(
        {"spread": 0.02, "price_drift": 0.25}, asset="MLB"
    )
    assert res_liquid_trend["regime"] == REGIME_TREND
    assert res_liquid_trend["regime_code"] == 1

    # 4. Extreme negative drift (-$0.25) with tight spread ($0.03) -> TREND_EXPANSION
    res_neg_drift = MarketRegimeClassifier.classify_market_state(
        {"spread": 0.03, "price_drift": -0.25}, asset="UFC"
    )
    assert res_neg_drift["regime"] == REGIME_TREND

    # 5. Out of bounds values: negative spread and mid > 1.0
    res_oob = MarketRegimeClassifier.classify_market_state(
        {"spread": -0.05, "market_mid": 1.5, "price_drift": 0.0}, asset="NFL"
    )
    assert res_oob["regime"] in (REGIME_COMPRESSION, REGIME_TREND, REGIME_WHIPSAW)


def test_regime_snapshot_inplace_enrichment_integrity():
    """Verify classify_snapshot properly enriches top-level, raw_features, and indicators in place."""
    snap = {
        "ticker": "KXBTCD-26OCT13-T65000",
        "cur_price": 0.52,
        "raw_features": {
            "adx": 35.0,
            "atr_percentile": 60.0,
            "body_to_range": 0.75,
            "vol_ratio": 1.3,
            "ema_fast": 65500.0,
            "ema_slow": 65200.0,
            "ema_trend": 64900.0
        },
        "indicators": {
            "rsi": 62.0
        }
    }

    out = MarketRegimeClassifier.classify_snapshot(snap, asset="BTC")
    assert out is snap  # Enriched in place
    assert out["market_regime"] == REGIME_TREND
    assert out["regime_code"] == 1
    assert out["regime_slug"] == REGIME_SLUG_TREND

    # Inner raw_features enriched
    assert out["raw_features"]["market_regime"] == REGIME_TREND
    assert out["raw_features"]["regime_code"] == 1

    # Inner indicators enriched
    assert out["indicators"]["market_regime"] == REGIME_TREND
    assert out["indicators"]["regime_code"] == 1


# ==============================================================================
# 2. StrategyCoder AST Sandbox Security & Attack Matrix
# ==============================================================================

def test_ast_sandbox_blocks_all_malicious_imports():
    """Verify that every attempted explicit import is strictly blocked by verify_code_safety."""
    malicious_import_payloads = [
        "import os",
        "import sys",
        "import subprocess",
        "import socket",
        "import shutil",
        "import builtins",
        "import ctypes",
        "import http.client",
        "import urllib.request",
        "import requests",
        "import tempfile",
        "import threading",
        "import multiprocessing",
        "import pickle",
        "import base64",
        "from os import system",
        "from subprocess import Popen, call, check_output",
        "from importlib import import_module",
        "from pathlib import Path",
        "from posixpath import join",
        "from builtins import eval, exec, open",
        "from sys import modules, exit",
        "import os as my_os",
        "from os import system as s",
        "import sys\nimport os\n",
    ]

    for payload in malicious_import_payloads:
        # 1. Directly in verify_code_safety
        with pytest.raises(StrategySecurityError, match="Explicit imports are disallowed"):
            verify_code_safety(payload)

        # 2. Wrapped in a function definition
        code_wrapper = f"def evaluate_signal(snapshot):\n    {payload}\n    return {{'action': 'BUY'}}"
        with pytest.raises(StrategySecurityError, match="Explicit imports are disallowed"):
            verify_code_safety(code_wrapper)

        # 3. Via StrategyCoder.compile_strategy
        with pytest.raises(StrategySecurityError):
            StrategyCoder.compile_strategy(code_wrapper)


def test_ast_sandbox_blocks_all_forbidden_calls():
    """Verify all forbidden functions and attribute calls are blocked by verify_code_safety."""
    forbidden_calls_list = [
        "eval('1+1')",
        "exec('a = 1')",
        "compile('a = 1', '', 'exec')",
        "open('some_file.txt', 'w')",
        "__import__('os')",
        "input('enter pin:')",
        "globals()",
        "locals()",
        "getattr(obj, 'attr')",
        "setattr(obj, 'attr', 1)",
        "delattr(obj, 'attr')",
        "subprocess()",
        "os()",
        "sys()",
        "socket()",
        "urllib()",
        "requests()",
        # Attribute calls
        "my_obj.eval()",
        "my_obj.exec()",
        "my_obj.compile()",
        "my_obj.open()",
        "my_obj.getattr()",
        "my_obj.subprocess()",
        "my_obj.os()",
        "my_obj.sys()",
    ]

    for payload in forbidden_calls_list:
        code = f"def evaluate_signal(snapshot):\n    {payload}\n    return {{'action': 'PASS'}}"
        with pytest.raises(StrategySecurityError, match="Prohibited (function|attribute) call"):
            verify_code_safety(code)

        with pytest.raises(StrategySecurityError):
            StrategyCoder.compile_strategy(code)


def test_ast_sandbox_runtime_environment_isolation():
    """Verify runtime sandbox execution environment contains only safe whitelisted builtins."""
    # Attempting to call non-whitelisted builtins directly in compiled code
    dangerous_runtime_attempts = [
        "def evaluate_signal(snapshot):\n    f = open('test', 'r')\n    return {'action': 'PASS'}",
        "def evaluate_signal(snapshot):\n    __import__('os')\n    return {'action': 'PASS'}",
        "def evaluate_signal(snapshot):\n    eval('2+2')\n    return {'action': 'PASS'}",
    ]
    for code in dangerous_runtime_attempts:
        with pytest.raises(StrategySecurityError):
            StrategyCoder.compile_strategy(code)

    # Valid harmless code compiles and executes safely
    safe_code = """
def evaluate_signal(snapshot):
    # Safe allowed builtins test
    v = abs(-5.5)
    mn = min(1, 2)
    mx = max(1, 2)
    r = round(3.14159, 2)
    flt = float(4)
    i = int(4.5)
    s = str(123)
    b = bool(1)
    is_d = isinstance({}, dict)
    d = dict(a=1)
    l = len([1, 2, 3])
    a_ok = any([True, False])
    all_ok = all([True, True])
    return {"action": "BUY", "result": v + mn + mx + r + flt + i + l}
"""
    fn = StrategyCoder.compile_strategy(safe_code)
    out = fn({})
    assert out["action"] == "BUY"
    assert out["result"] > 0


def test_hypothesis_adversarial_injection_attempts():
    """Verify that malicious code strings injected into hypothesis fields cannot escape sandbox."""
    # 1. Malicious name with code injection
    hypo_malicious_name = {
        "name": "ExploitStrat\ndef evaluate_signal(snap):\n    import os\n#",
        "target_side": "YES",
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 30.0}],
    }
    with pytest.raises(StrategySecurityError):
        code, _ = StrategyCoder.generate_code(hypo_malicious_name)
        StrategyCoder.compile_strategy(code)

    # 2. Malicious condition threshold with code injection
    hypo_malicious_thresh = {
        "name": "ExploitThresh",
        "target_side": "YES",
        "entry_conditions": [
            {"indicator": "rsi", "operator": "<", "threshold": "__import__('os')"}
        ],
    }
    # When threshold contains non-numeric strings, it's treated as a string literal comparison or feature lookup
    code_thresh, _ = StrategyCoder.generate_code(hypo_malicious_thresh)
    # verify_code_safety must block if it executes prohibited calls or compile_strategy safely runs it as string comparison
    fn_thresh = StrategyCoder.compile_strategy(code_thresh)
    # Execution must not crash or execute code
    res = fn_thresh({"raw_features": {"rsi": 25.0}, "cur_price": 0.50})
    assert res["action"] in ("BUY", "PASS")

    # 3. Syntax error in code
    syntax_error_code = "def evaluate_signal(snapshot): return {{{"
    with pytest.raises(StrategySecurityError, match="Syntax error"):
        verify_code_safety(syntax_error_code)


# ==============================================================================
# 3. Dynamic Kelly & Calibrated Win Probability Edge Cases
# ==============================================================================

def test_dynamic_kelly_and_win_prob_boundary_conditions():
    """Verify dynamic Kelly sizing and calibrated win probability under boundary conditions."""
    hypo = {
        "name": "Boundary Test Alpha",
        "target_side": "YES",
        "target_regimes": ["COMPRESSION_MEAN_REVERSION", "HIGH_WHIPSAW_EVENT_RISK"],
        "base_edge": 0.08,
        "entry_conditions": [
            {"indicator": "rsi", "operator": "<", "threshold": 40.0}
        ],
        "max_entry_price": 0.80,
        "min_entry_price": 0.20,
    }
    code, _ = StrategyCoder.generate_code(hypo)
    fn = StrategyCoder.compile_strategy(code)

    # 1. Price below corridor -> PASS
    snap_low_price = {"raw_features": {"rsi": 30.0}, "cur_price": 0.15}
    res_low = fn(snap_low_price)
    assert res_low["action"] == "PASS"
    assert res_low["reason"] == "price_outside_corridor"

    # 2. Price above corridor -> PASS
    snap_high_price = {"raw_features": {"rsi": 30.0}, "cur_price": 0.85}
    res_high = fn(snap_high_price)
    assert res_high["action"] == "PASS"
    assert res_high["reason"] == "price_outside_corridor"

    # 3. Mismatched regime -> PASS
    snap_wrong_reg = {
        "raw_features": {"rsi": 30.0},
        "cur_price": 0.50,
        "market_regime": "TREND_EXPANSION_MOMENTUM"
    }
    res_wrong_reg = fn(snap_wrong_reg)
    assert res_wrong_reg["action"] == "PASS"
    assert res_wrong_reg["reason"] == "regime_mismatch"

    # 4. Matching in COMPRESSION regime (quarter-Kelly lambda = 0.25)
    snap_comp = {
        "raw_features": {"rsi": 30.0},
        "cur_price": 0.50,
        "market_regime": "COMPRESSION_MEAN_REVERSION"
    }
    res_comp = fn(snap_comp)
    assert res_comp["action"] == "BUY"
    assert res_comp["calibrated_win_prob"] > 0.50
    kelly_comp = res_comp["kelly_fraction"]
    assert kelly_comp > 0.0

    # 5. Matching in WHIPSAW regime (reduced fractional Kelly lambda = 0.15)
    snap_whip = {
        "raw_features": {"rsi": 30.0},
        "cur_price": 0.50,
        "market_regime": "HIGH_WHIPSAW_EVENT_RISK"
    }
    res_whip = fn(snap_whip)
    assert res_whip["action"] == "BUY"
    kelly_whip = res_whip["kelly_fraction"]
    # Due to increased shrinkage in whipsaw and lower lambda (0.15 vs 0.25),
    # kelly_fraction in whipsaw must be strictly lower than in compression
    assert kelly_whip < kelly_comp, f"Expected kelly_whip ({kelly_whip}) < kelly_comp ({kelly_comp})"

    # 6. Negative edge (expensive entry price with low base edge) -> f_star == 0, kelly_fraction == 0
    hypo_neg_edge = {
        "name": "Negative Edge Alpha",
        "target_side": "YES",
        "base_edge": -0.20,
        "entry_conditions": [{"indicator": "rsi", "operator": "<", "threshold": 40.0}],
        "max_entry_price": 0.95,
        "min_entry_price": 0.05,
    }
    code_neg, _ = StrategyCoder.generate_code(hypo_neg_edge)
    fn_neg = StrategyCoder.compile_strategy(code_neg)
    res_neg = fn_neg({"raw_features": {"rsi": 30.0}, "cur_price": 0.80})
    assert res_neg["action"] == "BUY"
    assert res_neg["f_star"] == 0.0
    assert res_neg["kelly_fraction"] == 0.0
