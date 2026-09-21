import os
import tempfile
import json
import pytest
from backend.btc.trade_db import TradeDB, get_trade_db
from backend.btc.auto_executor import AutoExecutor


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_trades.db")
    db = TradeDB(db_path)
    yield db


def test_sqlite_db_creation_and_wal(temp_db):
    """Verify tables and WAL mode are correctly initialized."""
    conn = temp_db._get_connection()
    cursor = conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0].upper()
    assert mode == "WAL", f"Expected WAL mode, got {mode}"

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trades';")
    assert cursor.fetchone() is not None, "trades table not found"


def test_sqlite_upsert_and_retrieve(temp_db):
    """Verify upserting and retrieving trade records."""
    trade1 = {
        "id": "sim_test_001",
        "ticker": "KXBTC15M-TEST",
        "side": "YES",
        "entry_price": 0.55,
        "count": 10.0,
        "pnl": 4.5,
        "status": "SETTLED",
        "result": "WIN",
        "timestamp": "2026-09-21 10:00:00 AM ET"
    }
    trade2 = {
        "id": "sim_test_002",
        "ticker": "KXBTC15M-TEST",
        "side": "NO",
        "entry_price": 0.40,
        "count": 5.0,
        "pnl": -2.0,
        "status": "OPEN",
        "result": "PENDING",
        "timestamp": "2026-09-21 10:15:00 AM ET"
    }

    assert temp_db.upsert_trades([trade1, trade2], asset="BTC")
    assert temp_db.count_trades(asset="BTC") == 2

    trades = temp_db.get_trades(asset="BTC")
    assert len(trades) == 2
    assert trades[0]["id"] == "sim_test_001"
    assert trades[1]["id"] == "sim_test_002"

    # Test update (upsert on existing ID)
    trade2["status"] = "CLOSED"
    trade2["pnl"] = 3.0
    assert temp_db.upsert_trade(trade2, asset="BTC")
    assert temp_db.count_trades(asset="BTC") == 2

    closed_trades = temp_db.get_trades(asset="BTC", status="CLOSED")
    assert len(closed_trades) == 1
    assert closed_trades[0]["pnl"] == 3.0


def test_sqlite_json_import(temp_db):
    """Verify import_from_json_if_needed imports trades from json."""
    temp_json = os.path.join(os.path.dirname(temp_db.db_path), "test_hist.json")
    mock_history = [
        {"id": f"trade_{i}", "side": "YES", "pnl": i * 1.5, "status": "SETTLED"}
        for i in range(15)
    ]
    with open(temp_json, "w", encoding="utf-8") as f:
        json.dump(mock_history, f)

    imported_count = temp_db.import_from_json_if_needed(temp_json, asset="BTC")
    assert imported_count == 15
    assert temp_db.count_trades(asset="BTC") == 15

    # Calling again when count matches should not re-import
    second_import = temp_db.import_from_json_if_needed(temp_json, asset="BTC")
    assert second_import == 0


def test_auto_executor_sqlite_integration():
    """Verify AutoExecutor uses TradeDB seamlessly."""
    executor = AutoExecutor(asset="BTC")
    trades = executor.get_trades_history()
    assert isinstance(trades, list)
    # Ensure count matches or exceeds existing historical records
    assert len(trades) >= 300
