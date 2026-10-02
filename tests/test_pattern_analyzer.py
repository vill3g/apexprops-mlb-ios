"""Unit tests for backend.btc.pattern_analyzer - the advisory up/down pattern watcher."""
import importlib
import sys
import time

import pytest


@pytest.fixture(autouse=True)
def _fresh_module():
    """Each test gets a clean module (its own in-process cache)."""
    sys.modules.pop("backend.btc.pattern_analyzer", None)
    mod = importlib.import_module("backend.btc.pattern_analyzer")
    yield mod
    sys.modules.pop("backend.btc.pattern_analyzer", None)


def _seq(results, start=0, step=900):
    """Build a fake [(epoch, result, ticker), ...] sequence, oldest first."""
    out = []
    for i, r in enumerate(results):
        epoch = start + i * step
        out.append((epoch, r, f"KXBTC15M-FAKE{i:04d}"))
    return out


def test_no_signal_on_thin_history(_fresh_module):
    mod = _fresh_module
    seq = _seq(["YES", "NO"] * 5)  # only 10 samples, well under every threshold
    assert mod._streak_signal(seq) is None
    assert mod._alternation_signal(seq) is None
    assert mod._time_of_day_signal(seq) is None


def test_streak_continuation_detected(_fresh_module):
    mod = _fresh_module
    # Build history where 3 YES in a row are followed by another YES ~85% of the time.
    results = []
    import random
    random.seed(7)
    for _ in range(200):
        if len(results) >= 3 and results[-3:] == ["YES", "YES", "YES"]:
            results.append("YES" if random.random() < 0.85 else "NO")
        else:
            results.append(random.choice(["YES", "NO"]))
    # End on a fresh 3-YES streak so the "current" streak matches what we trained.
    if results[-3:] != ["YES", "YES", "YES"]:
        results += ["NO", "YES", "YES", "YES"]
    seq = _seq(results)
    sig = mod._streak_signal(seq)
    assert sig is not None
    assert sig["kind"] == "STREAK"
    assert sig["direction"] == "ABOVE"  # continuation of a YES streak
    assert sig["sample_size"] >= mod.MIN_STREAK_SAMPLES


def test_alternation_detected(_fresh_module):
    mod = _fresh_module
    # Pure zig-zag history: alternation should be recognized as continuing.
    results = ["YES" if i % 2 == 0 else "NO" for i in range(80)]
    seq = _seq(results)
    sig = mod._alternation_signal(seq)
    assert sig is not None
    assert sig["kind"] == "ALTERNATION"
    # last was results[-1]; expected_next flips it
    expected_next = "NO" if results[-1] == "YES" else "YES"
    assert sig["direction"] == ("ABOVE" if expected_next == "YES" else "BELOW")


def test_nudge_is_capped_and_advisory_only(_fresh_module):
    mod = _fresh_module

    def fake_pooled_sequence(asset, limit=None):
        results = []
        import random
        random.seed(3)
        for _ in range(200):
            if len(results) >= 4 and results[-4:] == ["YES"] * 4:
                results.append("YES" if random.random() < 0.95 else "NO")
            else:
                results.append(random.choice(["YES", "NO"]))
        results[-4:] = ["YES"] * 4
        return _seq(results)

    mod._pooled_sequence = fake_pooled_sequence
    signal = mod.get_pattern_signal("BTC")
    if signal["has_signal"]:
        assert abs(signal["nudge"]) <= mod.MAX_NUDGE
        assert signal["direction"] in ("ABOVE", "BELOW")
        assert "description" in signal


def test_cache_hits_avoid_recompute(_fresh_module, monkeypatch):
    mod = _fresh_module
    calls = {"n": 0}

    def fake_pooled_sequence(asset, limit=None):
        calls["n"] += 1
        return []

    mod._pooled_sequence = fake_pooled_sequence
    mod.get_pattern_signal("BTC")
    mod.get_pattern_signal("BTC")
    assert calls["n"] == 1  # second call served from cache


def test_empty_history_returns_no_signal(_fresh_module):
    mod = _fresh_module
    mod._pooled_sequence = lambda asset, limit=None: []
    signal = mod.get_pattern_signal("ETH")
    assert signal == {"has_signal": False}
