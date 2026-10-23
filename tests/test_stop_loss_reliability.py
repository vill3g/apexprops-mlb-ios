"""Stop-loss reliability regression tests.

Root cause of the Oct 22 PAPER NO losses (entries 0.36 / 0.19, stop 65%, min_seen_bid
0.01-0.02, settled at $0): the settler re-confirms every exit with a fresh quote from
kalshi_trader.get_market_quote(), whose WebSocket fast path read ``no_bid`` straight out of
Kalshi's WS ticker message. That feed only carries yes_bid / yes_ask, so every NO quote came
back with no_bid = 0.00 and the stop was skipped as an "empty book" on every pass until expiry.

These tests drive the real settlement pass for PAPER NO and YES trades with a mocked market and
fresh quote (including the fresh quote failing / missing the NO side) and require a STOP_LOSS exit.
"""
import uuid
from unittest.mock import patch

import pytest

import backend.btc.kalshi_trader as kt_mod
import backend.saas_settler as settler
from backend.database.trade_store import TradeStore

BTC_TICKER = "KXBTC15M-26OCT220100-00"
ETH_TICKER = "KXETH15M-26OCT220100-00"


def _market(ticker, yes_bid, yes_ask):
    return {"ticker": ticker, "status": "active",
            "yes_bid": yes_bid, "yes_ask": yes_ask,
            "no_bid": round(1.0 - yes_ask, 4), "no_ask": round(1.0 - yes_bid, 4)}


def _new_user(prefix):
    import backend.database.models as models
    uid = models.create_user(f"{prefix}_{uuid.uuid4().hex[:6]}", "pw-hash")
    return {"id": uid, "username": prefix, "trading_mode": "PAPER", "ai_enabled": 1,
            "stop_loss_enabled": 1, "stop_loss_pct": 65.0,
            "take_profit_enabled": 1, "take_profit_pct": 45.0,
            "trailing_stop_enabled": 1, "trailing_stop_activation_pct": 25.0,
            "trailing_stop_distance_pct": 8.0, "atr_risk_enabled": 0,
            "reentry_after_stop_loss": 0, "second_entry_enabled": 0}


def _open_trade(uid, ticker, side, entry):
    trade = {"id": f"sl_{uuid.uuid4().hex[:10]}", "ticker": ticker, "side": side, "direction": side,
             "entry_price": entry, "count": 47, "status": "OPEN", "mode": "PAPER", "pnl": 0.0,
             # Same ET string format the live trades use; well past the stop grace period.
             "timestamp": "2026-10-22 12:46:50 AM ET"}
    TradeStore.insert_trade(uid, trade)
    return trade


def _run_pass(user, markets, fresh=None, fresh_raises=None, paper_exit=None):
    def _get(series_ticker="KXBTC15M", **kwargs):
        return markets.get(series_ticker)

    def _quote(ticker):
        if fresh_raises is not None:
            raise fresh_raises
        return fresh if fresh is not None else {"success": False, "error": "mock failure"}

    settler.clear_unresolved_settlement_cache()
    settler._skip_log_last.clear()
    with patch.object(settler, "get_kalshi_15m_market", side_effect=_get), \
         patch.object(settler, "get_all_active_users", return_value=[user]), \
         patch.object(kt_mod.kalshi_trader, "get_market_quote", side_effect=_quote), \
         patch.object(kt_mod, "paper_exit_price", side_effect=paper_exit or (lambda tk, sd, c, bid: bid)), \
         patch.object(settler.loss_analyzer, "diagnose_loss", return_value={}), \
         patch.object(settler, "credit_user_paper_balance") as credit:
        settler.settle_saas_trades(blocking=True)
    return credit


def _assert_stopped(trade, max_exit=None):
    stored = TradeStore.get_trade_by_id(trade["id"])
    assert str(stored["status"]).upper() == "CLOSED", stored
    assert "STOP_LOSS" in str(stored.get("exit_reason")), stored
    assert float(stored["exit_price"]) > 0.0
    if max_exit is not None:
        assert float(stored["exit_price"]) <= max_exit
    return stored


