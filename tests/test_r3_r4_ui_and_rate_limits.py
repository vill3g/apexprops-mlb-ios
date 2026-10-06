"""
Unit and integration tests for Requirements R3 and R4:
- R3: Decouple UI tab-switching, add explicit settings drawer auto-trading universe control.
- R4: Kalshi rate limit handling: frontend exponential backoff on 429 and backend fail_fast architecture.
"""

import re
import time
import inspect
from unittest.mock import MagicMock, patch
import pytest

from backend.auth.routes import UserConfigRequest
from backend.btc.kalshi_trader import KalshiTrader, get_authenticated_trader_for_user


# ── Requirement R3 Tests: Decouple UI Tab-Switching ──────────────────────────

def test_ui_select_universe_decoupled_from_backend_config():
    """Verify selectUniverse is a client-side view toggle and does NOT post to /api/auth/user/config."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Locate window.selectUniverse and slice its body up to the end of the definition
    start = html.find("window.selectUniverse = function(universe)")
    assert start != -1, "window.selectUniverse definition not found in saas_dashboard.html"
    end = html.find("const SPORT_ICONS =", start)
    assert end != -1, "SPORT_ICONS boundary not found after selectUniverse"
    select_univ_body = html[start:end]

    # Must NOT contain a fetch call to user config
    assert "/api/auth/user/config" not in select_univ_body, (
        "selectUniverse must not call /api/auth/user/config; tab switching must be decoupled"
    )
    assert "trading_universe: universe" not in select_univ_body, (
        "selectUniverse must not send trading_universe payload to server"
    )


def test_ui_toggle_auto_trading_does_not_overwrite_universe():
    """Verify toggleAutoTrader does not include trading_universe in its payload on tab changes."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    start = html.find("async function toggleAutoTrader(enabled)")
    assert start != -1, "toggleAutoTrader function not found in saas_dashboard.html"
    end = html.find("async function saveUserConfig()", start)
    assert end != -1, "saveUserConfig boundary not found after toggleAutoTrader"
    toggle_body = html[start:end]

    # In toggleAutoTrader, JSON.stringify must only persist ai_enabled and not targetUniverse
    assert "targetUniverse" not in toggle_body, (
        "toggleAutoTrader must not derive or send targetUniverse based on active tab"
    )
    assert "trading_universe: targetUniverse" not in toggle_body
    assert "body: JSON.stringify({ ai_enabled: enabled })" in toggle_body


def test_ui_settings_drawer_explicit_auto_trading_universe_control():
    """Verify the settings drawer has an explicit 3-way segmented control for auto-trading universe."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Check for the settings container and buttons in the drawer
    assert "id=\"auto-trading-universe-container\"" in html or "Auto-Trading Universe" in html
    assert "id=\"btn-auto-univ-crypto\"" in html
    assert "id=\"btn-auto-univ-sports\"" in html
    assert "id=\"btn-auto-univ-both\"" in html
    assert "id=\"auto-universe-label-badge\"" in html

    # Check for setAutoTradingUniverse function
    assert "window.setAutoTradingUniverse" in html
    assert "window.configuredTradingUniverse" in html

    # Verify setAutoTradingUniverse supports CRYPTO, SPORTS, BOTH
    assert "setAutoTradingUniverse('CRYPTO')" in html
    assert "setAutoTradingUniverse('SPORTS')" in html
    assert "setAutoTradingUniverse('BOTH')" in html

    # Verify saveUserConfig / saveConfig persists configuredTradingUniverse
    start_save = html.find("async function saveUserConfig()")
    assert start_save != -1, "saveUserConfig definition not found in saas_dashboard.html"
    end_save = html.find("async function saveKeys()", start_save)
    save_body = html[start_save:end_save]
    assert "configuredTradingUniverse" in save_body, (
        "saveUserConfig must persist window.configuredTradingUniverse"
    )
    assert "window.configuredTradingUniverse === 'CRYPTO' ? 'FINANCIAL'" in save_body, (
        "saveUserConfig must translate client-side CRYPTO to valid backend FINANCIAL"
    )
    assert "window.saveConfig = saveUserConfig;" in html


def test_ui_populate_user_settings_updates_explicit_setting():
    """Verify populateUserSettings updates setAutoTradingUniverse without overwriting tab view."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    start = html.find("function populateUserSettings(s, force = false)")
    assert start != -1, "populateUserSettings function not found"
    end = html.find("async function loadConfig()", start)
    body = html[start:end]

    assert "setAutoTradingUniverse" in body
    assert "!window.currentUniverse || force" in body


