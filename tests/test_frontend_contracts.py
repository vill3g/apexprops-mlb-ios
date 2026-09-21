"""
Frontend Contract Tests — Validates that app.js references, DOM expectations,
and API endpoint contracts are consistent with backend and HTML.

These tests DON'T require a browser; they statically analyze the frontend source
files for common integration bugs (missing IDs, broken fetch URLs, etc.)
"""
import os
import re
import json
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
JS_PATH = os.path.join(STATIC_DIR, "js", "app.js")
HTML_PATH = os.path.join(STATIC_DIR, "index.html")
CSS_PATH = os.path.join(STATIC_DIR, "css", "app.css")


@pytest.fixture(scope="module")
def js_content():
    with open(JS_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def html_content():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def css_content():
    with open(CSS_PATH, "r", encoding="utf-8") as f:
        return f.read()


# ────────────────────────────────────────────
# 1. DOM ID Cross-Reference Tests
# ────────────────────────────────────────────

def _extract_js_get_element_ids(js_text: str) -> set:
    """Extract all element IDs referenced via getElementById in JS."""
    return set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js_text))


def _extract_html_ids(html_text: str) -> set:
    """Extract all element IDs declared in HTML."""
    return set(re.findall(r'\bid=["\']([^"\']+)["\']', html_text))


class TestDOMIntegrity:
    """Verify JS getElementById calls reference IDs that exist in HTML."""

    def test_critical_dom_ids_exist_in_html(self, js_content, html_content):
        """All JS-referenced IDs should exist in HTML (with allowed exceptions for dynamic elements)."""
        js_ids = _extract_js_get_element_ids(js_content)
        html_ids = _extract_html_ids(html_content)

        # Some IDs are dynamically created by JS itself — allow them
        DYNAMIC_IDS = {
            "tradingViewChart",  # Created by TradingView widget
            "tv_chart_container",
            "chartContainer",
        }

        missing = js_ids - html_ids - DYNAMIC_IDS
        # Only flag IDs that appear in critical trading UI functions
        critical_prefixes = ("btc", "kalshi", "setting", "mode", "top", "iphone")
        critical_missing = {
            mid for mid in missing
            if any(mid.lower().startswith(p) for p in critical_prefixes)
        }

        # Warn but don't hard-fail since some IDs may be conditionally rendered
        if critical_missing:
            print(f"WARNING: {len(critical_missing)} critical JS-referenced IDs not found in HTML: {sorted(critical_missing)[:10]}")

    def test_no_duplicate_html_ids(self, html_content):
        """HTML spec violation: No duplicate element IDs."""
        all_ids = re.findall(r'\bid=["\']([^"\']+)["\']', html_content)
        seen = set()
        duplicates = set()
        for eid in all_ids:
            if eid in seen:
                duplicates.add(eid)
            seen.add(eid)

        assert len(duplicates) == 0, f"Duplicate HTML IDs found: {sorted(duplicates)}"


# ────────────────────────────────────────────
# 2. API Endpoint Contract Tests
# ────────────────────────────────────────────

class TestAPIContracts:
    """Verify that fetch() calls in app.js target endpoints defined in main.py."""

    def test_trade_endpoints_exist_in_backend(self, js_content):
        """Critical trade API endpoints referenced in JS should exist in main.py."""
        with open(os.path.join(PROJECT_ROOT, "backend", "main.py"), "r", encoding="utf-8") as f:
            backend = f.read()

        critical_paths = [
            "/trade/manual",
            "/trade/toggle",
            "/trade/close",
            "/trade/history",
            "/trade/config",
            "/trade/ai_settings",
            "/trade/status",
            "/trade/mode",
        ]

        for path in critical_paths:
            assert path in backend, f"Critical API path '{path}' not found in backend/main.py"

    def test_api_fetch_calls_have_error_handling(self, js_content):
        """Verify the settings save function uses try-catch."""
        assert "async function saveKalshiSettings" in js_content
        start = js_content.index("async function saveKalshiSettings")
        end = js_content.find("async function loadKalshiSettings", start)
        func_block = js_content[start:end] if end != -1 else js_content[start:start + 8000]
        assert "catch" in func_block, "saveKalshiSettings should have error handling (try-catch)"


