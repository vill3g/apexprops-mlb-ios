"""Regression tests for audit findings M-DUP and M-AMBIG.

M-DUP: an automated LIVE entry whose outcome is unknown must block any further automated
entry for that account on that market - across loops, processes and restarts.
M-AMBIG: any failure after a BUY request has been sent must come back as either a confirmed
fill or `ambiguous: True` - never as a clean rejection the bot would retry.
"""
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.btc.kalshi_trader import KalshiTrader
from backend.database import order_intents


# ── order_intents (M-DUP) ────────────────────────────────────────────────────

def test_only_one_claim_per_account_and_market():
    key = order_intents.account_key_for_user(9001)
    assert order_intents.claim(key, "KXBTC15M-T1", "yes") is True
    assert order_intents.claim(key, "KXBTC15M-T1", "yes") is False
    assert order_intents.claim(key, "KXBTC15M-T1", "no") is False  # side doesn't matter
    # A different market or a different account is unaffected.
    assert order_intents.claim(key, "KXBTC15M-T2", "yes") is True
    assert order_intents.claim(order_intents.account_key_for_user(9002), "KXBTC15M-T1", "yes") is True


def test_concurrent_claims_have_exactly_one_winner():
    key = order_intents.account_key_for_user(9003)
    results = []
    barrier = threading.Barrier(12)

    def worker():
        barrier.wait()
        results.append(order_intents.claim(key, "KXBTC15M-RACE", "yes"))

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 1


def test_ambiguous_and_filled_outcomes_keep_the_claim_rejection_releases_it():
    key = order_intents.account_key_for_user(9004)

    assert order_intents.claim(key, "KXBTC15M-AMB", "yes")
    assert order_intents.settle_outcome(key, "KXBTC15M-AMB", {"success": False, "ambiguous": True, "client_order_id": "c1"}) == "ambiguous"
    assert order_intents.claim(key, "KXBTC15M-AMB", "yes") is False
    assert order_intents.get(key, "KXBTC15M-AMB")["state"] == "ambiguous"

    assert order_intents.claim(key, "KXBTC15M-OK", "yes")
    assert order_intents.settle_outcome(key, "KXBTC15M-OK", {"success": True, "client_order_id": "c2"}) == "filled"
    assert order_intents.claim(key, "KXBTC15M-OK", "yes") is False

    assert order_intents.claim(key, "KXBTC15M-REJ", "yes")
    assert order_intents.settle_outcome(key, "KXBTC15M-REJ", {"success": False, "error": "Insufficient funds"}) == "released"
    assert order_intents.claim(key, "KXBTC15M-REJ", "yes") is True  # may retry later in the interval


def test_claim_fails_closed_when_db_unavailable():
    with patch("backend.database.order_intents._connect", side_effect=Exception("disk I/O error")):
        assert order_intents.claim(order_intents.account_key_for_user(9005), "KXBTC15M-X", "yes") is False


# ── place_order LIVE outcome handling (M-AMBIG) ──────────────────────────────

TICKER = "KXBTC15M-26SEP271015-15"


def _resp(status=200, payload=None, json_exc=None):
    r = MagicMock()
    r.status_code = status
    r.text = "" if payload is None else str(payload)
    if json_exc:
        r.json.side_effect = json_exc
    else:
        r.json.return_value = payload or {}
    return r


def _live_trader(post_side_effect, positions_before=0.0, positions_after=0.0, orders_lookup=None):
    """A KalshiTrader whose network calls are all mocked. Positions: first call returns
    `positions_before` YES contracts on TICKER, later calls return `positions_after`."""
    kt = KalshiTrader()
    close = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    market = {"ticker": TICKER, "close_time": close, "yes_ask": 0.50, "no_ask": 0.52}
    kt.get_active_15m_market = MagicMock(return_value=market)
    kt.get_balance = MagicMock(return_value={"success": True, "balance_dollars": 100.0, "raw": {}})
    kt._sign_headers = MagicMock(return_value={})
    pos_calls = {"n": 0}

    def get_positions():
        pos_calls["n"] += 1
        qty = positions_before if pos_calls["n"] == 1 else positions_after
        return {"success": True, "positions": [{"ticker": TICKER, "position": qty}]}

    kt.get_positions = MagicMock(side_effect=get_positions)
    kt.order_session = MagicMock()
    kt.order_session.post.side_effect = post_side_effect
    kt.session = MagicMock()
    kt.session.get.side_effect = orders_lookup or (lambda *a, **k: _resp(404))
    return kt


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("backend.btc.kalshi_trader.time.sleep"):
        yield