# ---------------------------------------------------------------- NO side
def test_paper_no_stop_fires_when_fresh_quote_lacks_no_side():
    """The exact production failure: fresh (WS) quote has only YES fields."""
    user = _new_user("sl_no_ws")
    trade = _open_trade(user["id"], ETH_TICKER, "NO", 0.36)
    # NO bid 0.10 (= 1 - yes_ask 0.90) is -72% vs entry 0.36 -> past the 65% stop.
    markets = {"KXETH15M": _market(ETH_TICKER, 0.89, 0.90)}
    fresh = {"success": True, "ticker": ETH_TICKER, "yes_bid": 0.89, "yes_ask": 0.90,
             "no_bid": 0.0, "no_ask": 0.0, "status": "active"}
    credit = _run_pass(user, markets, fresh=fresh)
    stored = _assert_stopped(trade, max_exit=0.11)
    assert float(stored["exit_price"]) == pytest.approx(0.10, abs=1e-6)
    credit.assert_called_once()


def test_paper_no_stop_falls_back_to_cached_bid_when_fresh_quote_fails(caplog):
    user = _new_user("sl_no_fail")
    trade = _open_trade(user["id"], BTC_TICKER, "NO", 0.19)
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.94, 0.95)}  # NO bid 0.05 (-74%)
    with caplog.at_level("WARNING", logger="backend.saas_settler"):
        _run_pass(user, markets, fresh={"success": False, "error": "HTTP 503"})
    _assert_stopped(trade)
    assert any("fresh quote unavailable" in r.getMessage() for r in caplog.records)


def test_paper_no_stop_survives_fresh_quote_exception():
    """get_market_quote() re-raises 429/5xx; that used to abort the user's whole pass."""
    import requests
    user = _new_user("sl_no_raise")
    trade = _open_trade(user["id"], BTC_TICKER, "NO", 0.19)
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.94, 0.95)}
    _run_pass(user, markets, fresh_raises=requests.exceptions.RequestException("HTTP 429"))
    _assert_stopped(trade)


def test_paper_no_stop_not_aborted_by_low_simulated_exit():
    """A simulated book exit <= $0.03 used to abort the exit ('holding') -> $0 settlement."""
    user = _new_user("sl_no_lowexit")
    trade = _open_trade(user["id"], BTC_TICKER, "NO", 0.19)
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.95, 0.96)}  # NO bid 0.04
    fresh = {"success": True, "ticker": BTC_TICKER, "yes_bid": 0.95, "yes_ask": 0.96,
             "no_bid": 0.04, "no_ask": 0.05}
    _run_pass(user, markets, fresh=fresh, paper_exit=lambda tk, sd, c, bid: 0.02)
    stored = _assert_stopped(trade)
    assert float(stored["exit_price"]) == pytest.approx(0.02)


# ---------------------------------------------------------------- YES side (symmetry)
def test_paper_yes_stop_fires_with_fresh_quote():
    user = _new_user("sl_yes_ok")
    trade = _open_trade(user["id"], ETH_TICKER, "YES", 0.36)
    markets = {"KXETH15M": _market(ETH_TICKER, 0.10, 0.11)}  # YES bid 0.10 (-72%)
    fresh = {"success": True, "ticker": ETH_TICKER, "yes_bid": 0.10, "yes_ask": 0.11,
             "no_bid": 0.89, "no_ask": 0.90}
    _run_pass(user, markets, fresh=fresh)
    _assert_stopped(trade, max_exit=0.11)


def test_paper_yes_stop_falls_back_to_cached_bid_when_fresh_quote_fails():
    user = _new_user("sl_yes_fail")
    trade = _open_trade(user["id"], BTC_TICKER, "YES", 0.36)
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.10, 0.11)}
    _run_pass(user, markets, fresh=None)
    _assert_stopped(trade)


