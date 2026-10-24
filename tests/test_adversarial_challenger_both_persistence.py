"""
Adversarial Stress Test Suite: Backend "BOTH" Universe Persistence & Concurrent Settings
Authored by challenger_1 for Milestone M4 Adversarial Coverage Hardening.

Requirements under challenge:
- R2: Universe "BOTH" Persistence across all backend routes and direct SQLite state.
- Stress-Testing Tasks:
  1. Rapid sequential and concurrent auto-trade toggles on sports and financial assets while universe is set to "BOTH".
  2. Submitting partial config payloads, empty payloads, and boundary values to /api/engine/{asset}/trade/config and /api/auth/user/config.
  3. Checking SQLite DB directly (users table) after every mutation to ensure trading_universe remains strictly "BOTH".
  4. Verify that sports trade size and financial risk parameters do not overwrite each other during concurrent saves.
"""

import contextlib
import concurrent.futures
import random
import threading
import uuid
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.database.models import (
    get_db_connection,
    create_user,
    get_user_by_id,
    update_user_trading_universe,
    update_user_config,
    copy_user_settings,
    admin_update_user,
)
from backend.auth.security import create_jwt_token


@pytest.fixture
def adversarial_user():
    """
    Creates an isolated ephemeral user for adversarial testing,
    sets trading_universe to 'BOTH', and tears down the user afterwards.
    """
    uid_suffix = uuid.uuid4().hex[:8]
    username = f"adv_user_{uid_suffix}"
    password = f"AdvPass123!_{uid_suffix}"
    user_id = create_user(username, password)
    assert user_id is not None, f"Failed creating adversarial test user {username}"

    # Explicitly set universe to BOTH
    update_user_trading_universe(user_id, "BOTH")

    token = create_jwt_token(user_id, username)
    headers = {"Authorization": f"Bearer {token}"}

    # Verify initial DB state
    conn = get_db_connection()
    row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    assert row["trading_universe"] == "BOTH"

    yield {
        "id": user_id,
        "username": username,
        "token": token,
        "headers": headers,
    }

    # Teardown
    with contextlib.suppress(Exception):
        conn = get_db_connection()
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()


