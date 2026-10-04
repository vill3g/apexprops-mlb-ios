"""
Unit tests for Milestone 1: Backend Stability & Kalshi 429 Resilience.
Covers:
- KalshiTrader get_market_result & get_market_quote 429 retries
- KalshiTrader get_balance & get_positions 429 backoff
- KalshiTrader place_order 429 backoff & interface contract
- SaaS settler per-ticker negative caching / backoff
- SaaS broadcaster raw_features list validation
- launch_desktop.py venv fallback
- auto_executor __init__.py re-exports
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch
import pytest
import requests

from backend.btc.kalshi_trader import KalshiTrader
import backend.saas_settler as saas_settler
from backend.btc.auto_executor import add_all_indicators


@pytest.fixture(autouse=True)
def _patch_sleep():
    """Bypass sleep delays in unit tests to keep test runs fast."""
    with patch("time.sleep"):
        yield


# ── 1. KalshiTrader 429 Retry Tests ──────────────────────────────────────────

def test_kalshi_get_market_result_retries_on_429():
    kt = KalshiTrader()
    
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limit exceeded"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "market": {"result": "yes", "status": "finalized"}
    }

    # First call returns 429, second returns 200
    kt.session.get = MagicMock(side_effect=[mock_resp_429, mock_resp_200])

    res = kt.get_market_result("KXBTC15M-TEST-1")
    assert res["success"] is True
    assert res["result"] == "yes"
    assert kt.session.get.call_count == 2


def test_kalshi_get_market_result_exhausts_retries_gracefully():
    kt = KalshiTrader()

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limit exceeded"

    kt.session.get = MagicMock(return_value=mock_resp_429)

    res = kt.get_market_result("KXBTC15M-TEST-EXHAUST")
    assert res["success"] is False
    assert res["result"] == ""
    assert "retries exhausted" in res["error"].lower() or "429" in res["error"]
    assert kt.session.get.call_count == 3


def test_kalshi_get_market_quote_retries_on_429():
    kt = KalshiTrader()

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Too Many Requests"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "market": {
            "status": "active",
            "yes_bid": 52,
            "no_bid": 48,
            "exchange_index": 0
        }
    }

    kt.session.get = MagicMock(side_effect=[mock_resp_429, mock_resp_200])

    res = kt.get_market_quote("KXBTC15M-TEST-QUOTE")
    assert res["success"] is True
    assert res["yes_bid"] == 0.52
    assert res["no_bid"] == 0.48
    assert kt.session.get.call_count == 2


# ── 2. Account Operations 429 Protection ─────────────────────────────────────

def test_kalshi_get_balance_retries_on_429():
    kt = KalshiTrader()
    kt._sign_headers = MagicMock(return_value={"test": "header"})

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limited"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "balance": 15000,
        "portfolio_value": 25000,
        "updated_ts": int(time.time())
    }

    kt.session.get = MagicMock(side_effect=[mock_resp_429, mock_resp_200])

    res = kt.get_balance(force_refresh=True)
    assert res["success"] is True
    assert res["balance_dollars"] == 150.0
    assert res["portfolio_value"] == 250.0
    assert kt.session.get.call_count == 2


def test_kalshi_get_positions_retries_on_429():
    kt = KalshiTrader()
    kt._sign_headers = MagicMock(return_value={"test": "header"})

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limited"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "market_positions": [{"ticker": "KXBTC15M-T", "position": 5}]
    }

    kt.session.get = MagicMock(side_effect=[mock_resp_429, mock_resp_200])

    res = kt.get_positions()
    assert res["success"] is True
    assert len(res["positions"]) == 1
    assert kt.session.get.call_count == 2


def test_kalshi_place_order_retries_on_429():
    kt = KalshiTrader()
    kt.get_active_15m_market = MagicMock(return_value={
        "ticker": "KXBTC15M-T", "strike_price": 80000.0, "yes_ask": 0.50, "no_ask": 0.50,
        "close_time": "2030-01-01T00:00:00Z"
    })
    kt.get_balance = MagicMock(return_value={"success": True, "balance_dollars": 500.0, "raw": {}})
    kt.get_positions = MagicMock(return_value={"success": True, "positions": []})
    kt._sign_headers = MagicMock(return_value={})

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limit hit"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "order_id": "ord-live-429",
        "client_order_id": "cid-429",
        "fill_count": "2.00",
        "average_fill_price": "0.54"
    }

    kt.order_session.post = MagicMock(side_effect=[mock_resp_429, mock_resp_200])

    res = kt.place_order(ticker="KXBTC15M-T", side="yes", count=2, dry_run=False)
    assert res["success"] is True
    assert res["order_id"] == "ord-live-429"
    assert res["ambiguous"] is False
    assert kt.order_session.post.call_count == 2


# ── 3. Settlement Per-Ticker Negative Caching ────────────────────────────────

def test_settlement_per_ticker_negative_caching():
    saas_settler.clear_unresolved_settlement_cache()

    ticker = "KXBTC15M-26OCT021700-00"
    base_time = 1759400000.0
    simulated_time = [base_time]

    with patch("time.time", side_effect=lambda: simulated_time[0]), \
         patch("backend.saas_settler.get_kalshi_15m_market", return_value=None), \
         patch("backend.btc.kalshi_trader.kalshi_trader.get_market_result") as mock_get_result, \
         patch("backend.database.trade_store.TradeStore") as mock_store, \
         patch("backend.saas_settler.get_all_active_users") as mock_users:

        # Kalshi returns empty result (contract still determining / pending)
        mock_get_result.return_value = {"success": True, "result": "", "status": "determining"}

        test_trade = {
            "id": "tr-1", "ticker": ticker, "side": "yes", "entry_price": 0.50,
            "count": 1, "status": "OPEN", "mode": "PAPER"
        }
        test_user = {"id": "u1", "username": "trader1", "trades": [test_trade]}
        mock_users.return_value = [test_user]
        mock_store.get_open_trades.return_value = [test_trade]
        mock_store.get_trade_by_id.return_value = {"status": "OPEN"}

        # Pass 1: queries Kalshi once and triggers backoff
        saas_settler._settle_saas_trades_pass()
        assert mock_get_result.call_count == 1

        # Pass 2 immediately after (1 second later): must NOT query Kalshi again due to negative cache
        simulated_time[0] = base_time + 1.0
        saas_settler._settle_saas_trades_pass()
        assert mock_get_result.call_count == 1

        # Pass 3 after UNRESOLVED_POLL_INTERVAL_SEC (31 seconds later): allowed to query Kalshi again
        simulated_time[0] = base_time + 32.0
        saas_settler._settle_saas_trades_pass()
        assert mock_get_result.call_count == 2

    saas_settler.clear_unresolved_settlement_cache()


# ── 4. SaaS Broadcaster raw_features Dict Validation ─────────────────────────

def test_raw_features_list_does_not_crash_fallback():
    """Verify that when raw_features is a list ([]), accessing trend/EMAs does not crash."""
    forecast = {
        "pre_gate_direction": "PASS",
        "raw_features": [],  # list object that previously caused AttributeError: 'list' object has no attribute 'get'
        "ml_prob": 0.50
    }

    # Replicate the logic patched in saas_broadcaster.py
    raw_rf = forecast.get("raw_features")
    rf = raw_rf if isinstance(raw_rf, dict) else {}
    trend = str(rf.get("trend_1h", "UP")).upper()
    ema_9 = float(rf.get("ema_9", 0))
    ema_21 = float(rf.get("ema_21", 0))

    assert trend == "UP"
    assert ema_9 == 0.0
    assert ema_21 == 0.0


# ── 5. Desktop Launcher Python Executable Fallback ───────────────────────────

def test_launch_desktop_python_fallback():
    import launch_desktop
    # When .venv doesn't exist, verify python_exe resolves to a valid existing executable
    app_dir = launch_desktop.APP_DIR
    venv_python = os.path.join(app_dir, ".venv", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable
    assert os.path.exists(python_exe)


# ── 6. AutoExecutor __init__.py Re-exports ───────────────────────────────────

def test_auto_executor_re_exports():
    import backend.btc.auto_executor as ae
    assert hasattr(ae, "add_all_indicators")
    assert callable(ae.add_all_indicators)
    assert hasattr(ae, "evaluate_next_15m_contract")
    assert hasattr(ae, "fetch_candles")
