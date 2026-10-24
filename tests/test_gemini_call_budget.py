"""Gemini is paid per call: one market must cost one decision, not one call per evaluation.

Regression: in Every-Interval force mode the decision cache treated an answer as stale after 195s,
so every evaluation late in the 15-minute window called Gemini again (about 100 calls an hour)."""
import time
from unittest.mock import patch

import pytest

from backend.btc import gemini_15m_gate as gate

TICKER = "KXBTC15M-26OCT231945-45"


@pytest.fixture
def cached_yes():
    key = ("BTC", TICKER, False)
    decision = {"direction": "YES", "confidence": 70.0, "reason": "cached", "model": "gemini-test",
                "timestamp": time.time() - 60, "decision": "EXECUTE"}
    with gate._CACHE_LOCK:
        gate._MASTER_CACHE[key] = decision
    yield key
    with gate._CACHE_LOCK:
        gate._MASTER_CACHE.pop(key, None)


def test_force_mode_reuses_same_market_decision_late_in_window(cached_yes):
    with patch("backend.btc.dual_model_debate.run_dual_model_debate") as debate:
        for _ in range(5):
            res = gate.get_or_create_master_decision(
                "BTC", TICKER, strike=67000.0, spot=67100.0, sec_elapsed=400.0,
                active_m={}, forecast={}, df_ind=None, allow_pass=False)
            assert res["direction"] == "YES"
        debate.assert_not_called()


def test_pass_mode_still_treats_old_decision_as_stale_after_195s():
    decision = {"direction": "YES", "timestamp": time.time() - 60}
    assert gate._is_cached_decision_valid(decision, 100.0, True) is True
    assert gate._is_cached_decision_valid(decision, 400.0, True) is False


def test_force_mode_expires_decisions_after_max_age():
    decision = {"direction": "NO", "timestamp": time.time() - gate.MAX_DECISION_AGE_SEC - 1}
    assert gate._is_cached_decision_valid(decision, 400.0, False) is False
