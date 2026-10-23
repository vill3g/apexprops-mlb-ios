"""Head Trader Dossier card: dossier summary, call log scoring, and the live-dossier API."""
import os

os.environ.setdefault("IN_PROCESS_WORKER", "0")   # never start the trading worker from tests

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.btc.gemini_panel as gp
from backend.btc import gemini_15m_gate as gate
from backend.main import app

client = TestClient(app)

SAMPLE_DOSSIER = {
    "contract": {"ticker": "KXBTC15M-26OCT231945-45", "strike_price": 67240.5, "current_spot_price": 67312.2,
                 "spot_minus_strike": 71.7, "is_outside_deadzone": True},
    "kalshi_orderbook": {"yes_ask": 0.62, "yes_bid": 0.60, "no_ask": 0.40, "no_bid": 0.38},
    "opening_1m_micro_trend": {"trajectory": "BULLISH_HIGHER_LOWS_DRIVE"},
    "kalshi_microstructure_l2_oi_twap": {
        "twap_60s_strike_dislocation": {"opening_twap_regime": "BULLISH_YES_HEADSTART"},
        "level2_orderbook_depth": {"l2_book_imbalance_minus1_to_plus1": 0.31},
        "contract_1m_candlesticks_and_open_interest": {"oi_conviction_regime": "FRESH_BEARISH_NO_OI_BUILDUP"},
    },
    "live_kalshi_tape_and_whale_flow": {"tape_orderflow_verdict": "STRONG_YES_WHALE_SWEEP"},
    "cvd_orderflow_delta": {"cvd_trend": "BULLISH_CVD"},
    "price_action_and_indicators": {"indicators": {"rsi": 58.2, "bb_pct_b": 0.71, "trend_1h": "BEARISH"}},
    "perp_liquidations_and_funding": {"funding_rate_bias": "EXTREME_LONG_CROWDED (Longs paying high premium)",
                                      "short_squeeze_risk": "LOW"},
    "cross_asset_macro_beta_flow": {"macro_risk_sentiment": "SELECTIVE_ROTATION / MIXED"},
    "macro_economic_event_horizon": {"minutes_to_nearest_event": 22.0, "nearest_event_name": "CPI",
                                     "volatility_freeze_recommended": False},
    "synthetic_60s_settlement_lock": {"math_locked_outcome": "UNRESOLVED"},
    "recent_loss_regime_warnings": [{"reason": "Loss Guard Veto: 2 recent losses in tight range chop."}],
    "local_ai_models": {"ml_ensemble_prob_above_strike_pct": 64.0, "local_technical_gate_direction": "YES",
                        "voting_ensemble_consensus": {"consensus_direction": "NO", "agreement_ratio": 0.6}},
}


@pytest.fixture
def call_log(tmp_path, monkeypatch):
    """An empty, isolated call log; results come from the `results` dict."""
    monkeypatch.setattr(gp, "_path", lambda: str(tmp_path / "gemini_calls.json"))
    monkeypatch.setattr(gp, "_calls", None)
    results = {}
    with patch("backend.btc.market_results.get_result", side_effect=lambda t, trade=None: results.get(t)):
        yield results


@pytest.mark.parametrize("price,fee", [(0.62, 0.02), (0.50, 0.02), (0.01, 0.01), (0.95, 0.01), (0.0, 0.0), (1.0, 0.0)])
def test_kalshi_taker_fee(price, fee):
    assert gp.kalshi_taker_fee(price) == fee


def test_panel_summary_signals_and_tones():
    p = gp.panel_summary(SAMPLE_DOSSIER)
    tones = {s["name"]: s["tone"] for s in p["signals"]}
    assert tones["Opening 1m structure"] == "bull"
    assert tones["TWAP head start"] == "bull"
    assert tones["L2 book imbalance"] == "bull"
    assert tones["Whale tape"] == "bull"
    assert tones["Open interest"] == "bear"
    assert tones["RSI / BB %b"] == "neut"
    assert tones["1h trend"] == "bear"
    assert tones["Perp funding"] == "bear"          # crowded longs = downside risk
    assert tones["Macro beta"] == "neut"
    assert p["quotes_at_call"]["yes_ask"] == 0.62
    assert p["models"]["voting_direction"] == "NO"


