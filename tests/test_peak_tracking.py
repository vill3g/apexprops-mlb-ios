"""The settler must remember each trade's highest bid across passes (max_seen_bid).

Regression: the peak defaulted to the current bid on every pass, so a price that rose and then fell
was forgotten, and trailing stops measured from the current price instead of the real peak."""
import uuid
from unittest.mock import patch

import backend.database.models as models
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


def _open(user_id, entry):
    trade = {"id": f"t_{uuid.uuid4().hex[:10]}", "ticker": ETH_TICKER, "side": "YES", "direction": "YES",
             "entry_price": entry, "count": 5, "status": "OPEN", "mode": "PAPER", "pnl": 0.0,
             "timestamp": "2026-09-28T10:00:00-04:00"}
    TradeStore.insert_trade(user_id, trade)
    return trade


def _pass(user, bid):
    get, _ = _fake_get_market({"KXETH15M": _market(ETH_TICKER, yes_bid=bid, yes_ask=bid + 0.02),
                               "KXBTC15M": _market(BTC_TICKER)})
    with patch.object(settler, "get_kalshi_15m_market", side_effect=get), \
         patch.object(settler, "get_all_active_users", return_value=[user]), \
         patch.object(settler, "_fresh_quote", return_value=None), \
         patch.object(settler, "credit_user_paper_balance"):
        settler.settle_saas_trades(blocking=True)


def test_peak_survives_a_price_drop_between_passes():
    # No take-profit or stop-loss fires in this range, so the trade stays open across passes.
    # A real user row is needed: trades of users missing from the users table are closed as orphans first.
    uid = models.create_user(f"peak_tracker_{uuid.uuid4().hex[:6]}", "pw-hash")
    user = {"id": uid, "username": "peak_tracker", "trading_mode": "PAPER", "ai_enabled": 1,
            "stop_loss_pct": 50.0, "take_profit_pct": 80.0, "trailing_stop_enabled": 0,
            "second_entry_enabled": 0}
    trade = _open(user["id"], entry=0.40)
    try:
        _pass(user, bid=0.50)   # +25%: new peak
        _pass(user, bid=0.46)   # pulled back; the peak must still be 0.50
        stored = TradeStore.get_trade_by_id(trade["id"])
        assert stored is not None
        assert abs(float(stored.get("max_seen_bid", 0)) - 0.50) < 1e-9
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})