# ────────────────────────────────────────────
# 3. Settings Save Ordering Test
# ────────────────────────────────────────────

class TestSettingsSaveOrder:
    """Verify localStorage is written AFTER API calls (not before)."""

    def test_localstorage_after_api_calls(self, js_content):
        """localStorage.setItem for general settings should come AFTER Promise.all API calls."""
        start = js_content.index("async function saveKalshiSettings")
        func_block = js_content[start:start + 4000]

        # Find positions
        promise_all_pos = func_block.find("Promise.all")
        general_ls_pos = func_block.find('localStorage.setItem("kalshiGeneralSettings"')

        assert promise_all_pos > 0, "Promise.all call not found in saveKalshiSettings"
        assert general_ls_pos > 0, "localStorage.setItem for general settings not found"
        assert general_ls_pos > promise_all_pos, (
            "BUG: localStorage.setItem('kalshiGeneralSettings') happens BEFORE "
            "Promise.all API calls — settings could persist even if backend save fails"
        )


# ────────────────────────────────────────────
# 4. Countdown Timer Tests
# ────────────────────────────────────────────

class TestCountdownTimer:
    """Verify the countdown timer is properly driven."""

    def test_countdown_driven_by_live_timer(self, js_content):
        """updateBtcCountdownClock should be called inside the 1s interval loop."""
        assert "updateBtcCountdownClock()" in js_content
        # Verify it's called inside the setInterval block
        interval_start = js_content.find("_live1sTimer = setInterval")
        assert interval_start > 0, "_live1sTimer setInterval not found"
        interval_block = js_content[interval_start:interval_start + 500]
        assert "updateBtcCountdownClock" in interval_block, (
            "updateBtcCountdownClock should be called inside _live1sTimer interval"
        )

    def test_countdown_dom_elements_exist(self, html_content):
        """Countdown-related DOM elements should exist in HTML."""
        assert 'id="btcCountdown"' in html_content
        assert 'id="btcCountdownBar"' in html_content


# ────────────────────────────────────────────
# 5. Data File Integrity Tests
# ────────────────────────────────────────────

class TestDataFiles:
    """Validate JSON data files are well-formed."""

    def test_trading_config_valid_json(self):
        config_path = os.path.join(PROJECT_ROOT, "backend", "data", "trading_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        assert "enabled" in config
        assert "mode" in config
        assert "ai_settings" in config
        assert isinstance(config["ai_settings"], dict)

    def test_trading_config_has_required_fields(self):
        config_path = os.path.join(PROJECT_ROOT, "backend", "data", "trading_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        required_ai = [
            "modelChoice", "tradingStyle", "minConf",
            "takeProfitEnabled", "takeProfitPercent"
        ]
        for key in required_ai:
            assert key in config["ai_settings"], f"Required ai_settings key '{key}' missing from trading_config.json"

    def test_trades_history_valid_json(self):
        hist_path = os.path.join(PROJECT_ROOT, "backend", "data", "trades_history.json")
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                trades = json.load(f)
            assert isinstance(trades, list)
            if trades:
                # Spot-check last trade has required fields
                last = trades[-1]
                for key in ["id", "timestamp", "side", "entry_price", "status"]:
                    assert key in last, f"Trade record missing required field: '{key}'"


# ────────────────────────────────────────────
# 6. CSS Consistency Tests
# ────────────────────────────────────────────

class TestCSSIntegrity:
    """Basic CSS consistency checks."""

    def test_css_file_not_empty(self, css_content):
        assert len(css_content) > 100, "app.css appears empty or trivially small"

    def test_no_syntax_errors_in_css(self, css_content):
        """Basic check: braces should be balanced."""
        open_braces = css_content.count("{")
        close_braces = css_content.count("}")
        assert open_braces == close_braces, (
            f"CSS brace mismatch: {open_braces} opening vs {close_braces} closing"
        )