def test_yes_stop_derives_bid_when_quote_only_has_no_side():
    user = _new_user("sl_yes_noside")
    trade = _open_trade(user["id"], ETH_TICKER, "YES", 0.36)
    markets = {"KXETH15M": _market(ETH_TICKER, 0.10, 0.11)}
    fresh = {"success": True, "ticker": ETH_TICKER, "yes_bid": 0.0, "yes_ask": 0.0,
             "no_bid": 0.89, "no_ask": 0.90}
    _run_pass(user, markets, fresh=fresh)
    _assert_stopped(trade, max_exit=0.11)


def test_no_trade_above_stop_is_held():
    user = _new_user("sl_no_hold")
    trade = _open_trade(user["id"], ETH_TICKER, "NO", 0.36)
    markets = {"KXETH15M": _market(ETH_TICKER, 0.66, 0.67)}  # NO bid 0.33 (-8%)
    fresh = {"success": True, "ticker": ETH_TICKER, "yes_bid": 0.66, "yes_ask": 0.67}
    try:
        _run_pass(user, markets, fresh=fresh)
        stored = TradeStore.get_trade_by_id(trade["id"])
        assert str(stored["status"]).upper() == "OPEN"
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})


def test_anti_wick_prevents_premature_shakeout_on_single_bid_drop():
    """A 1-second bid drop (wick) with a resilient ask does NOT trigger stop-loss on the first pass."""
    user = _new_user("sl_anti_wick")
    trade = _open_trade(user["id"], BTC_TICKER, "NO", 0.50)
    # NO bid 0.10 (-80% bid loss vs entry 0.50), NO ask 0.40 -> mid is 0.25 (-50% loss < 65% sl)
    # Market representation: yes_ask = 1 - 0.10 = 0.90, yes_bid = 1 - 0.40 = 0.60
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.60, 0.90)}
    fresh = {"success": True, "ticker": BTC_TICKER, "yes_bid": 0.60, "yes_ask": 0.90,
             "no_bid": 0.10, "no_ask": 0.40}
    try:
        # Pass 1: Observed as a 1-second bid wick; trade must remain OPEN
        _run_pass(user, markets, fresh=fresh)
        stored = TradeStore.get_trade_by_id(trade["id"])
        assert str(stored["status"]).upper() == "OPEN"
        assert int(stored.get("sl_low_bid_count", 0)) == 1

        # Pass 2: Bid rebounds to 0.35 -> low_bid_count resets to 0, trade remains OPEN
        rebound_markets = {"KXBTC15M": _market(BTC_TICKER, 0.60, 0.65)} # no_bid 0.35, no_ask 0.40
        rebound_fresh = {"success": True, "ticker": BTC_TICKER, "yes_bid": 0.60, "yes_ask": 0.65,
                         "no_bid": 0.35, "no_ask": 0.40}
        _run_pass(user, rebound_markets, fresh=rebound_fresh)
        stored_rebound = TradeStore.get_trade_by_id(trade["id"])
        assert str(stored_rebound["status"]).upper() == "OPEN"
        assert int(stored_rebound.get("sl_low_bid_count", 0)) == 0
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})


def test_anti_wick_triggers_when_low_bid_persists():
    """If the low bid persists across consecutive passes, anti-wick confirmation allows stop-loss."""
    user = _new_user("sl_persist")
    trade = _open_trade(user["id"], BTC_TICKER, "NO", 0.50)
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.60, 0.90)}
    fresh = {"success": True, "ticker": BTC_TICKER, "yes_bid": 0.60, "yes_ask": 0.90,
             "no_bid": 0.10, "no_ask": 0.40}
    try:
        # Pass 1: Wick observed, low_bid_count becomes 1, trade stays open
        _run_pass(user, markets, fresh=fresh)
        stored = TradeStore.get_trade_by_id(trade["id"])
        assert str(stored["status"]).upper() == "OPEN"

        # Pass 2: Low bid persists -> low_bid_count becomes 2 -> triggers STOP_LOSS
        _run_pass(user, markets, fresh=fresh)
        _assert_stopped(trade)
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})


