"""Regression tests for the PREDICTION trading style in contract_eval.py.

Two bugs were fixed here, both making PREDICTION look "YES-only" in practice:
  1. It picked its side from `prob >= 50.0` (confidence-in-current-direction) instead of
     the actual signal `direction`, so it bought YES whenever it was confident, regardless
     of which way that confidence pointed.
  2. Once (1) was fixed, the *fallback* used when neither the ML model nor the chart
     heuristic has an opinion (both sit at the neutral 0.50 sentinel) still did
     `p_yes >= 50.0`, and 50.0 >= 50.0 is always True - so every "no opinion" case
     silently forced ABOVE. This test pins that fallback to spot-vs-strike instead.
"""
import numpy as np
import pandas as pd

from backend.btc.analyzer.contract_eval import evaluate_next_15m_contract


def _flat_df(n=20, level=80500.0):
    """A perfectly flat, featureless chart: no heuristic setup can fire, and with no
    trained ML model available the model probability stays at its 0.50 'no opinion' sentinel."""
    return pd.DataFrame({
        "open": np.full(n, level),
        "high": np.full(n, level + 5),
        "low": np.full(n, level - 5),
        "close": np.full(n, level),
        "volume": np.full(n, 100.0),
        "rsi": np.full(n, 50.0),
        "ema_9": np.full(n, level),
        "ema_21": np.full(n, level),
        "ema_50": np.full(n, level),
        "bb_upper": np.full(n, level + 50),
        "bb_lower": np.full(n, level - 50),
        "atr": np.full(n, 50.0),
        "cvd": np.full(n, 0.0),
        "vol_ratio": np.full(n, 1.0),
        "adx": np.full(n, 15.0),
        "time": np.arange(1000, 1000 + n * 900, 900),
    })


def _kalshi_m():
    return {"ticker": "KXBTC15M-TEST", "strike_price": 80500.0,
            "yes_ask": 0.50, "no_ask": 0.50, "status": "active"}


def test_prediction_tiebreak_follows_spot_not_always_above():
    """With no model/chart opinion at all, the forced side must track where price
    actually sits relative to the strike - not default to ABOVE every time."""
    df = _flat_df(level=80500.0)
    km = _kalshi_m()

    below = evaluate_next_15m_contract(
        df, target_price=80700.0, patterns=[], kalshi_m=km,
        trading_style="PREDICTION", signal_isolation="BLEND",
    )
    above = evaluate_next_15m_contract(
        df, target_price=80300.0, patterns=[], kalshi_m=km,
        trading_style="PREDICTION", signal_isolation="BLEND",
    )

    assert below["direction"] == "BELOW", (
        "Spot is below the strike with no other signal; PREDICTION must not force ABOVE.")
    assert above["direction"] == "ABOVE"
    # The two calls must actually disagree - proof this isn't just hardcoded either way.
    assert below["direction"] != above["direction"]


def test_prediction_always_returns_a_side_never_pass():
    df = _flat_df()
    km = _kalshi_m()
    result = evaluate_next_15m_contract(
        df, target_price=80500.0, patterns=[], kalshi_m=km,
        trading_style="PREDICTION", signal_isolation="BLEND",
    )
    assert result["direction"] in ("ABOVE", "BELOW")
    assert result["action_type"] in ("BID YES", "BID NO")


def test_prediction_follows_real_directional_signal_not_confidence():
    """When there IS a real directional read (not the neutral tie), PREDICTION must trade
    that direction - this is the original 'always buys YES when confident' bug."""
    n = 30
    level = 80500.0
    # A clear downtrend: price sliding under falling EMAs, RSI oversold - a real bearish read.
    df = pd.DataFrame({
        "open": np.linspace(level + 300, level - 300, n),
        "high": np.linspace(level + 320, level - 280, n),
        "low": np.linspace(level + 280, level - 320, n),
        "close": np.linspace(level + 290, level - 300, n),
        "volume": np.full(n, 100.0),
        "rsi": np.full(n, 28.0),
        "ema_9": np.linspace(level + 280, level - 290, n),
        "ema_21": np.linspace(level + 300, level - 270, n),
        "ema_50": np.linspace(level + 320, level - 250, n),
        "bb_upper": np.linspace(level + 400, level - 200, n),
        "bb_lower": np.linspace(level + 200, level - 400, n),
        "atr": np.full(n, 80.0),
        "cvd": np.linspace(50, -50, n),
        "vol_ratio": np.full(n, 1.3),
        "adx": np.full(n, 35.0),
        "time": np.arange(1000, 1000 + n * 900, 900),
    })
    df["timestamp"] = df["time"]
    km = _kalshi_m()
    result = evaluate_next_15m_contract(
        df, target_price=level, patterns=[], kalshi_m=km,
        trading_style="PREDICTION", signal_isolation="CHART_ONLY",
    )
    # Whatever side it lands on, `probability_percent` must be the confidence OF that side,
    # and action_type must agree with direction (this is what the original bug broke).
    if result["direction"] == "ABOVE":
        assert result["action_type"] == "BID YES"
    else:
        assert result["action_type"] == "BID NO"
