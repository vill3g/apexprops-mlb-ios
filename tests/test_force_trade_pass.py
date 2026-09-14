import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from backend.btc.auto_executor import AutoExecutor


class TestForceTradeOnPass(unittest.TestCase):
    def setUp(self):
        self.executor = AutoExecutor.__new__(AutoExecutor)
        self.executor.mode = "PAPER"
        self.executor.enabled = True
        self.executor.prediction_mode = True
        self.executor.min_conviction = "GRADE B SETUP"
        self.executor.max_contracts = 1
        self.executor.last_traded_interval = None
        self.executor.last_check_time = 0
        self.executor._cached_trades = []
        self.executor._cached_trades_mtime = 0
        self.executor.ai_settings = {
            "tradingStyle": "SNIPER",
            "minConf": 60,
            "ignorePass": True,
            "reverseCvd": False,
            "dryRun": True,
            "execDelay": 0,
            "maxCap": 0,
            "edgeWeightOn": False
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
    def test_force_trade_overrides_pass_with_pre_gate_bearish(self, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kalshi, mock_ml):
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_countdown.return_value = {"seconds_left": 860}  # sec_elapsed = 40 (inside sniper window)
        mock_candles.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        
        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-1",
            "strike_price": 90000.0,
            "yes_ask": 0.50,
            "no_ask": 0.50
        }
        mock_kalshi.place_order.return_value = {"success": True, "order_id": "ord-123"}
        
        # Forecast returned PASS due to CVD Divergence, but underlying setup was BELOW with 72% prob
        mock_eval.return_value = {
            "recommendation": "GRADE C / PASS (PASS)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "predicted_probability": 0.5,
            "ml_prob": 0.35,  # 65% confident in BELOW
            "pre_gate_direction": "BELOW",
            "pre_gate_prob": 72.0,
            "pre_gate_grade": "GRADE A SETUP",
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (CVD DIVERGENCE)",
            "target_settlement_zone": "--",
            "primary_edge": "Moderate Confluence Setup",
            "catalysts": ["CVD Volume Divergence"],
            "raw_features": {}
        }
        
        self.executor.check_and_execute_rollover()
        # Side should be "no" because pre_gate_direction is "BELOW"
        mock_kalshi.place_order.assert_called_once()
        call_kwargs = mock_kalshi.place_order.call_args.kwargs
        self.assertEqual(call_kwargs["side"], "no")
        self.assertEqual(call_kwargs["ticker"], "KXBTC15M-TEST-1")
        self.assertEqual(self.executor.last_traded_interval, "KXBTC15M-TEST-1")
        self.executor._save_trades_history.assert_called_once()
        saved_trades = self.executor._save_trades_history.call_args[0][0]
        self.assertEqual(len(saved_trades), 1)
        self.assertTrue(saved_trades[0].get("is_forced_pass"))
        self.assertEqual(saved_trades[0].get("direction"), "BELOW")
        self.assertEqual(saved_trades[0].get("probability_percent"), 72)

    @patch("backend.btc.ml_engine.get_ml_engine")
    @patch("backend.btc.auto_executor.kalshi_trader")
    @patch("backend.btc.auto_executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.fetch_candles")
    @patch("backend.btc.auto_executor.add_all_indicators")
    @patch("backend.btc.auto_executor.get_candle_countdown")
    def test_reverse_on_cvd_divergence(self, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kalshi, mock_ml):
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_countdown.return_value = {"seconds_left": 860}
        mock_candles.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        
        self.executor.ai_settings["ignorePass"] = False
        self.executor.ai_settings["reverseCvd"] = True
        
        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-2",
            "strike_price": 90000.0,
            "yes_ask": 0.50,
            "no_ask": 0.50
        }
        mock_kalshi.place_order.return_value = {"success": True, "order_id": "ord-456"}
        
        # Candidate was ABOVE, CVD divergence caused PASS -> reverseCvd flips to BELOW ("no")
        mock_eval.return_value = {
            "recommendation": "GRADE C / PASS (PASS)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "predicted_probability": 0.5,
            "ml_prob": 0.65,
            "pre_gate_direction": "ABOVE",
            "pre_gate_prob": 68.0,
            "pre_gate_grade": "GRADE A SETUP",
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (CVD DIVERGENCE)",
            "catalysts": []
        }
        
        self.executor.check_and_execute_rollover()
        mock_kalshi.place_order.assert_called_once()
        call_kwargs = mock_kalshi.place_order.call_args.kwargs
        self.assertEqual(call_kwargs["side"], "no")
        self.assertEqual(call_kwargs["ticker"], "KXBTC15M-TEST-2")
        self.assertEqual(self.executor.last_traded_interval, "KXBTC15M-TEST-2")
        self.executor._save_trades_history.assert_called_once()
        saved_trades = self.executor._save_trades_history.call_args[0][0]
        self.assertEqual(len(saved_trades), 1)
        self.assertTrue(saved_trades[0].get("is_reverse"))
        self.assertEqual(saved_trades[0].get("direction"), "BELOW")
        self.assertEqual(saved_trades[0].get("probability_percent"), 68)

    @patch("backend.btc.ml_engine.get_ml_engine")
    @patch("backend.btc.auto_executor.kalshi_trader")
    @patch("backend.btc.auto_executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.fetch_candles")
    @patch("backend.btc.auto_executor.add_all_indicators")
    @patch("backend.btc.auto_executor.get_candle_countdown")
    def test_pin_risk_still_blocks_even_with_ignore_pass(self, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kalshi, mock_ml):
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_countdown.return_value = {"seconds_left": 860}
        mock_candles.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        
        self.executor.ai_settings["ignorePass"] = True
        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-PIN",
            "strike_price": 90000.0
        }
        
        mock_eval.return_value = {
            "recommendation": "PASS (PIN RISK)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (PIN RISK)",
            "catalysts": []
        }
        
        self.executor.check_and_execute_rollover()
        mock_kalshi.place_order.assert_not_called()
        self.executor._save_trades_history.assert_not_called()

    @patch("backend.btc.ml_engine.get_ml_engine")
    @patch("backend.btc.auto_executor.kalshi_trader")
    @patch("backend.btc.auto_executor.evaluate_next_15m_contract")
    @patch("backend.btc.auto_executor.fetch_candles")
    @patch("backend.btc.auto_executor.add_all_indicators")
    @patch("backend.btc.auto_executor.get_candle_countdown")
    def test_force_trade_uses_raw_ml_prob_when_overridden_by_vwap(self, mock_countdown, mock_indicators, mock_candles, mock_eval, mock_kalshi, mock_ml):
        mock_ml.return_value = MagicMock(is_trained=True)
        mock_countdown.return_value = {"seconds_left": 860}
        mock_candles.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        mock_indicators.return_value = pd.DataFrame([{"close": 90000.0, "open": 89900.0, "high": 90100.0, "low": 89800.0, "volume": 100}])
        
        self.executor.ai_settings["ignorePass"] = True
        mock_kalshi.get_active_15m_market.return_value = {
            "ticker": "KXBTC15M-TEST-RAW-ML",
            "strike_price": 90000.0,
            "yes_ask": 0.50,
            "no_ask": 0.50
        }
        mock_kalshi.place_order.return_value = {"success": True, "order_id": "ord-raw-ml"}
        
        # Scenario: Technical VWAP override flattened ml_prob to 0.5, but raw_ml_prob is 0.38 (bearish model)
        mock_eval.return_value = {
            "recommendation": "GRADE C / PASS (PASS)",
            "direction": "PASS",
            "action_type": "PASS",
            "probability_percent": 50,
            "predicted_probability": 0.5,
            "ml_prob": 0.50,         # Technical VWAP override flattened this to 0.50
            "raw_ml_prob": 0.38,     # The TRUE raw ML model output (62% confident in BELOW)
            "pre_gate_direction": "PASS",
            "pre_gate_prob": 50.0,
            "conviction_grade": "GRADE C / PASS",
            "conviction_badge": "⚪ PASS (VWAP OVERRIDE)",
            "catalysts": []
        }
        
        self.executor.check_and_execute_rollover()
        mock_kalshi.place_order.assert_called_once()
        call_kwargs = mock_kalshi.place_order.call_args.kwargs
        # Since raw_ml_prob is 0.38 (< 0.50), it must place "no" (BELOW), NOT default to "yes" (ABOVE)
        self.assertEqual(call_kwargs["side"], "no")
        self.assertEqual(call_kwargs["ticker"], "KXBTC15M-TEST-RAW-ML")
        saved_trades = self.executor._save_trades_history.call_args[0][0]
        self.assertEqual(saved_trades[0].get("direction"), "BELOW")
        self.assertEqual(saved_trades[0].get("ml_prob"), 0.38)
        self.assertTrue(saved_trades[0].get("is_forced_pass"))


if __name__ == "__main__":
    unittest.main()