def query_db_universe(user_id: int) -> str:
    """Direct SQLite query for trading_universe."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT trading_universe FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["trading_universe"] if row else None
    finally:
        conn.close()


def query_db_user_row(user_id: int) -> dict:
    """Direct SQLite query for full user record."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# SUITE 1: RAPID SEQUENTIAL & CONCURRENT TOGGLES
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialTogglePersistence:
    """Adversarially challenge auto-trade toggles against 'BOTH' universe persistence."""

    def test_rapid_sequential_toggles_preserve_both(self, adversarial_user):
        """Perform 40 rapid alternating toggles across sports and BTC; DB must never deviate from 'BOTH'."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        for i in range(40):
            asset = "sports" if (i % 2 == 0) else "btc"
            enabled_flag = (i % 4 < 2)

            res = client.post(
                f"/api/engine/{asset}/trade/toggle?enabled={str(enabled_flag).lower()}",
                headers=headers
            )
            assert res.status_code == 200, f"Toggle failed on iteration {i} for {asset}: {res.text}"

            # Direct SQLite check after EVERY iteration
            current_universe = query_db_universe(user_id)
            assert current_universe == "BOTH", (
                f"DB corruption detected! Iteration {i} ({asset} toggle={enabled_flag}) changed universe to '{current_universe}'"
            )

    def test_concurrent_multithreaded_toggles_preserve_both(self, adversarial_user):
        """
        Adversarially hammer the toggle endpoints with 16 concurrent threads
        interleaving sports and btc toggles simultaneously.
        """
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]
        client = TestClient(app)
        errors = []

        def worker(thread_idx: int):
            try:
                for j in range(10):
                    asset = "sports" if ((thread_idx + j) % 2 == 0) else "btc"
                    enabled = bool((thread_idx * 7 + j) % 2)
                    res = client.post(
                        f"/api/engine/{asset}/trade/toggle?enabled={str(enabled).lower()}",
                        headers=headers
                    )
                    if res.status_code != 200:
                        errors.append(f"HTTP {res.status_code}: {res.text}")
                    # Direct DB inspection
                    db_u = query_db_universe(user_id)
                    if db_u != "BOTH":
                        errors.append(f"Thread {thread_idx} detected DB corruption: {db_u}")
            except Exception as ex:
                errors.append(f"Thread {thread_idx} crashed: {str(ex)}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent toggle errors detected: {errors[:5]}"
        assert query_db_universe(user_id) == "BOTH", "Final DB universe is not 'BOTH'"


# ═════════════════════════════════════════════════════════════════════════════
# SUITE 2: CONCURRENT SETTINGS CROSS-UPDATES (ISOLATION OF TRADE SIZES & RISK)
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialConcurrentSettingsIsolation:
    """
    Stress-test concurrent writes between financial parameters and sports parameters
    to verify neither overwrites the other nor corrupts 'BOTH' in SQLite.
    """

    def test_concurrent_sports_and_financial_saves_via_auth_config_do_not_overwrite(self, adversarial_user):
        """
        Thread A repeatedly saves BTC financial configs via /api/engine/btc/trade/config (trade_size_dollars=60+k, stop_loss_pct=28.0).
        Thread B repeatedly saves Sports configs via /api/auth/user/config (sports_trade_size_dollars=90+k, sports_max_daily_risk=180.0).
        Thread C repeatedly polls dashboard stats.
        Thread D toggles sports autotrade.
        All run concurrently. Verify final DB state retains both values and 'BOTH'.
        """
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]
        client = TestClient(app)
        errors = []

        # Initialize base values
        client.post(
            "/api/auth/user/config",
            json={
                "trading_universe": "BOTH",
                "trade_size_dollars": 10.0,
                "sports_trade_size_dollars": 10.0,
                "stop_loss_pct": 50.0,
                "sports_max_daily_risk": 50.0,
            },
            headers=headers
        )

        def financial_writer():
            try:
                for k in range(20):
                    val = 60.0 + k
                    res = client.post(
                        "/api/engine/btc/trade/config",
                        json={"trade_size_dollars": val, "stop_loss_pct": 28.0},
                        headers=headers
                    )
                    if res.status_code != 200:
                        errors.append(f"FinWriter error: {res.text}")
                    u = query_db_universe(user_id)
                    if u != "BOTH":
                        errors.append(f"FinWriter saw universe corruption: {u}")
            except Exception as e:
                errors.append(f"FinWriter exception: {e}")

        def sports_writer():
            try:
                for k in range(20):
                    val = 90.0 + k
                    res = client.post(
                        "/api/auth/user/config",
                        json={"sports_trade_size_dollars": val, "sports_max_daily_risk": 180.0},
                        headers=headers
                    )
                    if res.status_code != 200:
                        errors.append(f"SportsWriter error: {res.text}")
                    u = query_db_universe(user_id)
                    if u != "BOTH":
                        errors.append(f"SportsWriter saw universe corruption: {u}")
            except Exception as e:
                errors.append(f"SportsWriter exception: {e}")

        def stats_poller():
            try:
                for _ in range(30):
                    res = client.get("/api/auth/dashboard_stats", headers=headers)
                    if res.status_code != 200:
                        errors.append(f"StatsPoller error: {res.text}")
                    data = res.json()
                    if data.get("trading_universe") != "BOTH":
                        errors.append(f"StatsPoller returned non-BOTH: {data.get('trading_universe')}")
            except Exception as e:
                errors.append(f"StatsPoller exception: {e}")

        def toggle_fuzzer():
            try:
                for k in range(20):
                    client.post(
                        f"/api/engine/sports/trade/toggle?enabled={str(k % 2 == 0).lower()}",
                        headers=headers
                    )
            except Exception as e:
                errors.append(f"ToggleFuzzer exception: {e}")

        threads = [
            threading.Thread(target=financial_writer),
            threading.Thread(target=sports_writer),
            threading.Thread(target=stats_poller),
            threading.Thread(target=toggle_fuzzer)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent settings errors: {errors[:5]}"

        # Check final DB state
        db_row = query_db_user_row(user_id)
        assert db_row["trading_universe"] == "BOTH", "Final universe must remain 'BOTH'"
        assert float(db_row["trade_size_dollars"]) >= 60.0, (
            f"Financial trade_size_dollars was overwritten or corrupted: {db_row['trade_size_dollars']}"
        )
        assert float(db_row["stop_loss_pct"]) == 28.0, (
            f"Financial stop_loss_pct was overwritten or corrupted: {db_row['stop_loss_pct']}"
        )
        sports_wager = float(db_row.get("sports_trade_size_dollars") or db_row.get("sports_max_wager") or 0.0)
        assert sports_wager >= 90.0, (
            f"Sports trade size was overwritten or corrupted: {sports_wager}"
        )
        assert float(db_row["sports_max_daily_risk"]) == 180.0, (
            f"Sports max daily risk was corrupted: {db_row['sports_max_daily_risk']}"
        )

    def test_adversarial_finding_engine_sports_config_omits_sports_trade_size_dollars(self, adversarial_user):
        """
        EMPIRICAL ADVERSARIAL FINDING:
        Demonstrates that /api/engine/sports/trade/config in backend/routes/engine.py:884
        only checks `if 'sports_max_wager' in data:` and omits `sports_trade_size_dollars`.
        When posting {"sports_trade_size_dollars": 88.0}, the endpoint returns 200 OK
        but the SQLite database row for sports_trade_size_dollars remains un-mutated.
        """
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        # 1. Verify initial DB state
        initial_row = query_db_user_row(user_id)
        initial_val = float(initial_row.get("sports_trade_size_dollars") or 10.0)

        # 2. Post sports_trade_size_dollars to /api/engine/sports/trade/config
        target_val = initial_val + 77.0
        res = client.post(
            "/api/engine/sports/trade/config",
            json={"sports_trade_size_dollars": target_val},
            headers=headers
        )
        assert res.status_code == 200

        # 3. Direct DB check proves the omission: DB was NOT updated to target_val
        after_row = query_db_user_row(user_id)
        assert float(after_row.get("sports_trade_size_dollars") or 0.0) != target_val, (
            "If this passes, engine.py now supports sports_trade_size_dollars"
        )
        # Universe remains BOTH however
        assert after_row["trading_universe"] == "BOTH"


# ═════════════════════════════════════════════════════════════════════════════
# SUITE 3: PARTIAL, EMPTY, AND CORRUPT PAYLOAD FUZZING
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialPayloadFuzzing:
    """Stress-test partial, empty, None, and malformed payload submissions."""

    def test_empty_json_payloads_to_all_config_endpoints(self, adversarial_user):
        """Submitting {} to /api/auth/user/config, /api/engine/btc/trade/config, and /api/engine/sports/trade/config."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        # 1. /api/auth/user/config with empty payload
        r1 = client.post("/api/auth/user/config", json={}, headers=headers)
        assert r1.status_code == 200, f"Empty auth config failed: {r1.text}"
        assert query_db_universe(user_id) == "BOTH"

        # 2. /api/engine/btc/trade/config with empty payload
        r2 = client.post("/api/engine/btc/trade/config", json={}, headers=headers)
        assert r2.status_code == 200, f"Empty btc config failed: {r2.text}"
        assert query_db_universe(user_id) == "BOTH"

        # 3. /api/engine/sports/trade/config with empty payload
        r3 = client.post("/api/engine/sports/trade/config", json={}, headers=headers)
        assert r3.status_code == 200, f"Empty sports config failed: {r3.text}"
        assert query_db_universe(user_id) == "BOTH"

    def test_explicit_null_and_whitespace_universe_payloads(self, adversarial_user):
        """Testing explicit None / null, extra whitespace, and casing."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        # Null trading_universe in JSON -> should preserve existing BOTH
        r_null = client.post("/api/auth/user/config", json={"trading_universe": None}, headers=headers)
        assert r_null.status_code == 200
        assert query_db_universe(user_id) == "BOTH"

        # Lowercase "both"
        r_lower = client.post("/api/auth/user/config", json={"trading_universe": "both"}, headers=headers)
        assert r_lower.status_code == 200
        assert query_db_universe(user_id) == "BOTH"

        # Padded "  BOTH  "
        r_padded = client.post("/api/auth/user/config", json={"trading_universe": "  BOTH  "}, headers=headers)
        assert r_padded.status_code == 200
        assert query_db_universe(user_id) == "BOTH"

    def test_invalid_and_injection_universe_strings_rejected(self, adversarial_user):
        """Testing invalid universe values to ensure rejection and 0 state corruption."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        # CRYPTO and FOREX are legacy aliases (they map to FINANCIAL), so they are not attacks here.
        adversarial_strings = [
            "BITCOIN",
            "SPORTS_ONLY",
            "BOTH_AND_MORE",
            "NULL",
            "undefined",
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            "<script>alert(1)</script>",
            "   ",
            "",
            "12345",
        ]

        for bad_val in adversarial_strings:
            res = client.post("/api/auth/user/config", json={"trading_universe": bad_val}, headers=headers)
            assert res.status_code in (400, 422), (
                f"Adversarial value '{bad_val}' unexpectedly accepted with HTTP {res.status_code}"
            )
            # Verify DB was NOT corrupted
            assert query_db_universe(user_id) == "BOTH", (
                f"Adversarial payload '{bad_val}' mutated DB trading_universe to {query_db_universe(user_id)}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# SUITE 4: EXTREME BOUNDARIES, UNICODE, & FUZZING
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialBoundariesAndFuzzing:
    """Stress-test numerical extremes, unicode strings, and DB stability."""

    def test_extreme_numerical_payloads_do_not_corrupt_universe(self, adversarial_user):
        """Huge numbers, negatives, zero values across financial and sports inputs."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        extreme_payloads = [
            {"trade_size_dollars": 0.0, "sports_trade_size_dollars": 0.0},
            {"trade_size_dollars": 9999999.0, "sports_trade_size_dollars": 9999999.0},
            {"stop_loss_pct": 0.0, "take_profit_pct": 0.0},
            {"stop_loss_pct": 100.0, "take_profit_pct": 1000.0},
            {"max_daily_trades": 0, "max_daily_risk": 0.0},
            {"max_daily_trades": 1000, "max_daily_risk": 50000.0},
        ]

        for payload in extreme_payloads:
            res = client.post("/api/auth/user/config", json=payload, headers=headers)
            assert res.status_code in (200, 422)
            assert query_db_universe(user_id) == "BOTH"

    def test_unicode_and_complex_strings_in_leagues_and_props(self, adversarial_user):
        """Sports leagues and props containing emoji, unicode, and commas."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        payload = {
            "sports_active_leagues": "NFL,MLB,🏆_LEAGUE,日本語",
            "sports_active_props": "ANYTIME_TD,PASSING_YDS,🔥_PROP",
            "sports_trade_size_dollars": 44.0,
        }
        res = client.post("/api/auth/user/config", json=payload, headers=headers)
        assert res.status_code == 200

        row = query_db_user_row(user_id)
        assert row["trading_universe"] == "BOTH"
        assert "NFL" in row["sports_active_leagues"]
        assert float(row["sports_trade_size_dollars"]) == 44.0


