"""Regression tests for paper-trading realism fixes in kalshi_trader.py, executor.py and
saas_broadcaster.py. Before this change, PAPER fills were strictly better than any real LIVE
fill could be: no slippage, no latency drift, unlimited simulated liquidity, no balance cap,
and no expiry backstop inside place_order() itself. These tests pin the fixed behavior so it
can't silently regress back to "paper is easier than live".
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from backend.btc.kalshi_trader import KalshiTrader, PAPER_LATENCY_TAX_DOLLARS
from backend.btc.fees import kalshi_order_fee

_ET = ZoneInfo("America/New_York")


def _ticker_closing_in(seconds: int) -> str:
    """A KXBTC15M ticker whose encoded close time is `seconds` from now - same format
    market_close_epoch() parses (backend/btc/market_results.py), no network call needed."""
    close = datetime.now(_ET) + timedelta(seconds=seconds)
    return f"KXBTC15M-{close.strftime('%y%b%d%H%M').upper()}-15"


@pytest.fixture
def trader():
    return KalshiTrader()


def test_paper_entry_pays_slippage_and_latency_tax_rounded_to_cents(trader):
    ticker = _ticker_closing_in(400)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.place_order(ticker=ticker, side="yes", count=1, limit_price_dollars=0.55, dry_run=True)
    assert res["success"]
    expected = round(0.55 + 0.04 + PAPER_LATENCY_TAX_DOLLARS, 2)
    assert res["filled_price"] == expected
    # Never a fractional-cent price - Kalshi only quotes/fills in whole cents.
    assert round(res["filled_price"] * 100) == res["filled_price"] * 100


def test_paper_entry_is_never_cheaper_than_live_would_pay(trader):
    """This is the core bug: paper used to fill at the bare ask (no slippage/latency), making
    it strictly better-priced than a live order for the identical signal."""
    ticker = _ticker_closing_in(400)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.place_order(ticker=ticker, side="yes", count=1, limit_price_dollars=0.55, dry_run=True)
    assert res["filled_price"] > 0.55  # strictly worse than the bare quoted ask


def test_paper_entry_partial_fill_when_size_exceeds_simulated_depth(trader):
    ticker = _ticker_closing_in(400)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=5):
        res = trader.place_order(ticker=ticker, side="yes", count=50, limit_price_dollars=0.55, dry_run=True)
    assert res["success"]
    assert res["count"] == 5
    assert res["requested_count"] == 50
    assert "PARTIAL" in res["status"]


def test_paper_entry_no_fill_when_simulated_depth_is_zero(trader):
    ticker = _ticker_closing_in(400)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=0):
        res = trader.place_order(ticker=ticker, side="yes", count=1, limit_price_dollars=0.55, dry_run=True)
    assert res["success"] is False
    assert "liquidity" in res["error"].lower()


def test_paper_entry_rejects_market_inside_30s_expiry_backstop(trader):
    ticker = _ticker_closing_in(10)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.place_order(ticker=ticker, side="yes", count=1, limit_price_dollars=0.55, dry_run=True)
    assert res["success"] is False
    assert "30s" in res["error"]


def test_paper_entry_skips_expiry_check_for_a_ticker_with_no_encoded_close_time(trader):
    """A test fixture ticker or a fabricated offline ticker has nothing real to check the
    expiry backstop against, so it degrades gracefully instead of blocking every such order."""
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.place_order(ticker="KXBTC15M-TEST", side="yes", count=1, limit_price_dollars=0.55, dry_run=True)
    assert res["success"] is True


def test_paper_entry_enforces_affordability_when_balance_given(trader):
    ticker = _ticker_closing_in(400)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.place_order(ticker=ticker, side="yes", count=100, limit_price_dollars=0.55,
                                  dry_run=True, available_balance=1.00)
    assert res["success"] is False
    assert "Insufficient paper balance" in res["error"]


def test_paper_entry_skips_affordability_check_when_balance_omitted(trader):
    ticker = _ticker_closing_in(400)
    with patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.place_order(ticker=ticker, side="yes", count=1, limit_price_dollars=0.55, dry_run=True)
    assert res["success"] is True


def test_paper_exit_applies_latency_tax_rounds_to_cents_and_computes_real_fee(trader):
    with patch.object(trader, "get_market_quote", return_value={"success": True, "yes_bid": 0.60, "ticker": "KXBTC15M-TEST"}), \
         patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=100):
        res = trader.close_position(ticker="KXBTC15M-TEST", purchased_side="YES", count=2, dry_run=True)
    assert res["success"]
    expected_price = round(0.60 - PAPER_LATENCY_TAX_DOLLARS, 2)
    assert res["exit_price"] == expected_price
    assert round(res["exit_price"] * 100) == res["exit_price"] * 100
    assert res["fee_paid"] == round(kalshi_order_fee(expected_price, 2), 4)
    assert res["fee_paid"] > 0


def test_paper_exit_falls_back_to_full_fill_when_depth_is_zero(trader):
    """A missed exit isn't left 'stuck open' the way a missed entry simply never happens -
    it should still close, unlike a paper entry which is allowed to not fill at all."""
    with patch.object(trader, "get_market_quote", return_value={"success": True, "yes_bid": 0.60, "ticker": "KXBTC15M-TEST"}), \
         patch("backend.btc.kalshi_trader._simulated_book_depth", return_value=0):
        res = trader.close_position(ticker="KXBTC15M-TEST", purchased_side="YES", count=2, dry_run=True)
    assert res["success"]
    assert res["filled_count"] == 2