def test_panel_summary_warnings_only_when_active():
    texts = [w["text"] for w in gp.panel_summary(SAMPLE_DOSSIER)["warnings"]]
    assert any("CPI in 22 min" in t for t in texts)
    assert any("tight range chop" in t for t in texts)
    assert not any("locked" in t.lower() for t in texts)

    calm = dict(SAMPLE_DOSSIER, macro_economic_event_horizon={"minutes_to_nearest_event": 999.0},
                recent_loss_regime_warnings=[])
    assert gp.panel_summary(calm)["warnings"] == []


def test_panel_summary_never_raises_on_bad_input():
    assert isinstance(gp.panel_summary({}), dict)
    assert isinstance(gp.panel_summary({"contract": "garbage", "local_ai_models": None}), dict)


def test_call_log_keeps_one_call_per_market(call_log):
    gp.record_call("BTC", "KXBTC15M-26OCT231945-45", "YES", 70)
    gp.record_call("BTC", "KXBTC15M-26OCT231945-45", "NO", 81)
    gp.record_call("BTC", "KXBTC15M-X_SYNTH", "YES", 90)        # synthetic markets are ignored
    assert [(c["direction"], c["confidence"]) for c in gp._load()] == [("NO", 81.0)]


def test_call_stats_band_win_rate_and_recent(call_log):
    # 12 scored calls at 75-80%: 7 won.  Plus one unsettled and one PASS (both ignored).
    for i in range(12):
        t = f"KXBTC15M-26OCT23{i:04d}-00"
        gp.record_call("BTC", t, "YES", 77)
        call_log[t] = "YES" if i < 7 else "NO"
    gp.record_call("BTC", "KXBTC15M-UNSETTLED", "YES", 77)
    gp.record_call("BTC", "KXBTC15M-PASSED", "PASS", 77)

    s = gp.call_stats("BTC", 78.0)
    assert s["band"] == {"low": 75.0, "high": 80.0, "n": 12, "wins": 7, "win_rate": round(7 / 12, 3)}
    assert len(s["recent"]) == 12 and s["recent_wins"] == 7

    # Another band with too few samples reports no win rate rather than a noisy one.
    assert gp.call_stats("BTC", 91.0)["band"]["win_rate"] is None
    assert gp.call_stats("ETH", 78.0)["recent"] == []


def test_live_dossier_api_returns_card_fields(call_log):
    for i in range(10):
        t = f"KXBTC15M-26OCT22{i:04d}-00"
        gp.record_call("BTC", t, "YES", 78)
        call_log[t] = "YES" if i < 6 else "NO"            # 60% historical win rate

    key = ("BTC", "KXBTC15M-26OCT231945-45", False)
    decision = {"direction": "YES", "confidence": 78.0, "reason": "test", "model": "gemini-test",
                "timestamp": time.time(), "panel": gp.panel_summary(SAMPLE_DOSSIER)}
    with gate._CACHE_LOCK:
        gate._MASTER_CACHE[key] = decision
    try:
        with patch("backend.engine.kalshi_market_cache.get_market_cache_instance") as cache:
            cache.return_value.get_market.return_value = None      # fall back to quotes at call time
            d = client.get("/api/engine/BTC/gemini/live-dossier").json()
    finally:
        with gate._CACHE_LOCK:
            gate._MASTER_CACHE.pop(key, None)

    assert d["has_decision"] and d["direction"] == "YES"
    assert d["ticker"] == "KXBTC15M-26OCT231945-45"
    assert d["quotes_live"] is False
    t = d["trade"]
    assert t["side"] == "YES" and t["ask"] == 0.62 and t["fee"] == 0.02 and t["break_even"] == 0.64
    assert t["calibrated_win_rate"] == 0.6
    assert t["edge"] == pytest.approx(-0.04)
    assert d["recent_wins"] == 6 and len(d["recent_calls"]) == 10
    assert len(d["signals"]) == 10


def test_with_panel_attaches_summary_and_records(call_log):
    res = gate._with_panel({"direction": "NO", "confidence": 66}, SAMPLE_DOSSIER, "BTC", "KXBTC15M-26OCT232000-00")
    assert res["panel"]["ticker"] == "KXBTC15M-26OCT231945-45"
    assert gp._load()[-1]["direction"] == "NO"
