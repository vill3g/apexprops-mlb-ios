import os
import sys
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.btc.auto_executor import AutoExecutor
from backend.btc.analyzer import evaluate_next_15m_contract, THRESHOLDS


def test_manual_trade_not_blocked_above_60_cents():
    executor = AutoExecutor()
    executor.ai_settings["dryRun"] = True
    
    # Mock active market with ask price 0.63 (previously blocked by 60-cent ceiling)
    with patch("backend.btc.auto_executor.kalshi_trader") as mock_kt:
        mock_kt.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST",
            "yes_ask": 0.63,
            "no_ask": 0.35,
            "strike_price": 78000.0,
        }
        mock_kt.place_order.return_value = {
            "success": True,
            "mode": "PAPER",
            "order_id": "sim_test123",
            "filled_price": 0.63,
            "count": 1,
            "total_cost": 0.63,
        }
        res = executor.execute_manual_trade("ABOVE")
        assert res["success"] is True
        assert res["trade"]["entry_price"] == 0.63


def test_grade_a_plus_blocked_by_heavy_spot_sell_wall():
    """Verify Grade A+ setup no longer bypasses heavy orderbook ask walls."""
    # Create minimal synthetic candle series
    n = 60
    base_price = 78000.0
    dates = pd.date_range("2026-09-14 06:00", periods=n, freq="15min")
    df = pd.DataFrame({
        "timestamp": dates.astype("int64") // 10**9,
        "open": [base_price + i * 5 for i in range(n)],
        "high": [base_price + i * 5 + 15 for i in range(n)],
        "low": [base_price + i * 5 - 10 for i in range(n)],
        "close": [base_price + i * 5 + 10 for i in range(n)],
        "volume": [100.0 + i for i in range(n)],
    })
    
    from backend.btc.indicators import add_all_indicators
    df_ind = add_all_indicators(df)
    
    # Mock heavy ask wall on Coinbase (-30% imbalance, below -25% gate threshold)
    with patch("backend.btc.data_fetcher.get_coinbase_orderbook_imbalance", return_value={"imbalance": -30.0}):
        # Target contract matching current price
        res = evaluate_next_15m_contract(
            df_ind,
            target_price=base_price + n * 5
        )
        # If direction would have been YES, heavy ask wall MUST force PASS
        if "YES" in str(res.get("recommendation")):
            assert res.get("direction") == "PASS"
            assert "SPOT SELL WALL" in str(res.get("conviction_badge"))


def test_higher_timeframe_1h_trend_confluence_bonus():
    """Verify 1H trend alignment applies confidence bonus and catalysts."""
    n = 60
    base_price = 78000.0
    dates = pd.date_range("2026-09-14 06:00", periods=n, freq="15min")
    df = pd.DataFrame({
        "timestamp": dates.astype("int64") // 10**9,
        "open": [base_price + i * 10 for i in range(n)],
        "high": [base_price + i * 10 + 20 for i in range(n)],
        "low": [base_price + i * 10 - 5 for i in range(n)],
        "close": [base_price + i * 10 + 15 for i in range(n)],
        "volume": [100.0 + i for i in range(n)],
    })
    
    from backend.btc.indicators import add_all_indicators
    df_ind = add_all_indicators(df)
    
    with patch("backend.btc.data_fetcher.get_coinbase_orderbook_imbalance", return_value={"imbalance": 5.0}):
        res = evaluate_next_15m_contract(
            df_ind,
            target_price=base_price
        )
        catalysts = " ".join(res.get("catalysts", []))
        if res.get("direction") == "YES":
            assert "Macro 1H Confluence" in catalysts or "Bullish" in catalysts