def test_user_config_request_crypto_client_mapping_and_schema_enforcement():
    """Verify client translates CRYPTO to FINANCIAL, and UserConfigRequest strictly rejects CRYPTO."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Frontend maps CRYPTO to FINANCIAL before API dispatch
    assert "window.configuredTradingUniverse === 'CRYPTO' ? 'FINANCIAL'" in html

    # 2. Backend accepts strictly valid universes
    for valid_univ in ["FINANCIAL", "SPORTS", "BOTH", "ALL", "financial", "sports"]:
        req = UserConfigRequest(trading_universe=valid_univ)
        assert req.trading_universe == valid_univ.upper()

    # 3. Backend strictly rejects CRYPTO and other non-schema inputs
    for invalid_univ in ["CRYPTO", "crypto", "STOCK", "FOREX", "UNKNOWN"]:
        with pytest.raises(Exception):
            UserConfigRequest(trading_universe=invalid_univ)


# ── Requirement R4 Tests: Kalshi Rate Limit Handling ─────────────────────────

def test_ui_fetch_live_bids_exponential_backoff_on_429():
    """Verify saas_dashboard.html implements exponential backoff on HTTP 429 and resets on success."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Verify dynamic scheduling instead of static setInterval(fetchLiveBids, 800)
    assert "scheduleNextLiveBids" in html
    assert "BASE_LIVE_BIDS_INTERVAL_MS = 800" in html
    assert "MAX_LIVE_BIDS_BACKOFF_MS = 30000" in html

    # Slice fetchLiveBids body
    start = html.find("async function fetchLiveBids()")
    assert start != -1, "fetchLiveBids function not found"
    end = html.find("function hideChartLoader()", start)
    bids_body = html[start:end]

    assert "res.status === 429" in bids_body
    # Must double the interval and cap at max (30,000ms)
    assert "liveBidsIntervalMs * 2" in bids_body
    assert "MAX_LIVE_BIDS_BACKOFF_MS" in bids_body
    # Must reset to base 800ms upon successful response
    assert "liveBidsIntervalMs = BASE_LIVE_BIDS_INTERVAL_MS" in bids_body


def test_kalshi_trader_fail_fast_get_balance_on_429():
    """Verify KalshiTrader(fail_fast=True) immediately returns on 429 without sleeping."""
    kt = KalshiTrader(fail_fast=True)
    assert kt.fail_fast is True

    kt._sign_headers = MagicMock(return_value={"test": "header"})
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limited by Kalshi"
    kt.session.get = MagicMock(return_value=mock_resp_429)

    with patch("time.sleep") as mock_sleep:
        t0 = time.time()
        res = kt.get_balance(force_refresh=True)
        elapsed = time.time() - t0

        assert elapsed < 0.2, f"get_balance took {elapsed}s, expected fail-fast"
        assert mock_sleep.call_count == 0, "time.sleep must not be called when fail_fast=True"
        assert res["success"] is False
        assert res.get("status_code") == 429
        assert kt.session.get.call_count == 1, "fail_fast should exit on the first 429 attempt"


def test_kalshi_trader_fail_fast_get_positions_on_429():
    """Verify KalshiTrader(fail_fast=True) immediately returns positions error on 429 without sleeping."""
    kt = KalshiTrader(fail_fast=True)

    kt._sign_headers = MagicMock(return_value={"test": "header"})
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limited"
    kt.session.get = MagicMock(return_value=mock_resp_429)

    with patch("time.sleep") as mock_sleep:
        t0 = time.time()
        res = kt.get_positions()
        elapsed = time.time() - t0

        assert elapsed < 0.2
        assert mock_sleep.call_count == 0
        assert res["success"] is False
        assert res.get("status_code") == 429
        assert kt.session.get.call_count == 1


