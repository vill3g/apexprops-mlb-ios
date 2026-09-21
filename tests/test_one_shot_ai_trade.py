import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.btc.auto_executor import AutoExecutor


class TestOneShotAiPredictionTrade(unittest.TestCase):
    def setUp(self):
        self.executor = AutoExecutor.__new__(AutoExecutor)
        self.executor.asset = "BTC"
        self.executor._config_file = "dummy.json"
        self.executor.mode = "PAPER"
        self.executor.enabled = True
        self.executor.prediction_mode = True
        self.executor.min_conviction = "GRADE A SETUP"
        self.executor.max_contracts = 1
        self.executor.last_traded_interval = None
        self.executor.last_check_time = 0
        self.executor._cached_trades = []
        self.executor._cached_trades_mtime = 0
        self.executor.ai_settings = {
            "tradingStyle": "SNIPER",
            "minConf": 70,
            "ignorePass": False,
            "reverseCvd": False,
            "dryRun": True,
            "execDelay": 0,
            "maxCap": 0,
            "edgeWeightOn": False,
            "oneShotAiStartTrade": True
        }
        import threading
        self.executor._rollover_lock = threading.Lock()
        self.executor._save_config = MagicMock()
        self.executor._save_trades_history = MagicMock()
        self.executor.get_trades_history = MagicMock(return_value=[])
        self.executor.check_risk_budget = MagicMock(return_value=None)

    @patch("backend.btc.ml_engine.get_ml_engine")
    @patch("backend.btc.auto_executor.kalshi_trader")
    @patch("backend.btc.auto_executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.fetch_candles")
    @patch("backend.btc.auto_executor.add_all_indicators")
    @patch("backend.btc.auto_executor.get_candle_countdown")
    def test_one_shot_ai_trade_executes_and_auto_resets(self, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kalshi, mock_ml):
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_countdown.return_value = {"seconds_left": 870}  # 30s elapsed (sniper window)
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])

        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-ONESHOT",
            "strike_price": 78000.0,
            "yes_ask": 0.52,
            "no_ask": 0.48
        }
        mock_kalshi.place_order.return_value = {
            "success": True,
            "order_id": "ord-oneshot-123",
            "filled_price": 0.48,
            "fill_count": 1,
            "total_cost": 0.48
        }

        # Model evaluated PASS for technicals, but pure ML opening prediction was DOWN (ml_prob = 0.05 -> 95% DOWN)
        mock_eval.return_value = {
            "recommendation": "PASS / NO BID (CHOP)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "ml_prob": 0.05,
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (CHOP)",
            "primary_edge": "Chop",
            "catalysts": ["Range consolidation"]
        }

        # Run cycle with oneShotAiStartTrade = True
        self.executor.check_and_execute_rollover()

        # 1. Verify Kalshi order was placed for "no" (anticipating BELOW target since ml_prob=0.05)
        mock_kalshi.place_order.assert_called_once()
        call_kwargs = mock_kalshi.place_order.call_args.kwargs
        self.assertEqual(call_kwargs["side"], "no")
        self.assertEqual(call_kwargs["ticker"], "KXBTC15M-TEST-ONESHOT")

        # 2. Verify trade record was saved with 100% AI Prediction catalyst
        self.executor._save_trades_history.assert_called_once()
        saved_trades = self.executor._save_trades_history.call_args[0][0]
        self.assertEqual(len(saved_trades), 1)
        trade = saved_trades[0]
        self.assertEqual(trade["direction"], "BELOW")
        self.assertIn("100% AI Prediction at Start", trade["catalysts"][0])

        # 3. Verify oneShotAiStartTrade was automatically reset to False
        self.assertFalse(self.executor.ai_settings["oneShotAiStartTrade"])
        self.executor._save_config.assert_called()

    @patch("backend.btc.ml_engine.get_ml_engine")
    @patch("backend.btc.auto_executor.kalshi_trader")
    @patch("backend.btc.auto_executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.fetch_candles")
    @patch("backend.btc.auto_executor.add_all_indicators")
    @patch("backend.btc.auto_executor.get_candle_countdown")
    def test_one_shot_ai_trade_bullish_and_subsequent_cycle_returns_to_normal(self, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kalshi, mock_ml):
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_countdown.return_value = {"seconds_left": 870}
        mock_candles.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 78000.0, "open": 77900.0, "high": 78100.0, "low": 77800.0, "volume": 100}])

        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-BULLISH",
            "strike_price": 78000.0,
            "yes_ask": 0.49,
            "no_ask": 0.51
        }
        mock_kalshi.place_order.return_value = {
            "success": True,
            "order_id": "ord-bull-123",
            "filled_price": 0.49,
            "fill_count": 1,
            "total_cost": 0.49
        }

        # Model evaluated PASS for technicals, but pure ML opening prediction was UP (ml_prob = 0.82 -> 82% UP)
        mock_eval.return_value = {
            "recommendation": "PASS / NO BID (CHOP)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "ml_prob": 0.82,
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (CHOP)",
            "primary_edge": "Chop",
            "catalysts": ["Consolidation"]
        }

        # Cycle 1: 1-shot is ON -> takes the trade as YES/ABOVE
        self.executor.check_and_execute_rollover()
        self.assertEqual(mock_kalshi.place_order.call_args.kwargs["side"], "yes")
        self.assertFalse(self.executor.ai_settings["oneShotAiStartTrade"])

        # Cycle 2: Next interval arrives. Since oneShotAiStartTrade is now FALSE, normal PASS logic takes over!
        mock_kalshi.place_order.reset_mock()
        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-NEXT-INTERVAL",
            "strike_price": 78100.0,
            "yes_ask": 0.50,
            "no_ask": 0.50
        }
        self.executor.check_and_execute_rollover()
        # Should NOT place any order because PASS is strictly enforced under normal rules
        mock_kalshi.place_order.assert_not_called()


if __name__ == "__main__":
    unittest.main()