def test_anti_wick_resets_counter_on_fresh_quote_recovery():
    """If cached market triggers stop exit on pass 2, but fresh quote shows market rebounded, trade is held and counter is reset to 0."""
    user = _new_user("sl_fresh_rebound")
    trade = _open_trade(user["id"], BTC_TICKER, "NO", 0.50)
    markets = {"KXBTC15M": _market(BTC_TICKER, 0.60, 0.90)}
    wick_fresh = {"success": True, "ticker": BTC_TICKER, "yes_bid": 0.60, "yes_ask": 0.90,
                  "no_bid": 0.10, "no_ask": 0.40}
    try:
        # Pass 1: Wick observed, low_bid_count becomes 1, trade stays open
        _run_pass(user, markets, fresh=wick_fresh)
        stored = TradeStore.get_trade_by_id(trade["id"])
        assert str(stored["status"]).upper() == "OPEN"
        assert int(stored.get("sl_low_bid_count", 0)) == 1

        # Pass 2: Cached market still shows wick, but fresh quote shows complete recovery (no_bid 0.42, no_ask 0.45)
        recovered_fresh = {"success": True, "ticker": BTC_TICKER, "yes_bid": 0.55, "yes_ask": 0.58,
                           "no_bid": 0.42, "no_ask": 0.45}
        _run_pass(user, markets, fresh=recovered_fresh)
        stored_recovered = TradeStore.get_trade_by_id(trade["id"])
        assert str(stored_recovered["status"]).upper() == "OPEN"
        assert int(stored_recovered.get("sl_low_bid_count", 0)) == 0
    finally:
        TradeStore.close_if_open(user["id"], trade, {"exit_reason": "TEST_CLEANUP", "exit_price": 0.0, "pnl": 0.0})


# ---------------------------------------------------------------- helpers
def test_side_bid_ask_is_symmetric_and_derives_missing_side():
    q = {"yes_bid": 0.89, "yes_ask": 0.90}
    assert settler._side_bid_ask(q, "no") == (pytest.approx(0.10), pytest.approx(0.11))
    assert settler._side_bid_ask(q, "yes") == (pytest.approx(0.89), pytest.approx(0.90))
    q2 = {"no_bid": 0.89, "no_ask": 0.90}
    assert settler._side_bid_ask(q2, "yes") == (pytest.approx(0.10), pytest.approx(0.11))


def test_trade_epoch_parses_et_timestamp():
    import datetime
    from zoneinfo import ZoneInfo
    exp = datetime.datetime(2026, 10, 22, 0, 46, 50, tzinfo=ZoneInfo("America/New_York")).timestamp()
    assert settler._trade_epoch("2026-10-22 12:46:50 AM ET") == exp
    assert settler._trade_epoch("2026-10-22T00:46:50.219791-04:00") == pytest.approx(exp + 0.219791)


def test_ws_quote_derives_no_side_from_yes_fields():
    """kalshi_trader.get_market_quote WS fast path must return a usable NO bid."""
    import backend.btc.kalshi_ws as ws
    raw = {"market_ticker": BTC_TICKER, "price_dollars": "0.2200", "yes_bid_dollars": "0.2200",
           "yes_ask_dollars": "0.2300"}
    with patch.object(ws, "get_market_cache", return_value=raw), \
         patch.object(ws, "subscribe_to_market", return_value=None):
        q = kt_mod.KalshiTrader().get_market_quote(BTC_TICKER)
    assert q["success"] is True
    assert q["no_bid"] == pytest.approx(0.77)
    assert q["no_ask"] == pytest.approx(0.78)
    assert q["yes_bid"] == pytest.approx(0.22)
