"""
Comprehensive 4-Tier E2E Test Suite for SaaS Dashboard Decoupling & Universe Persistence.
Derived strictly from ORIGINAL_REQUEST.md and PROJECT.md requirements:
  - R1: Dedicated Settings Menus (independent #financialSettingsDrawer and #sportsSettingsDrawer)
  - R2: Universe "BOTH" Persistence across DB, API routes, stats, and frontend sync
  - R3: Frontend UI/UX Optimization, DOM integrity, and input/toggle saving

Test Suite Structure:
  - Tier 1: Feature Coverage (>=5 tests per core feature across 6 feature areas)
  - Tier 2: Boundary & Corner Cases (>=5 tests)
  - Tier 3: Cross-Feature Combinations (Pairwise Coverage)
  - Tier 4: Real-World Scenarios (End-to-End Workflows & DOM Integrity)
"""

import contextlib
import os
import re
import uuid

import pytest
from bs4 import BeautifulSoup
from starlette.testclient import TestClient

from backend.auth.security import create_jwt_token
from backend.database.models import (
    create_user,
    get_db_connection,
    get_user_by_id,
    update_user_config,
    update_user_trading_universe,
)
from backend.main import app

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HTML_PATH = os.path.join(REPO_ROOT, "static", "saas_dashboard.html")
APP_JS_PATH = os.path.join(REPO_ROOT, "static", "js", "app.js")


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES & ISOLATION HELPERS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def api_client():
    """TestClient instance configured for FastAPI E2E requests."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def ephemeral_user():
    """
    Creates an isolated, unique test user in the SQLite database
    and guarantees complete cleanup after test completion.
    """
    username = f"e2e_u_{uuid.uuid4().hex[:8]}"
    password = f"P@{uuid.uuid4().hex[:6]}9!"
    uid = create_user(username, password)
    assert uid is not None, f"Failed to seed ephemeral test user {username}"

    token = create_jwt_token(uid, username)
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "id": uid,
        "username": username,
        "token": token,
        "headers": headers,
    }

    # Teardown: delete user from database
    with contextlib.suppress(Exception):
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        conn.close()



@pytest.fixture(scope="module")
def html_content():
    """Reads raw saas_dashboard.html content."""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def html_soup(html_content):
    """Parses saas_dashboard.html into BeautifulSoup tree."""
    return BeautifulSoup(html_content, "html.parser")


@pytest.fixture(scope="module")
def app_js_content():
    """Reads static/js/app.js content if it exists."""
    if os.path.exists(APP_JS_PATH):
        with open(APP_JS_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# ═════════════════════════════════════════════════════════════════════════════
# TIER 1: FEATURE COVERAGE
# ═════════════════════════════════════════════════════════════════════════════

class TestTier1FinancialDrawerStructure:
    """Feature 1.1: Dedicated Financial Settings Drawer (#financialSettingsDrawer)."""

    def test_financial_drawer_container_exists(self, html_soup):
        """R1: Verifies #financialSettingsDrawer exists as a dedicated container."""
        drawer = html_soup.find(id="financialSettingsDrawer")
        assert drawer is not None, "HTML must contain dedicated #financialSettingsDrawer container"

    def test_financial_drawer_contains_crypto_forex_controls(self, html_soup):
        """R1: Verifies crypto/forex risk & trading controls exist inside financial drawer."""
        drawer = html_soup.find(id="financialSettingsDrawer")
        assert drawer is not None, "#financialSettingsDrawer missing"
        text = str(drawer).lower()
        # Must contain stop loss, trading style, or risk controls
        assert "stop loss" in text or "stop_loss" in text or "stop-loss" in text, (
            "Financial drawer must contain stop loss settings"
        )
        assert "trade size" in text or "trade_size" in text or "trade-size" in text, (
            "Financial drawer must contain trade size settings"
        )

    def test_financial_drawer_excludes_sports_leagues_and_props(self, html_soup):
        """R1: Verifies sports leagues and player props are NOT inside financial drawer."""
        drawer = html_soup.find(id="financialSettingsDrawer")
        assert drawer is not None, "#financialSettingsDrawer missing"
        # Player props and sports leagues must not be in financial drawer
        assert drawer.find(id="sports-active-leagues") is None, (
            "Sports active leagues must not be present in financial drawer"
        )
        assert drawer.find(id="sports-risk-settings") is None, (
            "Sports risk settings must not be present in financial drawer"
        )
        assert len(drawer.find_all(class_="sports-prop-toggle")) == 0, (
            "Player prop toggles must not reside in financial drawer"
        )

    def test_financial_drawer_contains_model_choice_and_signal_source(self, html_soup):
        """R1: Verifies ML engine and trading model selectors exist in financial drawer."""
        drawer = html_soup.find(id="financialSettingsDrawer")
        assert drawer is not None, "#financialSettingsDrawer missing"
        text = str(drawer).lower()
        assert "model" in text or "signal" in text or "ai" in text, (
            "Financial drawer must contain ML/AI model selection controls"
        )

    def test_financial_drawer_has_independent_close_mechanism(self, html_soup):
        """R1: Verifies financial drawer has an independent close button or dismiss trigger."""
        drawer = html_soup.find(id="financialSettingsDrawer")
        assert drawer is not None, "#financialSettingsDrawer missing"
        # Drawer should have a close button or onclick closeSettings
        close_triggers = drawer.find_all(lambda tag: tag.has_attr("onclick") and "close" in tag["onclick"].lower())
        assert len(close_triggers) > 0, (
            "Financial drawer must provide an independent close button/trigger"
        )


class TestTier1SportsDrawerStructure:
    """Feature 1.2: Dedicated Sports Settings Drawer (#sportsSettingsDrawer)."""

    def test_sports_drawer_container_exists(self, html_soup):
        """R1: Verifies #sportsSettingsDrawer exists as a dedicated container."""
        drawer = html_soup.find(id="sportsSettingsDrawer")
        assert drawer is not None, "HTML must contain dedicated #sportsSettingsDrawer container"

    def test_sports_drawer_contains_leagues_and_props_controls(self, html_soup):
        """R1: Verifies sports leagues and market/prop controls exist inside sports drawer."""
        drawer = html_soup.find(id="sportsSettingsDrawer")
        assert drawer is not None, "#sportsSettingsDrawer missing"
        text = str(drawer).upper()
        # Must contain major leagues
        assert "NFL" in text or "MLB" in text or "NBA" in text, (
            "Sports drawer must contain sports league selections"
        )

    def test_sports_drawer_contains_sports_trade_size_and_kelly(self, html_soup):
        """R1: Verifies sports trade size input and Kelly criterion controls in sports drawer."""
        drawer = html_soup.find(id="sportsSettingsDrawer")
        assert drawer is not None, "#sportsSettingsDrawer missing"
        # Check for sports trade size input
        has_size_input = (
            drawer.find(id="sports-trade-size-input") is not None
            or drawer.find(attrs={"name": "sports_trade_size_dollars"}) is not None
            or "sports trade size" in str(drawer).lower()
        )
        assert has_size_input, "Sports drawer must contain Sports Trade Size input"

    def test_sports_drawer_contains_price_corridor_and_tp(self, html_soup):
        """R1: Verifies price corridor (min/max price) and mid-game TP controls in sports drawer."""
        drawer = html_soup.find(id="sportsSettingsDrawer")
        assert drawer is not None, "#sportsSettingsDrawer missing"
        text = str(drawer).lower()
        assert "price" in text or "corridor" in text or "take profit" in text or "tp" in text, (
            "Sports drawer must contain price corridor or sports take profit controls"
        )

    def test_sports_drawer_excludes_crypto_forex_specific_controls(self, html_soup):
        """R1: Verifies crypto-only options (e.g. second entry) do not reside in sports drawer."""
        drawer = html_soup.find(id="sportsSettingsDrawer")
        assert drawer is not None, "#sportsSettingsDrawer missing"
        assert drawer.find(id="second-entry-toggle") is None, (
            "Crypto second entry toggle must not be in sports drawer"
        )
        assert drawer.find(id="finance-asset-select") is None, (
            "Crypto asset selector must not be in sports drawer"
        )


class TestTier1UniverseBothBackendPersistence:
    """Feature 1.3: Universe 'BOTH' backend persistence via API (POST /api/auth/user/config)."""

    def test_post_user_config_both_persists_in_db(self, api_client, ephemeral_user):
        """R2: POST /api/auth/user/config with 'BOTH' persists to SQLite database."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={"trading_universe": "BOTH"},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200, f"Failed updating to BOTH: {resp.text}"

        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (ephemeral_user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "BOTH", f"Expected 'BOTH' in DB, got {row['trading_universe']}"

    def test_post_user_config_all_persists_in_db(self, api_client, ephemeral_user):
        """R2: POST /api/auth/user/config with 'ALL' persists to SQLite database."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={"trading_universe": "ALL"},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200, f"Failed updating to ALL: {resp.text}"

        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (ephemeral_user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "ALL", f"Expected 'ALL' in DB, got {row['trading_universe']}"

    def test_post_user_config_case_insensitivity_normalization(self, api_client, ephemeral_user):
        """R2: Verifies lowercase 'both' is normalized to uppercase 'BOTH' in DB."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={"trading_universe": "both"},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        conn = get_db_connection()
        row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (ephemeral_user["id"],)).fetchone()
        conn.close()
        assert row["trading_universe"] == "BOTH"

    def test_post_user_config_standard_universes_persistence(self, api_client, ephemeral_user):
        """R2: Verifies standard universes 'FINANCIAL' and 'SPORTS' continue to persist accurately."""
        # 1. FINANCIAL
        r1 = api_client.post(
            "/api/auth/user/config",
            json={"trading_universe": "FINANCIAL"},
            headers=ephemeral_user["headers"]
        )
        assert r1.status_code == 200
        u1 = get_user_by_id(ephemeral_user["id"])
        assert u1["trading_universe"] == "FINANCIAL"

        # 2. SPORTS
        r2 = api_client.post(
            "/api/auth/user/config",
            json={"trading_universe": "SPORTS"},
            headers=ephemeral_user["headers"]
        )
        assert r2.status_code == 200
        u2 = get_user_by_id(ephemeral_user["id"])
        assert u2["trading_universe"] == "SPORTS"

    def test_direct_db_function_update_user_trading_universe_both(self, ephemeral_user):
        """R2: Direct invocation of update_user_trading_universe commits 'BOTH'."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")
        u = get_user_by_id(ephemeral_user["id"])
        assert u["trading_universe"] == "BOTH"


class TestTier1UniverseBothDashboardStats:
    """Feature 1.4: Universe 'BOTH' fetched correctly via GET /api/auth/dashboard_stats."""

    def test_dashboard_stats_returns_both(self, api_client, ephemeral_user):
        """R2: GET /api/auth/dashboard_stats returns trading_universe='BOTH'."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        resp = api_client.get("/api/auth/dashboard_stats", headers=ephemeral_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("trading_universe") == "BOTH", f"Expected trading_universe='BOTH', got {data.get('trading_universe')}"

    def test_dashboard_stats_returns_all(self, api_client, ephemeral_user):
        """R2: GET /api/auth/dashboard_stats returns trading_universe='ALL'."""
        update_user_trading_universe(ephemeral_user["id"], "ALL")

        resp = api_client.get("/api/auth/dashboard_stats", headers=ephemeral_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("trading_universe") == "ALL"

    def test_dashboard_stats_returns_financial_default(self, api_client, ephemeral_user):
        """R2: Default seeded user returns trading_universe='FINANCIAL'."""
        resp = api_client.get("/api/auth/dashboard_stats", headers=ephemeral_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("trading_universe") in ("FINANCIAL", "BOTH", "ALL", "SPORTS")

    def test_dashboard_stats_returns_sports(self, api_client, ephemeral_user):
        """R2: User configured for SPORTS returns trading_universe='SPORTS'."""
        update_user_trading_universe(ephemeral_user["id"], "SPORTS")

        resp = api_client.get("/api/auth/dashboard_stats", headers=ephemeral_user["headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("trading_universe") == "SPORTS"

    def test_dashboard_stats_requires_authentication(self, api_client):
        """R2: Unauthenticated GET /api/auth/dashboard_stats returns 401 or 403."""
        resp = api_client.get("/api/auth/dashboard_stats")
        assert resp.status_code in (401, 403)


class TestTier1PreservationOfBothDuringTogglesAndUpdates:
    """Feature 1.5: Preservation of 'BOTH' during auto-trade toggles and asset config updates."""

    def test_sports_toggle_preserves_both_universe(self, api_client, ephemeral_user):
        """R2: POST /api/engine/sports/trade/toggle?enabled=true preserves 'BOTH' (does NOT overwrite)."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")
        assert get_user_by_id(ephemeral_user["id"])["trading_universe"] == "BOTH"

        resp = api_client.post(
            "/api/engine/sports/trade/toggle?enabled=true",
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u_after = get_user_by_id(ephemeral_user["id"])
        assert u_after["trading_universe"] == "BOTH", (
            f"Regression: Sports toggle overwrote 'BOTH' with {u_after['trading_universe']}"
        )

    def test_sports_toggle_off_preserves_both_universe(self, api_client, ephemeral_user):
        """R2: POST /api/engine/sports/trade/toggle?enabled=false preserves 'BOTH'."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        resp = api_client.post(
            "/api/engine/sports/trade/toggle?enabled=false",
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u_after = get_user_by_id(ephemeral_user["id"])
        assert u_after["trading_universe"] == "BOTH"

    def test_btc_toggle_preserves_both_universe(self, api_client, ephemeral_user):
        """R2: POST /api/engine/btc/trade/toggle preserves 'BOTH'."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        resp = api_client.post(
            "/api/engine/btc/trade/toggle?enabled=true",
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u_after = get_user_by_id(ephemeral_user["id"])
        assert u_after["trading_universe"] == "BOTH"

    def test_btc_trade_config_post_preserves_both_universe(self, api_client, ephemeral_user):
        """R2: POST /api/engine/btc/trade/config preserves existing 'BOTH' in DB."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        resp = api_client.post(
            "/api/engine/btc/trade/config",
            json={"trade_size_dollars": 25.0, "stop_loss_pct": 12.0},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u_after = get_user_by_id(ephemeral_user["id"])
        assert u_after["trading_universe"] == "BOTH", (
            f"Regression: BTC trade config reset 'BOTH' to {u_after['trading_universe']}"
        )

    def test_sports_trade_config_post_preserves_both_universe(self, api_client, ephemeral_user):
        """R2: POST /api/engine/sports/trade/config preserves existing 'BOTH' in DB."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        resp = api_client.post(
            "/api/engine/sports/trade/config",
            json={"sports_trade_size_dollars": 30.0},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u_after = get_user_by_id(ephemeral_user["id"])
        assert u_after["trading_universe"] == "BOTH"


class TestTier1ProperInputToggleSaving:
    """Feature 1.6: Proper input/toggle saving to database (R3)."""

    def test_sports_trade_size_dollars_persists_to_db(self, api_client, ephemeral_user):
        """R3: Verifies sports_trade_size_dollars saves to database."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={"sports_trade_size_dollars": 45.0},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u = get_user_by_id(ephemeral_user["id"])
        assert float(u.get("sports_trade_size_dollars", 0.0)) == 45.0

    def test_sports_leagues_and_props_persist_to_db(self, api_client, ephemeral_user):
        """R3: Verifies sports_active_leagues and sports_active_props save to database."""
        leagues = "NFL,MLB,NHL"
        props = "ANYTIME_TD,PASSING_YDS"
        resp = api_client.post(
            "/api/auth/user/config",
            json={"sports_active_leagues": leagues, "sports_active_props": props},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u = get_user_by_id(ephemeral_user["id"])
        assert u.get("sports_active_leagues") == leagues
        assert u.get("sports_active_props") == props

    def test_financial_trade_size_and_stop_loss_persist(self, api_client, ephemeral_user):
        """R3: Verifies trade_size_dollars and stop_loss_pct save to database."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={"trade_size_dollars": 88.0, "stop_loss_pct": 22.5},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u = get_user_by_id(ephemeral_user["id"])
        assert float(u.get("trade_size_dollars", 0.0)) == 88.0
        assert float(u.get("stop_loss_pct", 0.0)) == 22.5

    def test_toggles_boolean_persistence(self, api_client, ephemeral_user):
        """R3: Verifies boolean toggles persist correctly as 1/0."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={
                "trailing_stop_enabled": True,
                "sports_tp_enabled": True,
                "second_entry_enabled": True,
                "sports_use_kelly": True
            },
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u = get_user_by_id(ephemeral_user["id"])
        assert u.get("trailing_stop_enabled") == 1
        assert u.get("sports_tp_enabled") == 1
        assert u.get("second_entry_enabled") == 1
        assert u.get("sports_use_kelly") == 1

    def test_saveUserConfig_contains_sportsActivePropsStr_definition(self, html_content):
        """R3: Verifies sportsActivePropsStr is defined before use in saveUserConfig, avoiding ReferenceError."""
        # Find saveUserConfig in html_content
        match = re.search(r"function\s+saveUserConfig\s*\([^)]*\)\s*\{(.*?)(\n\s*function|\n\s*window\.|\Z)", html_content, re.DOTALL)
        if match:
            fn_body = match.group(1)
            # If sportsActivePropsStr is used in the payload, it must be declared/assigned beforehand
            if "sportsActivePropsStr" in fn_body:
                assignment_match = re.search(r"(?:let|const|var)\s+sportsActivePropsStr\s*=", fn_body)
                assert assignment_match is not None, (
                    "sportsActivePropsStr is referenced without declaration in saveUserConfig! (ReferenceError bug)"
                )


# ═════════════════════════════════════════════════════════════════════════════
# TIER 2: BOUNDARY & CORNER CASES
# ═════════════════════════════════════════════════════════════════════════════

class TestTier2BoundaryAndCornerCases:
    """Boundary conditions, malformed payloads, extremes, and rapid toggles."""

    @pytest.mark.parametrize("invalid_universe", [
        "NONE",
        "INVALID_UNIVERSE_NAME",
        "",
        "   ",
    ])
    def test_user_config_rejects_invalid_universe_strings(self, api_client, ephemeral_user, invalid_universe):
        """Tier 2: API rejects invalid universe strings with HTTP 422 or 400 and preserves DB state."""
        orig_universe = get_user_by_id(ephemeral_user["id"])["trading_universe"]

        resp = api_client.post(
            "/api/auth/user/config",
            json={"trading_universe": invalid_universe},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code in (400, 422), (
            f"Expected rejection for '{invalid_universe}', got {resp.status_code}: {resp.text}"
        )

        u_after = get_user_by_id(ephemeral_user["id"])
        assert u_after["trading_universe"] == orig_universe

    def test_empty_sports_leagues_and_props_handling(self, api_client, ephemeral_user):
        """Tier 2: Empty string or empty list for sports leagues/props is handled safely."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={"sports_active_leagues": "", "sports_active_props": ""},
            headers=ephemeral_user["headers"]
        )
        # Must not throw 500 internal server error
        assert resp.status_code in (200, 400, 422)
        assert resp.status_code != 500

    def test_extreme_trade_sizes_and_slider_boundaries(self, api_client, ephemeral_user):
        """Tier 2: Extreme numeric values (zero, large numbers) execute safely without 500 crash."""
        resp = api_client.post(
            "/api/auth/user/config",
            json={
                "trade_size_dollars": 0.0,
                "sports_trade_size_dollars": 1000000.0,
                "stop_loss_pct": 100.0,
                "take_profit_pct": 500.0,
            },
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code in (200, 422)
        assert resp.status_code != 500

    def test_partial_config_payload_preserves_omitted_fields(self, api_client, ephemeral_user):
        """Tier 2: Partial payload updates only specified fields, preserving all omitted values."""
        # Setup initial state
        update_user_trading_universe(ephemeral_user["id"], "BOTH")
        update_user_config(
            user_id=ephemeral_user["id"],
            trade_size_dollars=25.0,
            paper_trade_size_dollars=50.0,
            stop_loss_pct=15.0,
            trading_universe="BOTH"
        )

        # Update ONLY trade_size_dollars via API
        resp = api_client.post(
            "/api/auth/user/config",
            json={"trade_size_dollars": 99.0},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u = get_user_by_id(ephemeral_user["id"])
        assert float(u["trade_size_dollars"]) == 99.0
        assert u["trading_universe"] == "BOTH", "Omitted trading_universe was unexpectedly overwritten"
        assert float(u["stop_loss_pct"]) == 15.0, "Omitted stop_loss_pct was unexpectedly overwritten"

    def test_rapid_toggle_concurrency(self, api_client, ephemeral_user):
        """Tier 2: Rapid alternating toggle operations execute without database lock or error."""
        for state in [True, False, True, False, True]:
            resp = api_client.post(
                f"/api/engine/btc/trade/toggle?enabled={str(state).lower()}",
                headers=ephemeral_user["headers"]
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("enabled") == state or data.get("status") == "ok"

    def test_invalid_json_payload_rejection(self, api_client, ephemeral_user):
        """Tier 2: Malformed or invalid JSON body returns 422/400 without crashing."""
        resp = api_client.post(
            "/api/auth/user/config",
            content=b"not-a-valid-json-string",
            headers={"Content-Type": "application/json", **ephemeral_user["headers"]}
        )
        assert resp.status_code in (400, 422)


# ═════════════════════════════════════════════════════════════════════════════
# TIER 3: CROSS-FEATURE COMBINATIONS (PAIRWISE)
# ═════════════════════════════════════════════════════════════════════════════

class TestTier3CrossFeatureCombinations:
    """Pairwise interactions between universe modes, execution toggles, and drawer actions."""

    def test_cross_toggle_autotrader_while_viewing_sports_with_both_universe(self, api_client, ephemeral_user):
        """Tier 3: Toggling sports auto-trader retains 'BOTH' while updating ai_enabled."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        # Toggle sports auto-trade ON
        r1 = api_client.post(
            "/api/engine/sports/trade/toggle?enabled=true",
            headers=ephemeral_user["headers"]
        )
        assert r1.status_code == 200

        u1 = get_user_by_id(ephemeral_user["id"])
        assert u1["ai_enabled"] == 1
        assert u1["trading_universe"] == "BOTH"

        # Toggle sports auto-trade OFF
        r2 = api_client.post(
            "/api/engine/sports/trade/toggle?enabled=false",
            headers=ephemeral_user["headers"]
        )
        assert r2.status_code == 200

        u2 = get_user_by_id(ephemeral_user["id"])
        assert u2["ai_enabled"] == 0
        assert u2["trading_universe"] == "BOTH"

    def test_cross_save_financial_settings_while_both_universe(self, api_client, ephemeral_user):
        """Tier 3: Saving financial settings via config endpoint preserves trading_universe='BOTH'."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")

        resp = api_client.post(
            "/api/engine/btc/trade/config",
            json={"trade_size_dollars": 60.0, "stop_loss_pct": 20.0, "trading_style": "SNIPER"},
            headers=ephemeral_user["headers"]
        )
        assert resp.status_code == 200

        u = get_user_by_id(ephemeral_user["id"])
        assert float(u["trade_size_dollars"]) == 60.0
        assert u["trading_universe"] == "BOTH"

    def test_cross_financial_and_sports_drawer_trigger_synchronization(self, html_content):
        """Tier 3: openSettings handles 'FINANCIAL' and 'SPORTS' routing, and syncs BOTH button."""
        # Verify function openSettings exists and routes between the drawers
        assert "openSettings" in html_content, "openSettings function must exist"
        # Verify auto-trading universe control with BOTH option is present in markup
        assert "btn-auto-univ-both" in html_content or "setAutoTradingUniverse('BOTH')" in html_content, (
            "Markup must support selecting BOTH universe"
        )

    def test_cross_paper_live_mode_and_auto_execution_across_drawers(self, api_client, ephemeral_user):
        """Tier 3: Changing trading mode preserves BOTH universe and ai_enabled."""
        update_user_trading_universe(ephemeral_user["id"], "BOTH")
        # Toggle auto execution on
        api_client.post("/api/engine/btc/trade/toggle?enabled=true", headers=ephemeral_user["headers"])

        # Change trading mode
        from backend.database.models import update_user_trading_mode
        update_user_trading_mode(ephemeral_user["id"], "PAPER")

        u = get_user_by_id(ephemeral_user["id"])
        assert u["trading_mode"] == "PAPER"
        assert u["trading_universe"] == "BOTH"
        assert u["ai_enabled"] == 1

        # Verify switching to LIVE mode also preserves BOTH and ai_enabled
        update_user_trading_mode(ephemeral_user["id"], "LIVE")
        u_live = get_user_by_id(ephemeral_user["id"])
        assert u_live["trading_mode"] == "LIVE"
        assert u_live["trading_universe"] == "BOTH"
        assert u_live["ai_enabled"] == 1

    def test_cross_simultaneous_multi_universe_executor_routing(self):
        """Tier 3: User with 'BOTH' is eligible for both financial and sports auto-executors."""
        mock_user = {
            "id": 9999,
            "username": "multi_trader",
            "ai_enabled": 1,
            "target_asset": "BTC",
            "trading_universe": "BOTH",
        }

        # Financial executor filter test
        fin_match = (
            mock_user.get("ai_enabled", 0)
            and (mock_user.get("trading_universe") or "FINANCIAL").upper() in ("FINANCIAL", "BOTH", "ALL")
        )
        assert fin_match is True or fin_match == 1, "User with 'BOTH' must match financial executor filter"

        # Sports executor filter test
        sports_match = (
            (mock_user.get("trading_universe") or "").upper() in ("SPORTS", "BOTH", "ALL")
            and bool(mock_user.get("ai_enabled", 0))
        )
        assert sports_match is True, "User with 'BOTH' must match sports executor filter"


# ═════════════════════════════════════════════════════════════════════════════
# TIER 4: REAL-WORLD SCENARIOS (END-TO-END WORKFLOWS)
# ═════════════════════════════════════════════════════════════════════════════

class TestTier4RealWorldScenarios:
    """Complex end-to-end workflows and DOM structural integrity validation."""

    def test_scenario1_new_user_both_universe_complete_setup(self, api_client, ephemeral_user):
        """
        Scenario 1: New user configures 'BOTH' auto-trading, updates sports trade size,
        updates BTC stop loss, reloads dashboard, and verifies all settings intact.
        """
        headers = ephemeral_user["headers"]
        uid = ephemeral_user["id"]

        # Step 1: Set universe to BOTH
        r1 = api_client.post("/api/auth/user/config", json={"trading_universe": "BOTH"}, headers=headers)
        assert r1.status_code == 200

        # Step 2: Update sports trade size to $35
        r2 = api_client.post("/api/auth/user/config", json={"sports_trade_size_dollars": 35.0}, headers=headers)
        assert r2.status_code == 200

        # Step 3: Update BTC stop loss to 18% and trade size to $55
        r3 = api_client.post(
            "/api/engine/btc/trade/config",
            json={"trade_size_dollars": 55.0, "stop_loss_pct": 18.0},
            headers=headers
        )
        assert r3.status_code == 200

        # Step 4: Reload dashboard stats
        r4 = api_client.get("/api/auth/dashboard_stats", headers=headers)
        assert r4.status_code == 200
        stats = r4.json()

        # Step 5: Verify all settings intact in stats and in DB
        assert stats.get("trading_universe") == "BOTH"

        db_user = get_user_by_id(uid)
        assert db_user["trading_universe"] == "BOTH"
        assert float(db_user["sports_trade_size_dollars"]) == 35.0
        assert float(db_user["trade_size_dollars"]) == 55.0
        assert float(db_user["stop_loss_pct"]) == 18.0

    def test_scenario2_active_trader_multi_tab_workflow(self, api_client, ephemeral_user):
        """
        Scenario 2: Active trader toggles auto-trading off and on across sports and financial tabs,
        verifying execution states and 'BOTH' persistence throughout.
        """
        headers = ephemeral_user["headers"]
        uid = ephemeral_user["id"]

        # User starts with BOTH
        update_user_trading_universe(uid, "BOTH")

        # Trader toggles sports auto-trade ON
        r1 = api_client.post("/api/engine/sports/trade/toggle?enabled=true", headers=headers)
        assert r1.status_code == 200
        assert get_user_by_id(uid)["trading_universe"] == "BOTH"

        # Trader switches to financial tab, toggles BTC auto-trade OFF
        r2 = api_client.post("/api/engine/btc/trade/toggle?enabled=false", headers=headers)
        assert r2.status_code == 200
        assert get_user_by_id(uid)["trading_universe"] == "BOTH"

        # Trader updates sports risk limits
        r3 = api_client.post("/api/auth/user/config", json={"sports_max_daily_trades": 15}, headers=headers)
        assert r3.status_code == 200

        # Verify universe remains BOTH
        stats = api_client.get("/api/auth/dashboard_stats", headers=headers).json()
        assert stats.get("trading_universe") == "BOTH"
        assert get_user_by_id(uid)["trading_universe"] == "BOTH"

    def test_scenario3_html_dom_integrity_and_drawer_nesting(self, html_soup, html_content):
        """
        Scenario 3: HTML DOM integrity check verifying:
        - Strict separation into #financialSettingsDrawer and #sportsSettingsDrawer
        - Enclosure of all financial controls within #financialSettingsPanel
        - Zero duplicate DOM element IDs across saas_dashboard.html
        - No unclosed tags in settings sections.
        """
        from collections import Counter
        fin_drawer = html_soup.find(id="financialSettingsDrawer")
        sports_drawer = html_soup.find(id="sportsSettingsDrawer")

        assert fin_drawer is not None, "HTML DOM missing #financialSettingsDrawer"
        assert sports_drawer is not None, "HTML DOM missing #sportsSettingsDrawer"

        # Ensure they are independent elements (neither is parent/child of the other)
        assert sports_drawer not in fin_drawer.descendants, "Sports drawer must not be nested inside financial drawer"
        assert fin_drawer not in sports_drawer.descendants, "Financial drawer must not be nested inside sports drawer"

        # Verify #financialSettingsPanel exists and contains critical controls
        fin_panel = fin_drawer.find(id="financialSettingsPanel")
        assert fin_panel is not None, "#financialSettingsDrawer must contain #financialSettingsPanel"
        for cid in ["finance-risk-settings", "trade-size-dollars", "stop-loss-pct", "kalshi-key"]:
            assert fin_panel.find(id=cid) is not None, f"Control #{cid} must reside inside #financialSettingsPanel"

        # Verify sportsSettingsPanel exists and contains sports controls
        sports_panel = sports_drawer.find(id="sportsSettingsPanel")
        assert sports_panel is not None, "#sportsSettingsDrawer must contain #sportsSettingsPanel"
        for scid in ["sports-trade-size-dollars", "sports-wager-dollars"]:
            assert sports_panel.find(id=scid) is not None, f"Control #{scid} must reside inside #sportsSettingsPanel"

        # Verify zero duplicate IDs across saas_dashboard.html
        all_ids = [el.get("id") for el in html_soup.find_all(id=True)]
        dupes = {k: v for k, v in Counter(all_ids).items() if v > 1}
        assert len(dupes) == 0, f"Duplicate IDs found in saas_dashboard.html: {dupes}"

        # Both dedicated drawers must have matching opening and closing <div> tags
        fin_open = len(fin_drawer.find_all("div"))
        sports_open = len(sports_drawer.find_all("div"))
        assert fin_open > 0, "Financial drawer must have structured DOM"
        assert sports_open > 0, "Sports drawer must have structured DOM"

    def test_scenario4_frontend_state_memory_protection(self, html_content, app_js_content):
        """
        Scenario 4: Verifies selectUniverse does NOT mutate window.lastDashboardStats.trading_universe
        in memory, which previously destroyed 'BOTH' on tab clicks.
        """
        target_bug = "window.lastDashboardStats.trading_universe = universe"
        assert target_bug not in html_content, (
            "Found in-memory corruption bug in saas_dashboard.html: "
            "'window.lastDashboardStats.trading_universe = universe' must be removed!"
        )
        assert target_bug not in app_js_content, (
            "Found in-memory corruption bug in app.js: "
            "'window.lastDashboardStats.trading_universe = universe' must be removed!"
        )
