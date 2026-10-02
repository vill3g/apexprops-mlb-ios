"""Regression tests for audit finding H3: the SaaS settler only ever fetched the BTC market,
so ETH trades never matched "the current market" - their stop-loss, take-profit and trailing
stop never fired and they could only settle at expiry."""
import uuid
from unittest.mock import patch

import backend.saas_settler as settler
from backend.database.trade_store import TradeStore

ETH_TICKER = "KXETH15M-26SEP281015-15"
BTC_TICKER = "KXBTC15M-26SEP281015-15"


def _market(ticker, **quotes):
    m = {"ticker": ticker, "status": "active", "yes_bid": 0.50, "yes_ask": 0.52,
         "no_bid": 0.46, "no_ask": 0.48}
    m.update(quotes)
    return m


def _fake_get_market(markets):
    calls = []

    def _get(series_ticker="KXBTC15M", **kwargs):
        calls.append(series_ticker)
        return markets.get(series_ticker)
    return _get, calls


def test_series_of():
    assert settler._series_of(ETH_TICKER) == "KXETH15M"
    assert settler._series_of(BTC_TICKER) == "KXBTC15M"
    assert settler._series_of("KXBTC15M_SYNTH") == ""
    assert settler._series_of("KXNFLGAME-XYZ") == ""
    assert settler._series_of(None) == ""


def test_market_for_ticker_fetches_the_trades_own_series_once_per_pass():
    get, calls = _fake_get_market({"KXETH15M": _market(ETH_TICKER), "KXBTC15M": _market(BTC_TICKER)})
    cache = {}
    with patch.object(settler, "get_kalshi_15m_market", side_effect=get):
        assert settler._market_for_ticker(ETH_TICKER, cache)["ticker"] == ETH_TICKER
        assert settler._market_for_ticker(ETH_TICKER, cache)["ticker"] == ETH_TICKER
        assert settler._market_for_ticker(BTC_TICKER, cache)["ticker"] == BTC_TICKER
        assert settler._market_for_ticker("KXNFLGAME-XYZ", cache) is None
    assert calls == ["KXETH15M", "KXBTC15M"]


def _open_trade(user_id, ticker, entry=0.40, side="YES"):
    trade = {"id": f"t_{uuid.uuid4().hex[:10]}", "ticker": ticker, "side": side, "direction": side,
             "entry_price": entry, "count": 5, "status": "OPEN", "mode": "PAPER", "pnl": 0.0,
             "timestamp": "2026-09-28T10:00:00-04:00"}
    TradeStore.insert_trade(user_id, trade)
    return trade


def test_fast_exit_check_sees_an_eth_take_profit():
    user = {"id": 7701, "username": "eth_tp", "stop_loss_pct": 50.0, "take_profit_pct": 20.0}
    trade = _open_trade(user["id"], ETH_TICKER, entry=0.40)
    get, calls = _fake_get_market({
        "KXETH15M": _market(ETH_TICKER, yes_bid=0.60, yes_ask=0.62),  # +50% on the bid
        "KXBTC15M": _market(BTC_TICKER),
    })
    try:
        with patch.object(settler, "get_kalshi_15m_market", side_effect=get), \
             patch.object(settler, "get_all_active_users", return_value=[user]), \
             patch.object(settler, "settle_saas_trades") as settle:
            hits = settler.fast_exit_check()
        assert hits >= 1
        assert "KXETH15M" in calls
        settle.assert_called_once()
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})


def test_fast_exit_check_ignores_an_eth_trade_that_has_not_hit_a_trigger():
    user = {"id": 7702, "username": "eth_hold", "stop_loss_pct": 50.0, "take_profit_pct": 50.0}
    trade = _open_trade(user["id"], ETH_TICKER, entry=0.50)
    get, _ = _fake_get_market({"KXETH15M": _market(ETH_TICKER, yes_bid=0.52, yes_ask=0.54),
                               "KXBTC15M": _market(BTC_TICKER)})
    try:
        with patch.object(settler, "get_kalshi_15m_market", side_effect=get), \
             patch.object(settler, "get_all_active_users", return_value=[user]), \
             patch.object(settler, "settle_saas_trades") as settle:
            hits = settler.fast_exit_check()
        # Other tests' leftover OPEN rows belong to other users, so only this user matters.
        assert settle.call_count == (1 if hits else 0)
        assert hits == 0
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})


def test_settlement_pass_takes_profit_on_an_eth_trade():
    """End to end through the real settlement pass: an ETH PAPER trade up well past the
    user's take-profit is sold, instead of being left to ride to expiry."""
    import backend.database.models as models
    uid = models.create_user(f"eth_tp_pass_{uuid.uuid4().hex[:6]}", "pw-hash")
    user = {"id": uid, "username": "eth_tp_pass", "trading_mode": "PAPER", "ai_enabled": 1,
            "stop_loss_pct": 50.0, "take_profit_pct": 20.0, "trailing_stop_enabled": 0,
            "second_entry_enabled": 0}
    trade = _open_trade(uid, ETH_TICKER, entry=0.40)
    get, _ = _fake_get_market({"KXETH15M": _market(ETH_TICKER, yes_bid=0.60, yes_ask=0.62),
                               "KXBTC15M": _market(BTC_TICKER)})
    fresh = {"success": True, "ticker": ETH_TICKER, "yes_bid": 0.60, "no_bid": 0.38}
    with patch.object(settler, "get_kalshi_15m_market", side_effect=get), \
         patch.object(settler, "get_all_active_users", return_value=[user]), \
         patch.object(settler, "_fresh_quote", return_value=fresh), \
         patch.object(settler, "credit_user_paper_balance") as credit:
        settler.settle_saas_trades(blocking=True)

    stored = TradeStore.get_trade_by_id(trade["id"])
    assert str(stored["status"]).upper() == "CLOSED"
    assert "TAKE_PROFIT" in str(stored.get("exit_reason") or stored.get("reason"))
    assert float(stored["exit_price"]) == 0.60
    credit.assert_called_once()