def test_kalshi_trader_fail_fast_place_order_on_429():
    """Verify KalshiTrader(fail_fast=True) immediately returns on 429 during place_order without sleeping."""
    kt = KalshiTrader(fail_fast=True)
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
    kt.order_session.post = MagicMock(return_value=mock_resp_429)

    with patch("time.sleep") as mock_sleep:
        t0 = time.time()
        res = kt.place_order(ticker="KXBTC15M-T", side="yes", count=2, dry_run=False)
        elapsed = time.time() - t0

        assert elapsed < 0.2
        assert mock_sleep.call_count == 0
        assert res["success"] is False
        assert res.get("status_code") == 429
        assert res.get("ambiguous") is False
        assert kt.order_session.post.call_count == 1


def test_kalshi_trader_fail_fast_place_sports_order_on_429():
    """Verify KalshiTrader(fail_fast=True) immediately returns on 429 during place_sports_order."""
    kt = KalshiTrader(fail_fast=True)
    kt.get_market_quote = MagicMock(return_value={
        "success": True,
        "market": {"ticker": "KXNFLGAME-T", "yes_ask_dollars": 0.50, "status": "active", "close_time": "2030-01-01T00:00:00Z"}
    })
    kt.get_balance = MagicMock(return_value={"success": True, "balance_dollars": 500.0, "raw": {}})
    kt.get_exchange_breakdown = MagicMock(return_value={"success": True, "exchanges": [{"exchange_index": 0, "balance": 500.0}]})
    kt.get_positions = MagicMock(return_value={"success": True, "positions": []})
    kt._sign_headers = MagicMock(return_value={})
    kt.session.get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"event": {"markets": []}}))

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Rate limit hit"
    kt.order_session.post = MagicMock(return_value=mock_resp_429)

    with patch("time.sleep") as mock_sleep:
        t0 = time.time()
        res = kt.place_sports_order(
            ticker="KXNFLGAME-T",
            side="yes",
            count=1,
            limit_price_dollars=0.50,
            dry_run=False
        )
        elapsed = time.time() - t0

        assert elapsed < 0.2, f"place_sports_order took {elapsed}s"
        assert mock_sleep.call_count == 0
        assert res["success"] is False
        assert res.get("status_code") == 429
        assert kt.order_session.post.call_count == 1


def test_kalshi_trader_default_fail_fast_is_false():
    """Verify KalshiTrader() defaults to fail_fast=False for background workers to retry."""
    kt = KalshiTrader()
    assert kt.fail_fast is False


def test_engine_routes_fetch_series_events_no_sleep_on_429():
    """Verify _fetch_kalshi_series_events in engine.py does not call time.sleep on 429."""
    with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
        src = f.read()

    start = src.find("def _fetch_kalshi_series_events(series: str)")
    assert start != -1, "_fetch_kalshi_series_events function not found in engine.py"
    end = src.find("def _normalize_sport", start)
    func_src = src[start:end]

    assert "time.sleep" not in func_src, (
        "_fetch_kalshi_series_events must not call time.sleep on HTTP 429"
    )
    assert "elif resp.status_code == 429:" in func_src
    assert "break" in func_src


def test_engine_and_auth_routes_instantiate_trader_with_fail_fast():
    """Verify synchronous FastAPI routes instantiate KalshiTrader with fail_fast=True."""
    with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
        engine_src = f.read()

    with open("backend/auth/routes.py", "r", encoding="utf-8") as f:
        auth_src = f.read()

    # In engine.py: execute_sports_prediction must use fail_fast=True
    assert "get_authenticated_trader_for_user(user, fail_fast=True)" in engine_src

    # In auth/routes.py: synchronous routes must pass fail_fast=True
    assert "KalshiTrader(key_id=current_user['kalshi_key_id'], private_key_pem=priv, fail_fast=True)" in auth_src
    assert "KalshiTrader(fail_fast=True)" in auth_src


def test_get_authenticated_trader_for_user_accepts_fail_fast():
    """Verify get_authenticated_trader_for_user propagates fail_fast parameter."""
    sig = inspect.signature(get_authenticated_trader_for_user)
    assert "fail_fast" in sig.parameters
    assert sig.parameters["fail_fast"].default is False
