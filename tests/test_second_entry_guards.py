"""Regression tests for audit finding H2: second entries (the automatic re-entry after a
profitable take-profit / trailing-stop exit) used the user's CURRENT mode, ignored the AI
switch, and sized on the bare ask with no slippage buffer or fee."""
from backend.btc.fees import kalshi_order_fee
from backend.saas_settler import _second_entry_mode, _second_entry_size

KT = object()  # stands in for a working per-user Kalshi session


def test_paper_trade_after_user_switched_to_live_never_opens_a_live_second_entry():
    user = {"ai_enabled": 1, "trading_mode": "LIVE"}
    assert _second_entry_mode(user, "PAPER", KT) is None


def test_live_trade_after_user_switched_to_paper_is_skipped_too():
    user = {"ai_enabled": 1, "trading_mode": "PAPER"}
    assert _second_entry_mode(user, "LIVE", None) is None


def test_ai_switched_off_blocks_second_entries():
    assert _second_entry_mode({"ai_enabled": 0, "trading_mode": "LIVE"}, "LIVE", KT) is None
    assert _second_entry_mode({"ai_enabled": 0, "trading_mode": "PAPER"}, "PAPER", None) is None


def test_live_second_entry_needs_a_kalshi_session():
    """Previously a LIVE user without a session fell into the PAPER branch (paper deduction
    for a trade recorded as LIVE)."""
    assert _second_entry_mode({"ai_enabled": 1, "trading_mode": "LIVE"}, "LIVE", None) is None


def test_same_mode_with_ai_on_is_allowed():
    assert _second_entry_mode({"ai_enabled": 1, "trading_mode": "LIVE"}, "LIVE", KT) == "LIVE"
    assert _second_entry_mode({"ai_enabled": 1, "trading_mode": "PAPER"}, "paper", None) == "PAPER"


def test_live_sizing_keeps_worst_case_cost_plus_fee_within_trade_size():
    """The audit example: $5 trade size, ask $0.20. The old sizing bought 25 contracts,
    whose worst-case cost (limit $0.24) plus fee was about $6.28."""
    user = {"trade_size_dollars": 5.0}
    n = _second_entry_size(user, "LIVE", 0.20)
    assert n > 0
    worst = n * 0.24 + kalshi_order_fee(0.24, n)
    assert worst <= 5.0
    assert n < 25


def test_paper_sizing_uses_paper_trade_size_and_includes_fee():
    user = {"paper_trade_size_dollars": 50.0, "trade_size_dollars": 5.0}
    n = _second_entry_size(user, "PAPER", 0.40)
    worst = min(0.40 + 0.04 + 0.01, 0.99)
    assert n * worst + kalshi_order_fee(worst, n) <= 50.0
    assert n > 50  # sized off the $50 paper size, not the $5 live size


def test_unaffordable_second_entry_sizes_to_zero():
    assert _second_entry_size({"trade_size_dollars": 0.20}, "LIVE", 0.50) == 0