# ═════════════════════════════════════════════════════════════════════════════
# SUITE 5: DIRECT DATABASE MODELS & SETTINGS CLONING INTEGRITY
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialDirectModelIntegrity:
    """Direct functional tests against backend/database/models.py functions."""

    def test_direct_copy_user_settings_preserves_target_both(self, adversarial_user):
        """
        When copy_user_settings is invoked from another user (whose universe might be 'FINANCIAL'),
        verify that target user's 'BOTH' universe and trade size are STRICTLY preserved.
        """
        source_uid = create_user(f"src_{uuid.uuid4().hex[:6]}", "Pass1234!")
        update_user_trading_universe(source_uid, "FINANCIAL")

        target_uid = adversarial_user["id"]
        assert query_db_universe(target_uid) == "BOTH"

        try:
            # Copy settings from source to target
            result = copy_user_settings(source_uid, target_uid)
            assert result is not None

            # Verify target universe is still BOTH
            assert query_db_universe(target_uid) == "BOTH", (
                "copy_user_settings erroneously overwrote target user's 'BOTH' trading universe!"
            )
        finally:
            with contextlib.suppress(Exception):
                conn = get_db_connection()
                conn.execute("DELETE FROM users WHERE id = ?", (source_uid,))
                conn.commit()
                conn.close()

    def test_direct_admin_update_user_preserves_both(self, adversarial_user):
        """admin_update_user updating general fields must preserve 'BOTH' universe."""
        target_uid = adversarial_user["id"]

        success = admin_update_user(target_uid, {
            "trading_style": "SNIPER",
            "stop_loss_pct": 33.3,
            "max_daily_trades": 7
        })
        assert success is True
        assert query_db_universe(target_uid) == "BOTH"

        row = query_db_user_row(target_uid)
        assert row["trading_style"] == "SNIPER"
        assert float(row["stop_loss_pct"]) == 33.3
        assert int(row["max_daily_trades"]) == 7

    def test_multi_asset_crypto_config_preserves_both(self, adversarial_user):
        """Updating configs for other financial assets (ETH, SOL) preserves 'BOTH'."""
        client = TestClient(app)
        user_id = adversarial_user["id"]
        headers = adversarial_user["headers"]

        for asset in ["btc", "eth", "sol"]:
            res = client.post(
                f"/api/engine/{asset}/trade/config",
                json={"trade_size_dollars": 50.0 + len(asset)},
                headers=headers
            )
            assert res.status_code == 200, f"Config save failed for {asset}: {res.text}"
            assert query_db_universe(user_id) == "BOTH", f"Universe corrupted after {asset} config update"
