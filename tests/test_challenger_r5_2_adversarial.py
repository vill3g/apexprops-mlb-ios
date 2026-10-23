"""
Adversarial Verification Suite by teamwork_preview_challenger_r5_2.
Stress-testing and empirical verification of:
- Objective 1: UI Decoupling (R3) & JS 429 Exponential Backoff (R4)
- Objective 2: KalshiTrader fail_fast=True Benchmark (< 50ms, 0 time.sleep on 429) (R4)
- Objective 3: Sports Trade DB Insertions & SQLite typeof(timestamp) == 'text' & ET Regex (R5)
"""

import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo
import pytest

from backend.btc.kalshi_trader import KalshiTrader, get_authenticated_trader_for_user
from backend.database.models import get_db_connection
from backend.database.trade_store import TradeStore, _trade_epoch
from backend.routes.engine_sports import _execute_sports_trade, _fetch_kalshi_series_events
from backend.sports_bridge.executor import SportsBridgeExecutor, _parse_trade_timestamp
from backend.sports.sports_executor import run_sports_executor


ET_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} (AM|PM) ET$")


# =============================================================================
# OBJECTIVE 1: UI DECOUPLING & JAVASCRIPT 429 BACKOFF LOGIC
# =============================================================================

def test_ui_tab_switching_is_strictly_decoupled():
    """Verify window.selectUniverse and toggleAutoTrader do NOT mutate trading_universe on the backend."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. selectUniverse
    start = html.find("window.selectUniverse = function(universe)")
    assert start != -1, "selectUniverse function missing"
    end = html.find("const SPORT_ICONS =", start)
    assert end != -1, "SPORT_ICONS boundary missing"
    select_body = html[start:end]

    assert "/api/auth/user/config" not in select_body, (
        "selectUniverse must not send POST /api/auth/user/config"
    )
    assert "trading_universe: universe" not in select_body, (
        "selectUniverse must not pass trading_universe payload"
    )

    # 2. toggleAutoTrader
    toggle_start = html.find("async function toggleAutoTrader(enabled)")
    assert toggle_start != -1, "toggleAutoTrader function missing"
    toggle_end = html.find("async function saveUserConfig()", toggle_start)
    assert toggle_end != -1, "saveUserConfig boundary missing"
    toggle_body = html[toggle_start:toggle_end]

    assert "targetUniverse" not in toggle_body, "toggleAutoTrader must not derive targetUniverse"
    assert "trading_universe" not in toggle_body, "toggleAutoTrader must not send trading_universe"
    assert "body: JSON.stringify({ ai_enabled: enabled })" in toggle_body

    # 3. Settings drawer explicit controls
    assert 'id="auto-trading-universe-container"' in html
    assert 'id="btn-auto-univ-crypto"' in html
    assert 'id="btn-auto-univ-sports"' in html
    assert 'id="btn-auto-univ-both"' in html
    assert "window.setAutoTradingUniverse" in html
    assert "window.configuredTradingUniverse" in html


def test_javascript_429_backoff_node_execution():
    """Run Node.js script to execute the extracted JS backoff logic and verify exponential doubling and reset."""
    node_script = """
    const fs = require('fs');
    const vm = require('vm');

    const html = fs.readFileSync('static/saas_dashboard.html', 'utf8');

    // Extract fetchLiveBids and timing constants
    const start = html.indexOf('let liveBidsIntervalMs = 800;');
    if (start === -1) throw new Error('liveBidsIntervalMs declaration not found');
    const end = html.indexOf('function hideChartLoader()', start);
    if (end === -1) throw new Error('hideChartLoader boundary not found');
    const snippet = html.slice(start, end);

    const delays = [];
    const mockContext = {
        document: { hidden: false },
        window: { isTabActive: true, currentAsset: 'BTC', API_BASE_URL: '' },
        lastBidTs: 0,
        bidsQueue: [],
        isProcessingBids: false,
        processBidsQueue: () => {},
        clearTimeout: () => {},
        setTimeout: (fn, ms) => {
            delays.push(ms);
            return 999;
        },
        console: { warn: () => {}, log: () => {}, error: () => {} }
    };

    let fakeStatus = 429;
    mockContext.fetch = async () => ({
        status: fakeStatus,
        ok: fakeStatus >= 200 && fakeStatus < 300,
        json: async () => ({ trades: [] })
    });

    vm.runInNewContext(snippet, mockContext);

    (async () => {
        // Run 8 consecutive 429 calls
        for (let i = 0; i < 8; i++) {
            await mockContext.fetchLiveBids();
        }

        // Run 1 200 OK call
        fakeStatus = 200;
        await mockContext.fetchLiveBids();

        // Run another 200 OK call
        await mockContext.fetchLiveBids();

        // Run a 500 Error call (non-429 error should not reset to 800 if not ok)
        fakeStatus = 500;
        await mockContext.fetchLiveBids();

        // Run a 429 call again (doubles from 800 to 1600)
        fakeStatus = 429;
        await mockContext.fetchLiveBids();

        console.log(JSON.stringify(delays));
    })();
    """

    res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    delays = json.loads(res.stdout.strip())

    # Expected delays:
    # 8 consecutive 429s starting from 800ms:
    # 1: 1600
    # 2: 3200
    # 3: 6400
    # 4: 12800
    # 5: 25600
    # 6: 30000 (capped at MAX_LIVE_BIDS_BACKOFF_MS)
    # 7: 30000
    # 8: 30000
    # then 200 OK:
    # 9: 800 (reset to BASE_LIVE_BIDS_INTERVAL_MS)
    # then 200 OK:
    # 10: 800
    # then 500 error:
    # 11: 800 (res.ok is false, not 429 -> does not change liveBidsIntervalMs)
    # then 429:
    # 12: 1600 (doubles from 800 to 1600)

    expected = [1600, 3200, 6400, 12800, 25600, 30000, 30000, 30000, 800, 800, 800, 1600]
    assert delays == expected, f"Delays mismatch: got {delays}, expected {expected}"


# =============================================================================
# OBJECTIVE 2: BENCHMARK KALSHITRADER WITH fail_fast=True (< 50ms, 0 time.sleep)
# =============================================================================

@pytest.mark.parametrize("method_name", ["get_balance", "get_positions", "place_order", "place_sports_order"])
def test_kalshi_trader_fail_fast_benchmark_under_50ms(method_name):
    """Empirically benchmark KalshiTrader methods with fail_fast=True under simulated 429."""
    kt = KalshiTrader(fail_fast=True)
    kt._sign_headers = MagicMock(return_value={"Authorization": "Bearer test"})

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = '{"error": "Too Many Requests"}'
    kt.session.get = MagicMock(return_value=mock_resp_429)
    kt.order_session.post = MagicMock(return_value=mock_resp_429)

    # For order placement, provide successful balance and positions so 429 hits the order endpoint directly
    if method_name in ("place_order", "place_sports_order"):
        kt.get_balance = MagicMock(return_value={
            "success": True,
            "balance_dollars": 500.0,
            "raw": {"balance_breakdown": [{"exchange_index": 0, "balance": 500.0}]}
        })
        kt.get_positions = MagicMock(return_value={"success": True, "positions": []})

    # Stub market dependencies for place_order / place_sports_order
    kt.get_active_15m_market = MagicMock(return_value={
        "ticker": "KXBTC15M-T", "strike_price": 80000.0, "yes_ask": 0.50, "no_ask": 0.50,
        "close_time": "2030-01-01T00:00:00Z"
    })
    kt.get_market_quote = MagicMock(return_value={
        "success": True,
        "market": {"ticker": "KXNFLGAME-T", "yes_ask_dollars": 0.50, "status": "active", "close_time": "2030-01-01T00:00:00Z"}
    })
    kt.get_exchange_breakdown = MagicMock(return_value={"success": True, "exchanges": [{"balance": 500.0}]})

    with patch("time.sleep") as mock_sleep:
        latencies = []
        # Run 50 iterations to benchmark distribution
        for _ in range(50):
            t_start = time.perf_counter()
            if method_name == "get_balance":
                res = kt.get_balance(force_refresh=True)
            elif method_name == "get_positions":
                res = kt.get_positions()
            elif method_name == "place_order":
                res = kt.place_order(ticker="KXBTC15M-T", side="yes", count=1, dry_run=False)
            elif method_name == "place_sports_order":
                res = kt.place_sports_order(ticker="KXNFLGAME-T", side="yes", count=1, limit_price_dollars=0.50, dry_run=False)
            t_end = time.perf_counter()

            elapsed_ms = (t_end - t_start) * 1000.0
            latencies.append(elapsed_ms)

            # Strict assertions per iteration
            assert res["success"] is False, f"Expected success=False on 429 in {method_name}"
            assert res.get("status_code") == 429, f"Expected status_code=429 in {method_name}"

        # Assertions across the benchmark run
        assert mock_sleep.call_count == 0, (
            f"time.sleep called {mock_sleep.call_count} times in {method_name} with fail_fast=True!"
        )
        max_latency = max(latencies)
        mean_latency = sum(latencies) / len(latencies)
        assert max_latency < 50.0, (
            f"{method_name} maximum latency was {max_latency:.2f}ms >= 50ms requirement"
        )
        assert mean_latency < 10.0, (
            f"{method_name} average latency was {mean_latency:.2f}ms >= 10ms"
        )


def test_kalshi_trader_fail_fast_on_balance_429_during_order():
    """Verify place_order and place_sports_order also fail fast (< 50ms, 0 sleeps) when balance query hits 429."""
    kt = KalshiTrader(fail_fast=True)
    kt._sign_headers = MagicMock(return_value={})
    mock_resp_429 = MagicMock(status_code=429, text='{"error": "Too Many Requests"}')
    kt.session.get = MagicMock(return_value=mock_resp_429)

    kt.get_active_15m_market = MagicMock(return_value={"ticker": "KXBTC15M-T", "yes_ask": 0.50})
    kt.get_market_quote = MagicMock(return_value={"success": True, "market": {"ticker": "KXNFL-T", "yes_ask_dollars": 0.50}})

    with patch("time.sleep") as mock_sleep:
        t0 = time.perf_counter()
        res_btc = kt.place_order(ticker="KXBTC15M-T", side="yes", count=1, dry_run=False)
        t_btc_ms = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        res_sports = kt.place_sports_order(ticker="KXNFL-T", side="yes", count=1, dry_run=False)
        t_sports_ms = (time.perf_counter() - t1) * 1000.0

        assert mock_sleep.call_count == 0
        assert t_btc_ms < 50.0
        assert t_sports_ms < 50.0
        assert res_btc["success"] is False
        assert "429" in res_btc["error"]
        assert res_sports["success"] is False
        assert "429" in res_sports["error"]


def test_kalshi_trader_adversarial_comparison_fail_fast_false_vs_true():
    """Adversarially prove that fail_fast=False retries and sleeps, while fail_fast=True does not."""
    # 1. With fail_fast=False
    kt_slow = KalshiTrader(fail_fast=False)
    kt_slow._sign_headers = MagicMock(return_value={})
    mock_resp_429 = MagicMock(status_code=429, text="Rate Limited")
    kt_slow.session.get = MagicMock(return_value=mock_resp_429)

    with patch("time.sleep") as mock_sleep:
        kt_slow.get_balance(force_refresh=True)
        # Should have slept and retried
        assert mock_sleep.call_count == 2, f"fail_fast=False should sleep 2 times on backoff, got {mock_sleep.call_count}"
        assert kt_slow.session.get.call_count == 3, "fail_fast=False should attempt 3 times"

    # 2. With fail_fast=True
    kt_fast = KalshiTrader(fail_fast=True)
    kt_fast._sign_headers = MagicMock(return_value={})
    kt_fast.session.get = MagicMock(return_value=mock_resp_429)

    with patch("time.sleep") as mock_sleep:
        kt_fast.get_balance(force_refresh=True)
        assert mock_sleep.call_count == 0, "fail_fast=True must sleep 0 times"
        assert kt_fast.session.get.call_count == 1, "fail_fast=True must attempt only 1 time"


def test_engine_series_events_no_sleep_on_429():
    """Verify _fetch_kalshi_series_events breaks immediately on 429 without sleeping."""
    mock_trader = MagicMock()
    mock_trader.is_authenticated.return_value = True
    mock_trader._sign_headers.return_value = {}
    mock_resp_429 = MagicMock(status_code=429, text="Rate limited")
    mock_trader.session.get.return_value = mock_resp_429

    with patch("backend.btc.kalshi_trader.kalshi_trader", mock_trader), \
         patch("time.sleep") as mock_sleep:
        t0 = time.perf_counter()
        events = _fetch_kalshi_series_events("KXTEST")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert elapsed_ms < 50.0
        assert mock_sleep.call_count == 0, "_fetch_kalshi_series_events must not sleep on 429"
        assert events == [] or isinstance(events, list)


# =============================================================================
# OBJECTIVE 3: SPORTS TRADE DATABASE INSERTIONS & SQLITE TIMESTAMP FORMAT/TYPE
# =============================================================================

def test_engine_sports_trade_insertion_sqlite_type_and_regex():
    """Insert sports trade via _execute_sports_trade and query SQLite directly to assert typeof and format."""
    fake_event_resp = MagicMock()
    fake_event_resp.status_code = 200
    fake_event_resp.json.return_value = {
        "event": {
            "markets": [{
                "ticker": "KXTEST-SPORT-MKT",
                "yes_ask_dollars": "0.55",
                "no_ask_dollars": "0.45",
                "last_price_dollars": "0.55",
                "status": "open",
                "title": "Test Team Wins",
                "yes_sub_title": "Test Team"
            }]
        }
    }

    pred = {
        "event_ticker": "KXTEST-SPORT-MKT",
        "predicted_team": "Test Team",
        "confidence_pct": 82.5,
        "edge_pct": 7.5,
        "sport": "NFL"
    }

    test_user_id = 1
    with patch("backend.routes.engine.requests.get", return_value=fake_event_resp):
        trade, err = _execute_sports_trade("KXTEST-SPORT-MKT", pred, user_id=test_user_id, trade_size=15.0)

    assert err is None, f"Execution failed: {err}"
    assert trade is not None
    trade_id = trade["id"]

    try:
        # Directly connect to SQLite using standard sqlite3 to inspect physical column storage
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, typeof(timestamp) FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None, f"Trade {trade_id} was not found in SQLite"
        raw_ts, ts_type = row[0], row[1]

        # Assertions
        assert ts_type == "text", f"typeof(timestamp) in SQLite must be 'text', got '{ts_type}'"
        assert isinstance(raw_ts, str), f"raw_ts must be str, got {type(raw_ts)}"
        assert ET_TIMESTAMP_REGEX.match(raw_ts), f"Timestamp '{raw_ts}' failed regex ^\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}} (AM|PM) ET$"
        assert raw_ts.endswith(" ET"), f"Timestamp '{raw_ts}' does not end with ' ET'"

        # Verify exact datetime parsing
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %I:%M:%S %p ET").replace(tzinfo=ZoneInfo("America/New_York"))
        assert dt.year == 2026, f"Expected year 2026, got {dt.year}"
        assert 1 <= dt.month <= 12
        assert 1 <= dt.day <= 31

    finally:
        # Cleanup
        conn = get_db_connection()
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()


def test_sports_bridge_executor_sqlite_type_and_regex():
    """Insert sports trade via SportsBridgeExecutor.run_cycle and query SQLite directly to assert typeof and format."""
    executor = SportsBridgeExecutor()
    today_code = datetime.now(ZoneInfo("America/New_York")).strftime("%y%b%d").upper()
    pick = {
        "sport": "NBA",
        "predicted_team": "Celtics",
        "confidence_pct": 78.0,
        "edge_pct": 6.0,
        "metadata": {"is_upcoming": True, "date": today_code}
    }
    user_conf = {
        "id": 1,
        "ai_enabled": 1,
        "trading_mode": "PAPER",
        "trading_universe": "BOTH",
        "min_sports_confidence": 60.0,
        "min_sports_edge": 2.0,
        "sports_trade_size_dollars": 25.0,
        "sports_max_wager": 30.0,
        "sports_min_price": 0.20,
        "sports_max_price": 0.80,
        "sports_max_daily_trades": 10,
        "sports_max_daily_risk": 200.0,
        "sports_active_leagues": "NBA",
        "sports_market_types": "GAME"
    }

    test_ticker = f"KXNBAGAME-{today_code}BOS-BOS"
    created_trades = []
    real_insert = TradeStore.insert_trade

    def spy_insert(user_id, t_dict):
        created_trades.append(t_dict)
        return real_insert(user_id, t_dict)

    with patch("backend.sports_bridge.executor._generate_kalshi_market", return_value=(test_ticker, 0.50, "Celtics Win")), \
         patch.object(executor.client, "fetch_latest_picks", return_value=[pick]), \
         patch("backend.sports_bridge.executor.get_all_active_users", return_value=[user_conf]), \
         patch("backend.sports_bridge.executor.requests.get", return_value=MagicMock(status_code=200, json=lambda: {"events": []})), \
         patch.object(executor, "_settle_open_trades", return_value=None), \
         patch("backend.database.trade_store.TradeStore.insert_trade", side_effect=spy_insert):
        executor.last_check = 0
        executor.run_cycle()

    assert len(created_trades) >= 1, "SportsBridgeExecutor failed to insert any trade"
    trade_id = created_trades[0]["id"]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, typeof(timestamp) FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None, f"Trade {trade_id} not found in SQLite"
        raw_ts, ts_type = row[0], row[1]

        assert ts_type == "text", f"typeof(timestamp) in SQLite must be 'text', got '{ts_type}'"
        assert isinstance(raw_ts, str)
        assert ET_TIMESTAMP_REGEX.match(raw_ts), f"Timestamp '{raw_ts}' failed regex"
        assert raw_ts.endswith(" ET")

    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()


def test_sports_standalone_executor_sqlite_type_and_regex():
    """Insert sports trade via run_sports_executor and query SQLite directly to assert typeof and format."""
    pred_data = [{
        "sport": "NHL",
        "predicted_team": "Bruins",
        "confidence_pct": 77.0,
        "edge_pct": 5.5,
        "metadata": {"is_upcoming": True, "date": "261006"},
        "status": "upcoming"
    }]
    mock_users = [{
        "id": 1,
        "trading_mode": "PAPER",
        "min_sports_confidence": 70.0,
        "min_sports_edge": 3.0,
        "sports_max_wager": 15.0,
        "sports_include_live": False
    }]

    created_trades = []
    real_insert = TradeStore.insert_trade

    def spy_insert(user_id, t_dict):
        created_trades.append(t_dict)
        return real_insert(user_id, t_dict)

    with patch("backend.sports.sports_executor.get_predictions", return_value=pred_data), \
         patch("backend.sports.sports_executor.get_all_active_users", return_value=mock_users), \
         patch("backend.database.trade_store.TradeStore.get_open_trades", return_value=[]), \
         patch("backend.database.trade_store.TradeStore.insert_trade", side_effect=spy_insert):
        run_sports_executor()

    assert len(created_trades) >= 1
    trade_id = created_trades[0]["id"]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, typeof(timestamp) FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        raw_ts, ts_type = row[0], row[1]

        assert ts_type == "text", f"typeof(timestamp) in SQLite must be 'text', got '{ts_type}'"
        assert isinstance(raw_ts, str)
        assert ET_TIMESTAMP_REGEX.match(raw_ts), f"Timestamp '{raw_ts}' failed regex"
        assert raw_ts.endswith(" ET")

    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()