def _buy(kt, count=5):
    return kt.place_order(ticker=TICKER, side="yes", count=count, limit_price_dollars=0.50,
                          dry_run=False, slippage_buffer_dollars=0.04)


def test_read_timeout_with_no_visible_fill_is_ambiguous():
    kt = _live_trader(requests.exceptions.ReadTimeout("read timed out"))
    res = _buy(kt)
    assert res["success"] is False
    assert res["ambiguous"] is True
    assert res["client_order_id"]


def test_dropped_connection_after_send_is_no_longer_a_clean_rejection():
    """Previously any non-Timeout exception returned a plain failure, so the bot retried."""
    kt = _live_trader(requests.exceptions.ConnectionError("RemoteDisconnected"),
                      positions_before=0.0, positions_after=3.0)
    res = _buy(kt)
    assert res["success"] is True
    assert res["count"] == 3  # confirmed via the position change


def test_unreadable_200_response_is_ambiguous_not_rejected():
    kt = _live_trader(lambda *a, **k: _resp(200, json_exc=ValueError("garbled body")))
    res = _buy(kt)
    assert res["success"] is False and res["ambiguous"] is True


def test_connect_timeout_is_a_clean_failure_because_nothing_was_sent():
    kt = _live_trader(requests.exceptions.ConnectTimeout("connect timed out"))
    res = _buy(kt)
    assert res["success"] is False
    assert not res.get("ambiguous")


def test_lost_retry_response_is_confirmed_by_order_lookup():
    """First IOC comes back unfilled; the automatic retry is sent but its response is lost.
    Previously that was swallowed and reported as 'Unfilled' - a clean rejection."""
    sent = []

    def post(url, json=None, headers=None, timeout=None):
        sent.append(json)
        if len(sent) == 1:
            return _resp(200, {"fill_count": "0"})
        raise requests.exceptions.ReadTimeout("retry read timed out")

    def lookup(url, params=None, headers=None, timeout=None):
        retry_cid = sent[-1]["client_order_id"]
        return _resp(200, {"orders": [{"client_order_id": retry_cid, "fill_count": 4, "order_id": "ord-9"}]})

    kt = _live_trader(post, orders_lookup=lookup)
    res = _buy(kt)
    assert len(sent) == 2
    assert res["success"] is True
    assert res["count"] == 4
    assert res["client_order_id"] == sent[1]["client_order_id"]


def test_lost_retry_response_with_no_confirmation_is_ambiguous():
    calls = {"n": 0}

    def post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _resp(200, {"fill_count": "0"})
        raise requests.exceptions.ConnectionError("reset")

    kt = _live_trader(post)
    res = _buy(kt)
    assert res["success"] is False and res["ambiguous"] is True


def test_retry_that_was_never_sent_stays_a_clean_unfilled():
    """If the retry fails before sending (e.g. the fresh-market lookup errors), the only
    order that went out is known unfilled, so a clean 'Unfilled' is still correct."""
    kt = _live_trader(lambda *a, **k: _resp(200, {"fill_count": "0"}))
    real_market = kt.get_active_15m_market.return_value
    kt.get_active_15m_market = MagicMock(side_effect=[real_market, RuntimeError("market fetch failed")])
    res = _buy(kt)
    assert kt.order_session.post.call_count == 1
    assert res["success"] is False
    assert not res.get("ambiguous")
    assert "Unfilled" in res["error"]
