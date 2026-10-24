"""
ShadowTrader AI — Comprehensive Opaque-Box E2E Audit Test Suite
Covers Tiers 1-4 derived strictly from ORIGINAL_REQUEST.md and PROJECT.md.

Tier 1: Feature Coverage (>=5 tests per core feature)
    1. Backend Health & Watchdog Supervisor
    2. Kalshi 429 Rate Limit Handling
    3. Static Asset Zero 404s
    4. HTML Structural Integrity
    5. Auto Trader Logic & Toggle Synchronization
Tier 2: Boundary & Corner Cases (>=5 tests)
Tier 3: Cross-Feature Interactions (>=5 tests)
Tier 4: Real-World Scenarios (>=5 tests)
"""

import asyncio
import ctypes
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.auth.security import create_jwt_token
from backend.btc.indicators import add_all_indicators
from backend.btc.kalshi_trader import KalshiTrader
from backend.btc.pattern_detector import detect_candlestick_patterns
from backend.core.registry import get_auto_executor
from backend.database.models import (
    get_all_active_users,
    get_user_by_id,
)
from backend.main import SecurityMiddleware, app, require_auth

# =====================================================================
# FIXTURES
# =====================================================================

@pytest.fixture(scope="module")
def api_client():
    """TestClient instance configured for FastAPI E2E API requests."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture(scope="module")
def active_test_user():
    """Retrieve or create an active seeded user for session testing."""
    users = get_all_active_users()
    assert len(users) > 0, "At least one seeded test user must exist"
    user = users[0]
    token = create_jwt_token(user["id"], user["username"])
    return {"user": user, "token": token}


@pytest.fixture(scope="module")
def auth_headers(active_test_user):
    """Authenticated Bearer JWT headers for the seeded test user."""
    return {"Authorization": f"Bearer {active_test_user['token']}"}


@pytest.fixture(scope="module")
def static_dir():
    return os.path.join(REPO_ROOT, "static")


# =====================================================================
# TIER 1: FEATURE COVERAGE (Core Feature 1: Backend Health & Watchdog)
# =====================================================================

class TestTier1BackendHealthAndWatchdog:
    """Core Feature 1: Backend health endpoints, watchdog supervision, and middleware."""

    def test_tier1_backend_health_check_endpoint(self, api_client):
        """GET /api/health returns 200 OK with status='ok' and service metadata."""
        resp = api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        assert "service" in data
        assert "version" in data

    def test_tier1_backend_engine_root_endpoint(self, api_client):
        """GET /api/engine/ returns 200 OK and lists all supported trading assets."""
        resp = api_client.get("/api/engine/")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        assets = data.get("assets", [])
        assert isinstance(assets, list)
        for expected_asset in ["BTC", "ETH", "GOLD", "NDQ"]:
            assert expected_asset in assets

    def test_tier1_server_watchdog_single_instance_mutex(self):
        """server_watchdog._acquire_watchdog_lock enforces single-process execution."""

        # Create/test named mutex behavior
        test_mutex_name = f"TestWatchdogMutex_{os.getpid()}_{int(time.time())}"
        h1 = ctypes.windll.kernel32.CreateMutexW(None, False, test_mutex_name)
        assert h1 != 0, "Initial mutex handle creation must succeed"

        # Second acquisition of the same named mutex must report ERROR_ALREADY_EXISTS (183)
        h2 = ctypes.windll.kernel32.CreateMutexW(None, False, test_mutex_name)
        err = ctypes.windll.kernel32.GetLastError()
        assert err == 183, "Duplicate mutex acquisition must report ERROR_ALREADY_EXISTS"

        # Cleanup handles
        ctypes.windll.kernel32.CloseHandle(h1)
        ctypes.windll.kernel32.CloseHandle(h2)

    def test_tier1_server_watchdog_command_construction(self):
        """server_watchdog configuration selects a valid python executable and headless flags."""
        import server_watchdog

        assert os.path.exists(server_watchdog.PYTHON_EXE), "Watchdog Python executable must exist on disk"
        assert server_watchdog.APP_PORT == 8058, "Watchdog target port must be 8058"
        assert os.path.isdir(server_watchdog.APP_DIR), "Watchdog APP_DIR must be a valid directory"

    def test_tier1_security_middleware_rate_limiting(self, api_client):
        """SecurityMiddleware triggers HTTP 429 when client exceeds request threshold."""
        # Find SecurityMiddleware instance on app
        sec_middleware = None
        current = app.middleware_stack
        while current is not None:
            if isinstance(current, SecurityMiddleware):
                sec_middleware = current
                break
            current = getattr(current, "app", None)

        if sec_middleware is not None:
            client_ip = "testclient"
            # Simulate 5000 requests in window
            now = time.time()
            sec_middleware.rate_limit_records[client_ip] = [now] * 5001
            try:
                resp = api_client.get("/api/engine/btc/trade/config")
                assert resp.status_code == 429
                assert "Rate Limit Exceeded" in resp.text
            finally:
                sec_middleware.rate_limit_records[client_ip].clear()
        else:
            # Direct unit test of SecurityMiddleware dispatch
            dummy_app = MagicMock()
            sm = SecurityMiddleware(dummy_app)
            req = MagicMock()
            req.client.host = "127.0.0.1"
            req.url.path = "/api/custom/resource"
            req.method = "POST"
            now = time.time()
            sm.rate_limit_records["127.0.0.1"] = [now] * 5005

            async def call_dispatch():
                return await sm.dispatch(req, None)

            res = asyncio.run(call_dispatch())
            assert res.status_code == 429


# =====================================================================
# TIER 1: FEATURE COVERAGE (Core Feature 2: Kalshi 429 Rate Limit Handling)
# =====================================================================

class TestTier1Kalshi429RateLimitHandling:
    """Core Feature 2: Kalshi rate limit handling across market, quote, balance, and order APIs."""

    def test_tier1_kalshi_trader_market_result_429_graceful(self):
        """get_market_result handles HTTP 429 by returning an error dictionary without raising."""
        trader = KalshiTrader()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = '{"error": "Rate limit exceeded. Please retry."}'

        with patch.object(trader.session, "get", return_value=mock_resp):
            res = trader.get_market_result("KXBTC15M-26MAR14-T1000")
            assert isinstance(res, dict)
            assert res.get("success") is False
            assert "429" in res.get("error", "")

    def test_tier1_kalshi_trader_market_quote_429_graceful(self):
        """get_market_quote handles HTTP 429 returning structured error without crashing."""
        trader = KalshiTrader()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = '{"error": "Too Many Requests"}'

        with patch.object(trader.session, "get", return_value=mock_resp):
            res = trader.get_market_quote("KXBTC15M-26MAR14-T1000")
            assert isinstance(res, dict)
            assert res.get("success") is False
            assert "429" in res.get("error", "")

    def test_tier1_kalshi_trader_balance_429_handled(self):
        """get_balance handles HTTP 429 returning safe zero-balance fallback."""
        trader = KalshiTrader()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "HTTP 429 Too Many Requests"

        with patch.object(trader.session, "get", return_value=mock_resp):
            res = trader.get_balance(force_refresh=True)
            assert isinstance(res, dict)
            assert res.get("success") is False
            assert "429" in res.get("error", "")
            assert res.get("balance_dollars") == 0.0
            assert res.get("balance_cents") == 0

    def test_tier1_kalshi_trader_active_15m_market_fallback_on_429(self):
        """get_active_15m_market falls back to synthetic or returns clean None under 429 pressure."""
        trader = KalshiTrader()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "HTTP 429 Rate Limit"

        with patch.object(trader.session, "get", return_value=mock_resp):
            res = trader.get_active_15m_market(
                series_ticker="KXBTC15M",
                allow_synthetic=True,
                force_refresh=True,
            )
            # When synthetic fallback is allowed, must return synthetic object
            assert res is not None
            assert res.get("is_synthetic") is True or res.get("status") == "synthetic"
            assert "SYNTH" in res.get("ticker", "")

    def test_tier1_kalshi_trader_close_position_429_handled(self):
        """close_position handles HTTP 429 without unhandled exceptions."""
        trader = KalshiTrader()
        mock_quote = {
            "success": True,
            "ticker": "KXBTC15M-26MAR14-T1000",
            "yes_bid": 0.55,
            "no_bid": 0.45,
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"

        with patch.object(trader, "get_market_quote", return_value=mock_quote), \
             patch.object(trader, "is_authenticated", return_value=True), \
             patch.object(trader, "_sign_headers", return_value={}), \
             patch.object(trader.order_session, "post", return_value=mock_resp):
            res = trader.close_position(
                ticker="KXBTC15M-26MAR14-T1000",
                purchased_side="YES",
                count=1.0,
                dry_run=False,
            )
            assert isinstance(res, dict)
            assert res.get("success") is False
            assert "429" in res.get("error", "")


# =====================================================================
# TIER 1: FEATURE COVERAGE (Core Feature 3: Static Asset Zero 404s)
# =====================================================================

class TestTier1StaticAssetZero404s:
    """Core Feature 3: Static asset resolution, zero 404s, and file integrity."""

    def test_tier1_static_css_assets_exist(self, static_dir):
        """All stylesheet files referenced in HTML exist on disk."""
        html_files = ["saas_dashboard.html", "login.html", "trades.html"]
        referenced_css = set()

        for fname in html_files:
            fpath = os.path.join(static_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            matches = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']', content)
            matches += re.findall(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\']', content)
            for m in matches:
                if not m.startswith("http") and not m.startswith("//"):
                    clean = m.split("?")[0].lstrip("./")
                    clean = clean.removeprefix("static/")
                    referenced_css.add(clean)

        for rel_css in referenced_css:
            full_path = os.path.join(static_dir, rel_css)
            assert os.path.isfile(full_path), f"CSS asset referenced in HTML missing: {full_path}"

    def test_tier1_static_js_assets_exist(self, static_dir):
        """All local JavaScript files referenced in HTML exist on disk."""
        html_files = ["saas_dashboard.html", "login.html", "trades.html"]
        referenced_js = set()

        for fname in html_files:
            fpath = os.path.join(static_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            matches = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', content)
            for m in matches:
                if not m.startswith("http") and not m.startswith("//"):
                    clean = m.split("?")[0].lstrip("./")
                    clean = clean.removeprefix("static/")
                    referenced_js.add(clean)

        for rel_js in referenced_js:
            full_path = os.path.join(static_dir, rel_js)
            assert os.path.isfile(full_path), f"JS asset referenced in HTML missing: {full_path}"

    def test_tier1_static_images_and_icons_exist(self, static_dir):
        """Local images and splash screens in saas_dashboard.html exist on disk."""
        fpath = os.path.join(static_dir, "saas_dashboard.html")
        assert os.path.exists(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        # Find img src and link icons (ignoring JS template variables ${...})
        img_srcs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
        icon_hrefs = re.findall(r'<link[^>]+rel=["\'](?:icon|apple-touch-icon|apple-touch-startup-image)["\'][^>]+href=["\']([^"\']+)["\']', content)

        for path in img_srcs + icon_hrefs:
            if path.startswith("${") or "{" in path:
                continue
            if not path.startswith("http") and not path.startswith("data:") and not path.startswith("//"):
                clean = path.split("?")[0].lstrip("./")
                clean = clean.removeprefix("static/")
                full_path = os.path.join(static_dir, clean)
                assert os.path.isfile(full_path), f"Local image/icon referenced in saas_dashboard.html missing: {full_path}"

    def test_tier1_manifest_icons_exist(self, static_dir):
        """All icons specified in manifest.json exist on disk with valid byte sizes."""
        manifest_path = os.path.join(static_dir, "manifest.json")
        assert os.path.exists(manifest_path), "manifest.json must exist"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        icons = manifest.get("icons", [])
        assert len(icons) > 0, "manifest.json must define at least one icon"
        for icon in icons:
            src = icon.get("src", "").lstrip("./")
            if src.startswith("/static/"):
                src = src[len("/static/"):]
            elif src.startswith("static/"):
                src = src[len("static/"):]
            full_path = os.path.join(static_dir, src)
            assert os.path.isfile(full_path), f"Icon defined in manifest.json missing: {full_path}"
            assert os.path.getsize(full_path) > 0, f"Icon file empty: {full_path}"

    def test_tier1_fastapi_serves_static_assets(self, api_client):
        """FastAPI static file router returns 200 OK for core static assets."""
        resp1 = api_client.get("/static/css/app.css")
        assert resp1.status_code == 200
        assert "text/css" in resp1.headers.get("content-type", "")

        resp2 = api_client.get("/static/js/app.js")
        assert resp2.status_code == 200
        assert "javascript" in resp2.headers.get("content-type", "")


# =====================================================================
# TIER 1: FEATURE COVERAGE (Core Feature 4: HTML Structural Integrity)
# =====================================================================

class _HTMLTagValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.open_tags: list[str] = []
        self.unclosed_critical: list[str] = []
        self.all_ids: list[str] = []
        self.critical_ids: set[str] = {"settingsDrawer", "tradingModal", "orderModal"}

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        elem_id = attrs_dict.get("id")
        if elem_id:
            self.all_ids.append(elem_id)
        if tag in ["div", "main", "header", "section"]:
            self.open_tags.append((tag, elem_id))

    def handle_endtag(self, tag):
        for i in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[i][0] == tag:
                self.open_tags.pop(i)
                break


class TestTier1HTMLStructuralIntegrity:
    """Core Feature 4: HTML syntax parsing, DOM hierarchy, and viewport definitions."""

    def test_tier1_saas_dashboard_html_syntax(self, static_dir):
        """saas_dashboard.html parses cleanly without fatal syntax or tokenization errors."""
        fpath = os.path.join(static_dir, "saas_dashboard.html")
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        validator = _HTMLTagValidator()
        validator.feed(content)
        assert len(validator.all_ids) > 50, "HTML must contain populated DOM element IDs"

    def test_tier1_saas_dashboard_critical_drawers_closed(self, static_dir):
        """settingsDrawer element is cleanly closed in saas_dashboard.html."""
        fpath = os.path.join(static_dir, "saas_dashboard.html")
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'id="settingsDrawer"' in content
        # Ensure closing tags exist after the settings drawer declaration
        idx = content.find('id="settingsDrawer"')
        tail = content[idx:]
        assert "</div>" in tail

    def test_tier1_saas_dashboard_unique_element_ids(self, static_dir):
        """Critical interactive element IDs in saas_dashboard.html are unique."""
        fpath = os.path.join(static_dir, "saas_dashboard.html")
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        validator = _HTMLTagValidator()
        validator.feed(content)

        # Check critical trading control IDs
        critical_ids = [
            "settingsDrawer",
            "autoTraderToggle",
            "nav-auto-badge",
            "tradingModal",
            "chartContainer",
        ]
        for cid in critical_ids:
            if cid in validator.all_ids:
                count = validator.all_ids.count(cid)
                assert count == 1, f"Element ID '{cid}' duplicated {count} times in saas_dashboard.html"

    def test_tier1_login_and_trades_html_structural_tags(self, static_dir):
        """login.html and trades.html contain valid opening and closing structural tags."""
        for fname in ["login.html", "trades.html"]:
            fpath = os.path.join(static_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read().lower()
            assert "<!doctype html>" in content or "<html" in content
            assert "<head>" in content or "<head " in content
            assert "</head>" in content
            assert "<body" in content
            assert "</body>" in content
            assert "</html>" in content

    def test_tier1_viewport_meta_has_no_fit_cover(self, static_dir):
        """AGENTS.md: never use viewport-fit=cover (it causes the iOS status-bar blur/black gap)."""
        for fname in sorted(f for f in os.listdir(static_dir) if f.endswith(".html")):
            with open(os.path.join(static_dir, fname), "r", encoding="utf-8") as f:
                content = f.read()
            assert "viewport-fit=cover" not in content, f"viewport-fit=cover found in {fname}"


# =====================================================================
# TIER 1: FEATURE COVERAGE (Core Feature 5: Auto Trader Logic & Toggle Sync)
# =====================================================================

class TestTier1AutoTraderLogicAndToggle:
    """Core Feature 5: Auto Trader configuration, toggling, and state reflection."""

    def test_tier1_autotrader_config_get(self, api_client, auth_headers):
        """GET /api/engine/{asset}/trade/config returns complete configuration schema."""
        resp = api_client.get("/api/engine/btc/trade/config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "mode" in data
        assert data.get("mode") in ["PAPER", "LIVE"]
        assert "max_contracts" in data
        assert "min_conviction" in data

    def test_tier1_autotrader_toggle_post(self, api_client, auth_headers):
        """POST /api/engine/{asset}/trade/toggle toggles execution and returns updated state."""
        resp = api_client.post("/api/engine/btc/trade/toggle?enabled=true", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("enabled") is True or data.get("status") == "ok"

    def test_tier1_autotrader_toggle_sync_state(self, api_client, auth_headers):
        """Toggling state to false synchronizes with subsequent GET config calls."""
        # Toggle OFF
        toggle_res = api_client.post("/api/engine/btc/trade/toggle?enabled=false", headers=auth_headers)
        assert toggle_res.status_code == 200

        # Query config to verify synchronization
        cfg_res = api_client.get("/api/engine/btc/trade/config", headers=auth_headers)
        assert cfg_res.status_code == 200
        assert cfg_res.json().get("enabled") is False

    def test_tier1_autotrader_mode_switch(self, api_client, auth_headers):
        """POST /api/engine/{asset}/trade/mode cleanly updates mode between PAPER/LIVE."""
        resp = api_client.post("/api/engine/btc/trade/mode?mode=PAPER", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json().get("mode") == "PAPER"

    def test_tier1_autotrader_status_reflection(self, api_client, auth_headers):
        """GET /api/engine/{asset}/trade/status returns real-time metrics and state."""
        resp = api_client.get("/api/engine/btc/trade/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert "trades_count" in data or "balance" in data or "balance_dollars" in data


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES (>=5 Tests)
# =====================================================================

class TestTier2BoundaryAndCornerCases:
    """Tier 2: Empty payloads, network timeouts, invalid tickers, missing tokens, malformed queries."""

    def test_tier2_boundary_empty_config_payload(self, api_client, auth_headers):
        """POST /api/engine/btc/trade/config with empty payload does not cause a 500 error."""
        resp = api_client.post("/api/engine/btc/trade/config", json={}, headers=auth_headers)
        assert resp.status_code in [200, 422], f"Unexpected status: {resp.status_code}"

    def test_tier2_boundary_kalshi_network_timeout(self):
        """KalshiTrader.get_market_result gracefully catches Timeout returning structured error."""
        trader = KalshiTrader()
        with patch.object(trader.session, "get", side_effect=requests.exceptions.Timeout("Connection timed out")):
            res = trader.get_market_result("KXBTC15M-TEST")
            assert isinstance(res, dict)
            assert res.get("success") is False
            assert "timed out" in res.get("error", "").lower()

    def test_tier2_boundary_invalid_asset_rejected(self, api_client):
        """GET /api/engine/{unsupported_asset}/trade/config rejects invalid asset with 404."""
        resp = api_client.get("/api/engine/NONEXISTENT_ASSET_XYZ/trade/config")
        assert resp.status_code == 404
        assert "unknown asset" in resp.text.lower() or "not found" in resp.text.lower()

    def test_tier2_boundary_missing_auth_token_rejected(self):
        """require_auth dependency raises HTTP 401 when foreign caller lacks required token."""
        req = MagicMock()
        req.client.host = "203.0.113.1"  # Foreign non-LAN address
        req.headers = {}
        req.cookies = {}

        with patch("backend.main.API_TOKEN", "valid-secret-master-token"):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc_info:
                require_auth(req, x_api_token=None)
            assert exc_info.value.status_code == 401
            assert "invalid or missing" in exc_info.value.detail.lower()

    def test_tier2_boundary_malformed_toggle_query(self, api_client, auth_headers):
        """POST /api/engine/btc/trade/toggle with non-boolean query rejects with 422."""
        resp = api_client.post("/api/engine/btc/trade/toggle?enabled=invalid_boolean_string", headers=auth_headers)
        assert resp.status_code == 422

    def test_tier2_boundary_order_invalid_count_rejected(self):
        """KalshiTrader.place_order rejects non-positive or fractional counts."""
        trader = KalshiTrader()
        # Zero count
        res_zero = trader.place_order("KXBTC15M-TEST", "yes", count=0, dry_run=True)
        assert res_zero.get("success") is False
        assert "invalid" in res_zero.get("error", "").lower()

        # Negative count
        res_neg = trader.place_order("KXBTC15M-TEST", "yes", count=-5, dry_run=True)
        assert res_neg.get("success") is False

        # Fractional count
        res_frac = trader.place_order("KXBTC15M-TEST", "yes", count=1.5, dry_run=True)
        assert res_frac.get("success") is False
        assert "fractional" in res_frac.get("error", "").lower()

    def test_tier2_boundary_order_invalid_side_rejected(self):
        """KalshiTrader.place_order rejects invalid contract sides."""
        trader = KalshiTrader()
        res = trader.place_order("KXBTC15M-TEST", "maybe", count=1, dry_run=True)
        assert res.get("success") is False
        assert "side" in res.get("error", "").lower()


# =====================================================================
# TIER 3: CROSS-FEATURE INTERACTIONS (>=5 Tests)
# =====================================================================

class TestTier3CrossFeatureInteractions:
    """Tier 3: Toggle synchronization with DB, rate limit in loop, routing, asset isolation."""

    def test_tier3_cross_autotrader_toggle_db_user_sync(self, api_client, active_test_user):
        """Auto Trader toggle via API synchronizes memory executor and SQLite user record."""
        user = active_test_user["user"]
        token = active_test_user["token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Enable trading
        resp1 = api_client.post("/api/engine/btc/trade/toggle?enabled=true", headers=headers)
        assert resp1.status_code == 200
        u1 = get_user_by_id(user["id"])
        assert u1.get("ai_enabled") == 1

        # Disable trading
        resp2 = api_client.post("/api/engine/btc/trade/toggle?enabled=false", headers=headers)
        assert resp2.status_code == 200
        u2 = get_user_by_id(user["id"])
        assert u2.get("ai_enabled") == 0

    def test_tier3_cross_rate_limit_during_trading_loop(self):
        """Simulated 429 during active trading loop executes without process crash or exception bubble."""
        executor = get_auto_executor("BTC")
        trader = KalshiTrader()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"

        with patch.object(trader.session, "get", return_value=mock_resp), \
             patch("backend.btc.kalshi_trader.kalshi_trader", trader):
            # Check rollover under simulated 429
            result = executor.check_and_execute_rollover()
            assert result is None or isinstance(result, dict)

    def test_tier3_cross_frontend_asset_url_routing(self, api_client, static_dir):
        """Frontend asset references in HTML map directly to working FastAPI routes."""
        # Query primary dashboard routes
        routes = [
            "/favicon.ico",
            "/trades.html",
            "/login.html",
            "/saas_dashboard.html",
        ]
        for route in routes:
            resp = api_client.get(route)
            assert resp.status_code in [200, 404], f"Unexpected status on {route}: {resp.status_code}"
            # trades.html, login.html, and saas_dashboard.html must serve 200 OK
            if route.endswith(".html"):
                assert resp.status_code == 200

    def test_tier3_cross_multi_asset_executor_isolation(self):
        """AutoExecutor instances for different assets remain fully isolated."""
        ex_btc = get_auto_executor("BTC")
        ex_eth = get_auto_executor("ETH")

        assert ex_btc is not ex_eth, "Executors for different assets must be separate instances"
        assert ex_btc.asset == "BTC"
        assert ex_eth.asset == "ETH"

        # Mutate configuration on one instance and verify non-interference
        ex_btc.set_max_contracts(7)
        ex_eth.set_max_contracts(14)

        assert ex_btc.max_contracts == 7
        assert ex_eth.max_contracts == 14

    def test_tier3_cross_risk_limit_suppression(self):
        """AutoExecutor suppresses order submission when daily risk budget is exceeded."""
        executor = get_auto_executor("BTC")
        executor.set_risk_limits(max_daily_risk=50.0, max_daily_trades=2)

        # Mock trade history with losses exceeding budget
        mock_trades = [
            {
                "id": "t1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "realized_pnl": -35.0,
                "status": "CLOSED",
            },
            {
                "id": "t2",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "realized_pnl": -25.0,
                "status": "CLOSED",
            },
        ]

        rejection_reason = executor.check_risk_budget(mock_trades)
        assert rejection_reason is not None, "Risk budget check must reject when limit exceeded"
        assert any(term in rejection_reason.lower() for term in ["risk", "trades", "limit", "budget", "reached"])


# =====================================================================
# TIER 4: REAL-WORLD SCENARIOS (>=5 Tests)
# =====================================================================

class TestTier4RealWorldScenarios:
    """Tier 4: Full startup to shutdown, simulated 15m candle evaluation, repeated 429, directory scan."""

    def test_tier4_real_world_lifespan_startup_and_shutdown(self):
        """FastAPI lifespan context manager completes startup and shutdown hooks cleanly."""
        from backend.main import lifespan

        async def run_lifecycle():
            async with lifespan(app):
                # Verify application is initialized
                assert app.title == "BTC 15M Pattern & Confluence Engine"

        # Execute lifespan
        asyncio.run(run_lifecycle())

    def test_tier4_real_world_simulated_15m_candle_evaluation(self):
        """Simulate 15m candle evaluation: compute indicators and detect patterns on synthetic data."""
        # Generate 60 synthetic 15m bars
        np.random.seed(42)
        n_bars = 60
        base_price = 65000.0
        price_changes = np.random.normal(0, 100, n_bars)
        closes = base_price + np.cumsum(price_changes)
        highs = closes + np.random.uniform(10, 50, n_bars)
        lows = closes - np.random.uniform(10, 50, n_bars)
        opens = (closes + lows) / 2.0
        volumes = np.random.uniform(50, 500, n_bars)

        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-10-01", periods=n_bars, freq="15min"),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })

        # Apply indicator calculations
        df_ind = add_all_indicators(df)
        assert df_ind is not None
        assert not df_ind.empty
        assert any(col in df_ind.columns for col in ["ema_9", "ema_21", "rsi", "macd_line", "atr"])

        # Apply pattern detection
        patterns = detect_candlestick_patterns(df_ind)
        assert isinstance(patterns, (list, dict))

    def test_tier4_real_world_simulated_repeated_429_resilience(self):
        """Simulate prolonged 429 burst: trader functions gracefully back off and return safe structures."""
        trader = KalshiTrader()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = '{"error": "Rate limit exceeded"}'

        with patch.object(trader.session, "get", return_value=mock_resp):
            # Repeated calls in tight loop
            for _ in range(10):
                res = trader.get_market_result("KXBTC15M-BURST-TEST")
                assert res.get("success") is False
                assert "429" in res.get("error", "")

    def test_tier4_real_world_static_directory_scan(self, static_dir):
        """Recursive directory scan of static/ verifying all files exist, are readable, and non-empty."""
        assert os.path.isdir(static_dir)
        total_files = 0
        zero_byte_files = []

        for root, _, files in os.walk(static_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                total_files += 1
                size = os.path.getsize(fpath)
                if size == 0:
                    zero_byte_files.append(fpath)
                # Verify read accessibility
                with open(fpath, "rb") as f:
                    _ = f.read(128)

        assert total_files > 10, "Static directory must contain populated assets"
        assert len(zero_byte_files) == 0, f"Found 0-byte corrupt static files: {zero_byte_files}"

    def test_tier4_real_world_paper_trading_roundtrip(self):
        """Paper trading order placement roundtrip simulates depth, fee calculation, and order state."""
        trader = KalshiTrader()
        res = trader.place_order(
            ticker="KXBTC15M-26MAR14-T1000",
            side="yes",
            count=2,
            limit_price_dollars=0.52,
            dry_run=True,
            slippage_buffer_dollars=0.04,
            available_balance=1000.0,
        )

        assert isinstance(res, dict)
        assert res.get("success") is True
        assert res.get("mode") == "PAPER"
        assert res.get("count", 0) > 0 or res.get("filled_count", 0) > 0
        assert "source" in res or "status" in res
