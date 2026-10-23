import time
import pytest
from backend.sports_bridge.executor import (
    _is_event_within_start_window,
    _candidate_priority_key,
    MAX_FUTURE_START_WINDOW_SECONDS
)

def test_within_4h_horizon_accepted():
    now_ts = time.time()
    # Event starting in 2.5 hours
    cand = {"start_epoch": now_ts + (2.5 * 3600), "ticker": "KXTEST-2.5H"}
    ok, reason = _is_event_within_start_window(cand, now_ts, max_future_seconds=MAX_FUTURE_START_WINDOW_SECONDS, allow_live=False)
    assert ok is True
    assert "within 4h window" in reason

def test_outside_4h_horizon_rejected():
    now_ts = time.time()
    # Event starting in 5 hours
    cand = {"start_epoch": now_ts + (5.0 * 3600), "ticker": "KXTEST-5H"}
    ok, reason = _is_event_within_start_window(cand, now_ts, max_future_seconds=MAX_FUTURE_START_WINDOW_SECONDS, allow_live=False)
    assert ok is False
    assert "auto-trade horizon limit" in reason

def test_tomorrow_night_game_rejected():
    now_ts = time.time()
    # Event scheduled for tomorrow night (22 hours away)
    cand = {"start_epoch": now_ts + (22.0 * 3600), "ticker": "KXTEST-22H"}
    ok, reason = _is_event_within_start_window(cand, now_ts, max_future_seconds=MAX_FUTURE_START_WINDOW_SECONDS, allow_live=False)
    assert ok is False
    assert "auto-trade horizon limit" in reason

def test_live_event_filtering():
    now_ts = time.time()
    # Event started 45 minutes ago
    cand = {"start_epoch": now_ts - (45 * 60), "ticker": "KXTEST-LIVE", "is_live": False}
    # When allow_live is False
    ok_no_live, reason_no_live = _is_event_within_start_window(cand, now_ts, allow_live=False)
    assert ok_no_live is False

    # When allow_live is True
    ok_live, reason_live = _is_event_within_start_window(cand, now_ts, allow_live=True)
    assert ok_live is True
    assert "Live in-progress event" in reason_live

def test_concluded_past_event_rejected():
    now_ts = time.time()
    # Event started 6 hours ago
    cand = {"start_epoch": now_ts - (6 * 3600), "ticker": "KXTEST-PAST"}
    ok, reason = _is_event_within_start_window(cand, now_ts, allow_live=True)
    assert ok is False
    assert "Concluded" in reason

def test_unknown_start_time_rejected():
    now_ts = time.time()
    cand = {"ticker": "KXUNKNOWN-START"}
    ok, reason = _is_event_within_start_window(cand, now_ts, allow_live=True)
    assert ok is False
    assert "Unknown start time" in reason

def test_candidate_priority_sorting():
    now_ts = time.time()
    c_sooner = {"start_epoch": now_ts + 1800, "ticker": "SOONER", "confidence_pct": 60.0}
    c_later = {"start_epoch": now_ts + 10800, "ticker": "LATER", "confidence_pct": 75.0}
    c_tomorrow = {"start_epoch": now_ts + 86400, "ticker": "TOMORROW", "confidence_pct": 80.0}

    k_sooner = _candidate_priority_key(c_sooner)
    k_later = _candidate_priority_key(c_later)
    k_tomorrow = _candidate_priority_key(c_tomorrow)

    # Both sooner and later must be Tier 0 (within 4h)
    assert k_sooner[0] == 0
    assert k_later[0] == 0
    # Tomorrow must be Tier 1 (outside 4h)
    assert k_tomorrow[0] == 1

    # Sooner must sort before later within Tier 0
    cands = [c_later, c_tomorrow, c_sooner]
    cands.sort(key=_candidate_priority_key)
    assert cands[0]["ticker"] == "SOONER"
    assert cands[1]["ticker"] == "LATER"
    assert cands[2]["ticker"] == "TOMORROW"
