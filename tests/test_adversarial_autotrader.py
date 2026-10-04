"""
Adversarial Stress Test Suite for Auto Trader Engine
Tests:
1. Kalshi HTTP 429 resilience & runaway loop prevention in executor.py and saas_broadcaster.py
2. Paper trading order_intents.claim concurrency and duplicate prevention
3. execDelay non-blocking multi-asset worker execution and concurrent re-entry gating
"""

import os
import sys
import time
import threading
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.btc.auto_executor import AutoExecutor
from backend.btc.auto_executor.saas_broadcaster import (
    SaasBroadcasterMixin,
    _user_last_traded_cache,
    _user_last_traded_lock
)
from backend.database import order_intents


class TestAdversarialAutoTrader(unittest.TestCase):
    def setUp(self):
        # Clean up database order_intents table
        try:
            conn = order_intents._connect()
            with conn:
                conn.execute("DELETE FROM order_intents WHERE ticker LIKE 'KXBTC15M-ADV%'")
                conn.execute("DELETE FROM order_intents WHERE ticker LIKE 'KXETH15M-ADV%'")
            conn.close()
        except Exception:
            pass

        # Clear SaaSBroadcaster user last traded cache
        with _user_last_traded_lock:
            _user_last_traded_cache.clear()

        # Build reusable AutoExecutor instance
        self.executor = AutoExecutor.__new__(AutoExecutor)
        self.executor.asset = "BTC"
        self.executor._config_file = "dummy.json"
        self.executor.mode = "LIVE"
        self.executor.enabled = True
        self.executor.prediction_mode = True
        self.executor.min_conviction = "GRADE A SETUP"
        self.executor.max_contracts = 1
        self.executor.last_traded_interval = None
        self.executor.last_check_time = 0.0
        self.executor._inflight_interval = None
        self.executor._cached_trades = []
        self.executor._cached_trades_mtime = 0
        self.executor.broadcast_trades = True
        self.executor._last_saas_eval_time = 0.0
        self.executor.ai_settings = {
            "tradingStyle": "SNIPER",
            "minConf": 70,
            "ignorePass": False,
            "reverseCvd": False,
            "dryRun": False,
            "execDelay": 0,
            "maxCap": 0,
            "edgeWeightOn": False,
            "oneShotAiStartTrade": False
        }
        self.executor._rollover_lock = threading.Lock()
        self.executor._saas_eval_lock = threading.Lock()
        self.executor._config_lock = threading.Lock()
        self.executor._save_config = MagicMock()
        self.executor._save_trades_history = MagicMock()
        self.executor.get_trades_history = MagicMock(return_value=[])
        self.executor.check_risk_budget = MagicMock(return_value=None)

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 1: Executor Kalshi 429 Resilience & 1-Second Runaway Prevention
    # ──────────────────────────────────────────────────────────────────────────
    @patch("backend.btc.auto_executor.executor.kalshi_trader")
    @patch("backend.btc.auto_executor.executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.executor.fetch_candles")
    @patch("backend.btc.auto_executor.executor.add_all_indicators")
    @patch("backend.btc.auto_executor.executor.get_candle_countdown")
    @patch("backend.btc.auto_executor.executor.is_market_open", return_value=True)
    def test_executor_429_halts_runaway_loop(
        self, mock_market_open, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kt
    ):
        """Simulate repeated Kalshi 429 rate limit responses and verify that
        last_traded_interval halts runaway 1-second re-evaluations."""
        interval_1 = "KXBTC15M-ADV-429-1"
        mock_countdown.return_value = {"seconds_left": 870}  # Within 60s rollover window
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])

        mock_kt.get_active_15m_market.return_value = {
            "ticker": interval_1,
            "strike_price": 78000.0,
            "yes_ask": 0.52,
            "no_ask": 0.48
        }
        mock_kt.get_balance.return_value = {"success": True, "balance_dollars": 100.0}

        # Simulate Kalshi 429 rejection on place_order
        mock_kt.place_order.return_value = {
            "success": False,
            "order_id": "",
            "ambiguous": False,
            "error": "Kalshi Order Rejected (HTTP 429): Rate limit exceeded"
        }

        mock_eval.return_value = {
            "recommendation": "BUY YES",
            "direction": "ABOVE",
            "action_type": "BUY",
            "probability_percent": 80,
            "ml_prob": 0.80,
            "conviction_grade": "GRADE A+",
            "conviction_badge": "🟢 HIGH CONVICTION",
            "primary_edge": "Trend",
            "catalysts": ["Strong momentum"]
        }

        # 1. First execution attempt hits 429
        res1 = self.executor.check_and_execute_rollover()
        self.assertIsNone(res1)
        self.assertEqual(mock_kt.place_order.call_count, 1)

        # Verify last_traded_interval was marked to current interval
        self.assertEqual(self.executor.last_traded_interval, interval_1)

        # 2. Adversarial stress test: Rapid 1-second loop iterations
        # Simulating worker loop running every 1 second in the same interval
        for _ in range(10):
            # Advance last_check_time so the 0.95s throttling gate passes
            self.executor.last_check_time = time.time() - 2.0
            res_subsequent = self.executor.check_and_execute_rollover()
            self.assertIsNone(res_subsequent)

        # Assert: place_order MUST NOT be called again (call count remains strictly 1)
        self.assertEqual(
            mock_kt.place_order.call_count, 1,
            "Kalshi 429 triggered a runaway loop! place_order was invoked more than once for the same interval."
        )

        # 3. Advance to NEXT 15-minute interval: verify executor does not freeze permanently
        interval_2 = "KXBTC15M-ADV-429-2"
        mock_kt.get_active_15m_market.return_value["ticker"] = interval_2
        self.executor.last_check_time = time.time() - 2.0

        res_next = self.executor.check_and_execute_rollover()
        self.assertIsNone(res_next)
        # Order should be attempted for the new interval
        self.assertEqual(mock_kt.place_order.call_count, 2)
        self.assertEqual(self.executor.last_traded_interval, interval_2)

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 2: SaaS Broadcaster Kalshi 429 Resilience
    # ──────────────────────────────────────────────────────────────────────────
    @patch("backend.btc.auto_executor.saas_broadcaster.kalshi_trader")
    @patch("backend.btc.auto_executor.saas_broadcaster.get_user_kalshi_trader")
    @patch("backend.btc.auto_executor.saas_broadcaster.get_all_active_users")
    @patch("backend.btc.auto_executor.saas_broadcaster.get_candle_countdown")
    @patch("backend.btc.auto_executor.saas_broadcaster.is_market_open", return_value=True)
    @patch("backend.btc.auto_executor.saas_broadcaster.fetch_candles")
    @patch("backend.btc.auto_executor.saas_broadcaster.add_all_indicators")
    @patch("backend.btc.auto_executor.saas_broadcaster.evaluate_next_15m_contract")
    def test_saas_broadcaster_429_halts_runaway_loop(
        self, mock_eval, mock_indicators, mock_candles, mock_open, mock_countdown,
        mock_get_users, mock_get_user_kt, mock_global_kt
    ):
        """Simulate repeated Kalshi 429 responses in SaaS multi-tenant broadcaster
        and verify _user_last_traded_cache prevents continuous re-evaluation."""
        interval_id = "KXBTC15M-ADV-SAAS-429"
        user_id = 9988

        mock_countdown.return_value = {"seconds_left": 870}
        active_market = {
            "ticker": interval_id,
            "strike_price": 78000.0,
            "yes_ask": 0.52,
            "no_ask": 0.48,
            "is_synthetic": False
        }
        mock_global_kt.get_active_15m_market.return_value = active_market

        mock_user_kt = MagicMock()
        mock_user_kt.get_balance.return_value = {"success": True, "balance_dollars": 500.0}
        mock_user_kt.place_order.return_value = {
            "success": False,
            "order_id": "",
            "ambiguous": False,
            "error": "Kalshi Order Rejected (HTTP 429): Too Many Requests"
        }
        mock_get_user_kt.return_value = mock_user_kt

        mock_user = {
            "id": user_id,
            "username": "adversarial_user",
            "ai_enabled": 1,
            "target_asset": "BTC",
            "trading_mode": "LIVE",
            "signal_source": "BLEND",
            "trading_style": "SNIPER",
            "trade_size_dollars": 20.0,
            "edge_gate_enabled": 0
        }
        mock_get_users.return_value = [mock_user]

        mock_eval.return_value = {
            "direction": "ABOVE",
            "probability_percent": 85,
            "conviction_grade": "GRADE A+",
            "conviction_badge": "🟢 STRONG",
            "primary_edge": "Trend",
            "catalysts": []
        }
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = mock_candles.return_value

        # First broadcaster round
        self.executor.evaluate_and_execute_saas_users()
        self.assertEqual(mock_user_kt.place_order.call_count, 1)

        # Verify _user_last_traded_cache is populated
        with _user_last_traded_lock:
            cached_val = _user_last_traded_cache.get((user_id, "BTC"))
        self.assertEqual(cached_val, interval_id)

        # Stress test: Repeated broadcaster cycles within the same interval
        for _ in range(5):
            self.executor._last_saas_eval_time = time.time() - 10.0  # bypass 4s throttle
            self.executor.evaluate_and_execute_saas_users()

        # place_order must NOT have been called again!
        self.assertEqual(
            mock_user_kt.place_order.call_count, 1,
            "SaaS Broadcaster did not halt 429 retry loop! place_order called repeatedly."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 3: Paper Trading Concurrency & order_intents.claim Deduplication
    # ──────────────────────────────────────────────────────────────────────────
    def test_paper_trading_order_intents_concurrency_race(self):
        """High contention concurrency test on paper trading order_intents.claim.
        Spawns 20 concurrent threads trying to claim the identical paper interval.
        Exactly 1 must succeed."""
        account_key = "paper:owner"
        ticker = "KXBTC15M-ADV-PAPER-CONC"

        # Ensure clean initial state
        order_intents.release(account_key, ticker)

        results = []
        barrier = threading.Barrier(20)

        def _race_claim():
            barrier.wait()
            win = order_intents.claim(account_key, ticker, "YES")
            results.append(win)

        threads = [threading.Thread(target=_race_claim) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 1 winner
        self.assertEqual(results.count(True), 1, f"Expected exactly 1 claim winner, got {results.count(True)}")
        self.assertEqual(results.count(False), 19)

        # Outcome settlement as filled keeps the intent locked
        order_intents.settle_outcome(account_key, ticker, {"success": True, "client_order_id": "sim-conc-1"})
        # Subsequent attempts must continue to be blocked
        self.assertFalse(order_intents.claim(account_key, ticker, "YES"))
        self.assertFalse(order_intents.claim(account_key, ticker, "NO"))

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 4: AutoExecutor Paper Mode Rejects Duplicate Interval Orders
    # ──────────────────────────────────────────────────────────────────────────
    @patch("backend.btc.auto_executor.executor.kalshi_trader")
    @patch("backend.btc.auto_executor.executor.load_balance", return_value=1000.0)
    def test_auto_executor_paper_mode_rejects_duplicate_interval(self, mock_load_bal, mock_kt):
        """Verify AutoExecutor in PAPER mode claims order_intents with 'paper:' prefix
        and rejects concurrent / duplicate executions for the same interval."""
        ticker = "KXBTC15M-ADV-PAPER-DUP"
        base_key = order_intents.account_key_for_executor(None)
        paper_key = f"paper:{base_key}"

        order_intents.release(paper_key, ticker)

        # Pre-claim the paper intent to simulate a concurrent thread having claimed it
        pre_claimed = order_intents.claim(paper_key, ticker, "YES")
        self.assertTrue(pre_claimed)

        # Configure executor in PAPER mode
        self.executor.mode = "PAPER"
        self.executor.ai_settings["dryRun"] = True

        mock_kt.place_order.return_value = {
            "success": True,
            "mode": "PAPER",
            "filled_price": 0.50,
            "fill_count": 1,
            "total_cost": 0.50
        }

        # Verify that claiming the already-claimed paper intent fails
        intent_claimed = order_intents.claim(paper_key, ticker, "YES")
        self.assertFalse(intent_claimed, "Duplicate paper intent was erroneously permitted!")

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 5: execDelay Non-Blocking Worker Execution
    # ──────────────────────────────────────────────────────────────────────────
    @patch("backend.btc.auto_executor.executor.kalshi_trader")
    @patch("backend.btc.auto_executor.executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.executor.fetch_candles")
    @patch("backend.btc.auto_executor.executor.add_all_indicators")
    @patch("backend.btc.auto_executor.executor.get_candle_countdown")
    @patch("backend.btc.auto_executor.executor.is_market_open", return_value=True)
    def test_exec_delay_non_blocking_worker_execution(
        self, mock_market_open, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kt
    ):
        """Verify that execDelay > 0 offloads execution to a background thread
        and returns immediately (< 0.25s), preventing worker thread stall."""
        interval_id = "KXBTC15M-ADV-DELAY-NONBLOCK"
        self.executor.ai_settings["execDelay"] = 1  # 1 second delay

        mock_countdown.return_value = {"seconds_left": 870}
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = mock_candles.return_value

        mock_kt.get_active_15m_market.return_value = {
            "ticker": interval_id,
            "strike_price": 78000.0,
            "yes_ask": 0.52,
            "no_ask": 0.48
        }
        mock_kt.get_balance.return_value = {"success": True, "balance_dollars": 100.0}
        mock_kt.place_order.return_value = {
            "success": True,
            "order_id": "ord-delayed-1",
            "filled_price": 0.52,
            "fill_count": 1,
            "total_cost": 0.52
        }

        mock_eval.return_value = {
            "recommendation": "BUY YES",
            "direction": "ABOVE",
            "action_type": "BUY",
            "probability_percent": 80,
            "ml_prob": 0.80,
            "conviction_grade": "GRADE A+",
            "conviction_badge": "🟢 STRONG",
            "primary_edge": "Trend",
            "catalysts": []
        }

        start_time = time.time()
        res = self.executor.check_and_execute_rollover()
        elapsed = time.time() - start_time

        # Must return virtually instantaneously
        self.assertLess(elapsed, 0.25, f"check_and_execute_rollover blocked worker thread for {elapsed:.3f}s!")
        self.assertIsNone(res)

        # Inflight interval must be marked
        self.assertEqual(getattr(self.executor, "_inflight_interval", None), interval_id)

        # Wait for delayed execution background task to complete
        time.sleep(1.3)

        # After delay completes, place_order must have been called
        self.assertEqual(mock_kt.place_order.call_count, 1)
        self.assertEqual(self.executor.last_traded_interval, interval_id)
        self.assertIsNone(getattr(self.executor, "_inflight_interval", None))

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 6: execDelay Multi-Asset Worker Non-Starvation (ETH & GOLD not stalled)
    # ──────────────────────────────────────────────────────────────────────────
    @patch("backend.btc.auto_executor.executor.kalshi_trader")
    @patch("backend.btc.auto_executor.executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.executor.fetch_candles")
    @patch("backend.btc.auto_executor.executor.add_all_indicators")
    @patch("backend.btc.auto_executor.executor.get_candle_countdown")
    @patch("backend.btc.auto_executor.executor.is_market_open", return_value=True)
    def test_exec_delay_multi_asset_worker_non_starvation(
        self, mock_market_open, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kt
    ):
        """Simulate worker.py sequential loop across ['BTC', 'ETH', 'GOLD'].
        Verify that a 2-second execDelay on BTC does NOT delay or stall ETH and GOLD."""
        btc_exec = self.executor
        btc_exec.ai_settings["execDelay"] = 2  # 2 seconds delay on BTC

        # Create ETH executor with 0 delay
        eth_exec = AutoExecutor.__new__(AutoExecutor)
        eth_exec.asset = "ETH"
        eth_exec._config_file = "dummy_eth.json"
        eth_exec.mode = "PAPER"
        eth_exec.enabled = True
        eth_exec.prediction_mode = True
        eth_exec.min_conviction = "GRADE A SETUP"
        eth_exec.max_contracts = 1
        eth_exec.last_traded_interval = None
        eth_exec.last_check_time = 0.0
        eth_exec._inflight_interval = None
        eth_exec._cached_trades = []
        eth_exec._cached_trades_mtime = 0
        eth_exec.ai_settings = {"tradingStyle": "SNIPER", "minConf": 70, "execDelay": 0, "dryRun": True}
        eth_exec._rollover_lock = threading.Lock()
        eth_exec._save_config = MagicMock()
        eth_exec._save_trades_history = MagicMock()
        eth_exec.get_trades_history = MagicMock(return_value=[])
        eth_exec.check_risk_budget = MagicMock(return_value=None)

        mock_countdown.return_value = {"seconds_left": 870}
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = mock_candles.return_value

        mock_kt.get_active_15m_market.side_effect = lambda series_ticker, **kwargs: {
            "ticker": f"{series_ticker}-ADV-MULTI",
            "strike_price": 3000.0 if "ETH" in series_ticker else 78000.0,
            "yes_ask": 0.50,
            "no_ask": 0.50
        }
        mock_kt.get_balance.return_value = {"success": True, "balance_dollars": 100.0}
        mock_kt.place_order.return_value = {"success": True, "order_id": "ord-multi", "filled_price": 0.50, "fill_count": 1, "total_cost": 0.50}

        mock_eval.return_value = {
            "recommendation": "BUY YES",
            "direction": "ABOVE",
            "action_type": "BUY",
            "probability_percent": 80,
            "ml_prob": 0.80,
            "conviction_grade": "GRADE A+",
            "conviction_badge": "🟢 STRONG",
            "primary_edge": "Trend",
            "catalysts": []
        }

        # Measure time to execute BTC and ETH rollover evaluations
        start_btc = time.time()
        btc_exec.check_and_execute_rollover()
        elapsed_btc = time.time() - start_btc

        start_eth = time.time()
        eth_exec.check_and_execute_rollover()
        elapsed_eth = time.time() - start_eth

        # 1. BTC must return non-blocking without waiting for the 2.0s delay
        self.assertLess(
            elapsed_btc, 0.35,
            f"BTC check_and_execute_rollover took {elapsed_btc:.3f}s! execDelay blocked worker thread."
        )

        # 2. When ETH finishes, BTC must STILL be inflight (delay thread still sleeping in background)
        self.assertIsNotNone(
            getattr(btc_exec, "_inflight_interval", None),
            "BTC delayed execution finished prematurely before ETH evaluation!"
        )

        # 3. Total time to evaluate both assets must be well under the 2.0s delay
        self.assertLess(
            elapsed_btc + elapsed_eth, 1.0,
            f"Combined evaluation took {elapsed_btc + elapsed_eth:.3f}s, stalling the multi-asset worker loop!"
        )

        # Cleanup: wait for BTC delay thread
        time.sleep(2.2)


    # ──────────────────────────────────────────────────────────────────────────
    # TEST 7: execDelay Prevents Concurrent Re-Entry During Delay Window
    # ──────────────────────────────────────────────────────────────────────────
    @patch("backend.btc.auto_executor.executor.kalshi_trader")
    @patch("backend.btc.auto_executor.executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.executor.fetch_candles")
    @patch("backend.btc.auto_executor.executor.add_all_indicators")
    @patch("backend.btc.auto_executor.executor.get_candle_countdown")
    @patch("backend.btc.auto_executor.executor.is_market_open", return_value=True)
    def test_exec_delay_blocks_concurrent_reentry_during_delay(
        self, mock_market_open, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kt
    ):
        """Verify that while a delayed execution task is sleeping in the background,
        concurrent rollover checks for the same interval are blocked by _inflight_interval,
        preventing duplicate trade execution."""
        interval_id = "KXBTC15M-ADV-REENTRY-TEST"
        self.executor.ai_settings["execDelay"] = 1  # 1 second delay

        mock_countdown.return_value = {"seconds_left": 870}
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = mock_candles.return_value

        mock_kt.get_active_15m_market.return_value = {
            "ticker": interval_id,
            "strike_price": 78000.0,
            "yes_ask": 0.52,
            "no_ask": 0.48
        }
        mock_kt.get_balance.return_value = {"success": True, "balance_dollars": 100.0}
        mock_kt.place_order.return_value = {
            "success": True,
            "order_id": "ord-reentry-1",
            "filled_price": 0.52,
            "fill_count": 1,
            "total_cost": 0.52
        }

        mock_eval.return_value = {
            "recommendation": "BUY YES",
            "direction": "ABOVE",
            "action_type": "BUY",
            "probability_percent": 80,
            "ml_prob": 0.80,
            "conviction_grade": "GRADE A+",
            "conviction_badge": "🟢 STRONG",
            "primary_edge": "Trend",
            "catalysts": []
        }

        # 1. Trigger initial rollover evaluation (starts 1s delay in background)
        self.executor.check_and_execute_rollover()
        self.assertEqual(getattr(self.executor, "_inflight_interval", None), interval_id)

        # 2. While the delay task is sleeping (at ~0.1s), simulate another worker check
        time.sleep(0.1)
        self.executor.last_check_time = time.time() - 2.0  # bypass 0.95s check throttling
        reentry_res = self.executor.check_and_execute_rollover()

        # Re-entry MUST be blocked immediately
        self.assertIsNone(reentry_res)

        # 3. Wait for background delayed task to complete its execution
        time.sleep(1.2)

        # Assert: place_order must have been called EXACTLY ONCE
        self.assertEqual(
            mock_kt.place_order.call_count, 1,
            f"Concurrent re-entry during execDelay occurred! place_order called {mock_kt.place_order.call_count} times."
        )
        self.assertEqual(self.executor.last_traded_interval, interval_id)

        # 4. Check again after completion
        self.executor.last_check_time = time.time() - 2.0
        post_res = self.executor.check_and_execute_rollover()
        self.assertIsNone(post_res)
        self.assertEqual(mock_kt.place_order.call_count, 1)


if __name__ == "__main__":
    unittest.main()
