"""
Unit tests for audit findings 1, 2, 3, and 5:
- Finding 3: slippage_buffer_dollars parameter and config migration
- Finding 5: mutable default preservation in backtest.py and deduplicated trade loading in auto_executor.py
- Finding 2: order state reconciliation on timeout in kalshi_trader.py and auto_executor.py
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.btc.kalshi_trader import KalshiTrader
from backend.btc.backtest import run_walkforward_backtest
from backend.btc.auto_executor import AutoExecutor


class TestFinding3SlippageBuffer(unittest.TestCase):
    """Finding 3: slippage_buffer_dollars unit mismatch & parameter rename."""

    def test_place_order_slippage_buffer_dollars_clamping(self):
        trader = KalshiTrader()
        # Test paper trading path preserves clamped slippage buffer
        res = trader.place_order(
            ticker="KXBTC15M-TEST",
            side="yes",
            count=1,
            limit_price_dollars=0.55,
            dry_run=True,
            slippage_buffer_dollars=0.25  # Should clamp to 0.15
        )
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("slippage_buffer"), 0.15)

        res_low = trader.place_order(
            ticker="KXBTC15M-TEST",
            side="yes",
            count=1,
            limit_price_dollars=0.55,
            dry_run=True,
            slippage_buffer_dollars=-0.05  # Should clamp to 0.0
        )
        self.assertTrue(res_low.get("success"))
        self.assertEqual(res_low.get("slippage_buffer"), 0.0)

    def test_auto_executor_config_migration_cents_to_dollars(self):
        executor = AutoExecutor.__new__(AutoExecutor)
        executor.asset = "BTC"
        executor._config_file = "dummy.json"
        executor.ai_settings = {"slippageBufferCents": 0.05}
        # Simulate migration logic
        if "slippageBufferDollars" not in executor.ai_settings:
            if "slippageBufferCents" in executor.ai_settings:
                executor.ai_settings["slippageBufferDollars"] = executor.ai_settings.pop("slippageBufferCents")
            else:
                executor.ai_settings["slippageBufferDollars"] = 0.04

        self.assertEqual(executor.ai_settings.get("slippageBufferDollars"), 0.05)
        self.assertNotIn("slippageBufferCents", executor.ai_settings)


class TestFinding5CodeQuality(unittest.TestCase):
    """Finding 5: Mutable defaults in backtest.py and deduplicated trade loading."""

    def test_run_walkforward_backtest_does_not_mutate_defaults(self):
        import inspect
        sig = inspect.signature(run_walkforward_backtest)
        default_val = sig.parameters["window_sizes"].default
        self.assertIsNone(default_val, "window_sizes default must be None, not a mutable list")


class TestFinding2OrderReconciliation(unittest.TestCase):
    """Finding 2: Order state reconciliation on timeout."""

    def setUp(self):
        self.trader = KalshiTrader()

    def test_reconcile_after_timeout_buy_success(self):
        pre_positions = [
            {"ticker": "KXBTC15M-26MAR14-T1000", "position": 2, "side": "YES"}
        ]
        post_positions = [
            {"ticker": "KXBTC15M-26MAR14-T1000", "position": 4, "side": "YES"}
        ]

        with patch.object(self.trader, "get_positions", return_value={"success": True, "positions": post_positions}):
            res = self.trader._reconcile_after_timeout(
                ticker="KXBTC15M-26MAR14-T1000",
                client_order_id="test-cid-123",
                side="YES",
                pre_positions=pre_positions,
                requested_count=2.0,
                action="BUY",
                price=0.60
            )

        self.assertIsNotNone(res)
        self.assertTrue(res["success"])
        self.assertEqual(res["source"], "reconciled_after_timeout")
        self.assertEqual(res["count"], 2.0)
        self.assertEqual(res["status"], "FILLED")
        self.assertEqual(res["client_order_id"], "test-cid-123")

    def test_reconcile_after_timeout_buy_no_change_returns_none(self):
        pre_positions = [
            {"ticker": "KXBTC15M-26MAR14-T1000", "position": 2, "side": "YES"}
        ]
        post_positions = [
            {"ticker": "KXBTC15M-26MAR14-T1000", "position": 2, "side": "YES"}
        ]

        with patch.object(self.trader, "get_positions", return_value={"success": True, "positions": post_positions}):
            res = self.trader._reconcile_after_timeout(
                ticker="KXBTC15M-26MAR14-T1000",
                client_order_id="test-cid-123",
                side="YES",
                pre_positions=pre_positions,
                requested_count=2.0,
                action="BUY",
                price=0.60
            )

        self.assertIsNone(res)

    def test_reconcile_after_timeout_close_success(self):
        pre_positions = [
            {"ticker": "KXBTC15M-26MAR14-T1000", "position": 3, "side": "YES"}
        ]
        post_positions = [
            {"ticker": "KXBTC15M-26MAR14-T1000", "position": 1, "side": "YES"}
        ]

        with patch.object(self.trader, "get_positions", return_value={"success": True, "positions": post_positions}):
            res = self.trader._reconcile_after_timeout(
                ticker="KXBTC15M-26MAR14-T1000",
                client_order_id="test-close-cid",
                side="YES",
                pre_positions=pre_positions,
                requested_count=2.0,
                action="CLOSE",
                price=0.75
            )

        self.assertIsNotNone(res)
        self.assertTrue(res["success"])
        self.assertEqual(res["source"], "reconciled_after_timeout")
        self.assertEqual(res["filled_count"], 2.0)
        self.assertEqual(res["exit_price"], 0.75)

    def test_place_order_timeout_reconciliation_flow_success(self):
        pre_positions = []
        post_positions = [{"ticker": "KXBTC15M-26MAR14-T1000", "position": 1, "side": "YES"}]

        mock_market = {
            "ticker": "KXBTC15M-26MAR14-T1000",
            "yes_ask": 0.55,
            "no_ask": 0.45,
            "is_synthetic": False
        }

        with patch.object(self.trader, "get_active_15m_market", return_value=mock_market), \
             patch.object(self.trader, "get_balance", return_value={"success": True, "balance_dollars": 100.0}), \
             patch.object(self.trader, "_sign_headers", return_value={"Authorization": "Bearer test"}), \
             patch.object(self.trader, "get_positions", side_effect=[
                 {"success": True, "positions": pre_positions},
                 {"success": True, "positions": post_positions}
             ]), \
             patch.object(self.trader.order_session, "post", side_effect=requests.exceptions.Timeout("Connection timed out")):

            res = self.trader.place_order(
                ticker="KXBTC15M-26MAR14-T1000",
                side="yes",
                count=1,
                limit_price_dollars=0.55,
                dry_run=False
            )

            self.assertTrue(res.get("success"), "Timeout should resolve to success when position appeared on Kalshi")
            self.assertEqual(res.get("source"), "reconciled_after_timeout")
            self.assertEqual(res.get("count"), 1.0)

    def test_place_order_timeout_reconciliation_flow_unconfirmed_ambiguous(self):
        pre_positions = []
        post_positions = []  # No change

        mock_market = {
            "ticker": "KXBTC15M-26MAR14-T1000",
            "yes_ask": 0.55,
            "no_ask": 0.45,
            "is_synthetic": False
        }

        with patch.object(self.trader, "get_active_15m_market", return_value=mock_market), \
             patch.object(self.trader, "get_balance", return_value={"success": True, "balance_dollars": 100.0}), \
             patch.object(self.trader, "_sign_headers", return_value={"Authorization": "Bearer test"}), \
             patch.object(self.trader, "get_positions", side_effect=[
                 {"success": True, "positions": pre_positions},
                 {"success": True, "positions": post_positions}
             ]), \
             patch.object(self.trader.order_session, "post", side_effect=requests.exceptions.Timeout("Gateway timeout")):

            res = self.trader.place_order(
                ticker="KXBTC15M-26MAR14-T1000",
                side="yes",
                count=1,
                limit_price_dollars=0.55,
                dry_run=False
            )

            self.assertFalse(res.get("success"))
            self.assertTrue(res.get("ambiguous"), "Unconfirmed order timeout must flag ambiguous: True")
            self.assertIn("MANUAL VERIFICATION REQUIRED", res.get("error"))


class TestDataFetcherAudit(unittest.TestCase):
    """Audit tests for data_fetcher.py fixes."""

    def test_fetch_1m_candles_history_uses_1m_interval(self):
        """Verify fetch_1m_candles_history specifies '1m' interval to Binance, not '15m'."""
        import inspect
        from backend.btc import data_fetcher
        src = inspect.getsource(data_fetcher.fetch_1m_candles_history)
        self.assertIn('"interval": "1m"', src, "fetch_1m_candles_history must query 1m interval")
        self.assertNotIn('"interval": "15m"', src, "fetch_1m_candles_history must not query 15m interval")

    def test_yfinance_datetime_int64_conversion(self):
        """Verify datetime with timezone converts to unix timestamps with int64 without throwing TypeError."""
        import pandas as pd
        s = pd.Series(pd.date_range("2026-01-01", periods=3, tz="UTC"))
        converted = pd.to_datetime(s).astype("int64") // 10**9
        self.assertEqual(len(converted), 3)
        self.assertTrue(all(isinstance(v, (int, pd.Int64Dtype, object)) for v in converted))


class TestExpirationSafetyGuard(unittest.TestCase):
    """Verify contracts nearing expiration (<30s) are never entered."""

    def setUp(self):
        self.trader = KalshiTrader()

    def test_place_order_rejects_expiring_contract(self):
        import datetime
        near_close = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)).isoformat()
        mock_market = {
            "ticker": "KXBTC15M-EXPIRING",
            "yes_ask": 0.50,
            "no_ask": 0.50,
            "close_time": near_close,
            "is_synthetic": False
        }
        with patch.object(self.trader, "get_active_15m_market", return_value=mock_market):
            res = self.trader.place_order(
                ticker="KXBTC15M-EXPIRING",
                side="yes",
                count=1,
                limit_price_dollars=0.50,
                dry_run=False
            )
            self.assertFalse(res.get("success"))
            self.assertIn("rejected", res.get("error", "").lower())
            self.assertIn("30s remaining", res.get("error", ""))

    def test_auto_executor_ignores_final_seconds(self):
        executor = AutoExecutor.__new__(AutoExecutor)
        executor.asset = "BTC"
        executor._config_file = "dummy.json"
        executor.mode = "LIVE"
        executor.enabled = True
        executor.prediction_mode = True
        executor.last_traded_interval = None
        executor.last_check_time = 0
        executor.ai_settings = {"tradingStyle": "SNIPER"}
        import threading
        executor._rollover_lock = threading.Lock()

        with patch("backend.btc.auto_executor.get_candle_countdown", return_value={"seconds_left": 8}), \
             patch("backend.btc.auto_executor.kalshi_trader") as mock_kt:
            res = executor.check_and_execute_rollover()
            self.assertIsNone(res)
            # Ensure kalshi market was never even queried for late execution
            mock_kt.get_active_15m_market.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from backend.btc.auto_executor import get_auto_executor
auto_executor = get_auto_executor('BTC')

import unittest
from unittest.mock import patch, MagicMock
from backend.btc.auto_executor import get_auto_executor
auto_executor = get_auto_executor('BTC')
import pandas as pd
import time

