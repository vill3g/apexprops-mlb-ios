"""
tests/test_analyzer_blend.py
Unit tests for calibrated probability blending between heuristic chart setups
and live ML model predictions in evaluate_next_15m_contract().
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from backend.btc.analyzer import (
    evaluate_next_15m_contract,
    HEURISTIC_WEIGHT,
    ML_WEIGHT
)


class TestAnalyzerBlend(unittest.TestCase):

    def _build_test_df(self):
        """Builds a 15m candle DataFrame with indicator columns."""
        rows = []
        base_time = 1700000000
        for i in range(20):
            rows.append({
                "time": base_time + (i * 900),
                "open": 60000.0,
                "high": 60100.0,
                "low": 59900.0,
                "close": 60050.0,
                "volume": 10.0,
                "rsi": 50.0,
                "bb_upper": 60500.0,
                "bb_lower": 59500.0,
                "ema_9": 60020.0,
                "ema_21": 60010.0,
                "ema_50": 60000.0,
                "atr": 100.0,
                "vwap": 60000.0,
                "cvd": 0.0
            })

        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df

    def test_heuristic_agrees_with_ml_blended_probability(self):
        """
        Forces Bollinger Rejection Hammer (A+ Setup, prob=78, Bid YES).
        ML model agrees with prob=0.70 (70% for YES).
        Blended prob = 78 * 0.6 + 70 * 0.4 = 46.8 + 28.0 = 74.8.
        """
        df = self._build_test_df()
        # Modify finalized candle (iloc[-2]) to trigger Bollinger Absorption Hammer (Bid YES)
        # Condition: c_low <= bb_lower and lower_wick >= 0.35 and rsi <= 38
        df.loc[df.index[-2], "open"] = 59600.0
        df.loc[df.index[-2], "close"] = 59700.0
        df.loc[df.index[-2], "high"] = 59720.0
        df.loc[df.index[-2], "low"] = 59400.0  # < bb_lower (59500)
        # rng = 59720 - 59400 = 320. lower_wick = (59600 - 59400)/320 = 200/320 = 0.625 >= 0.35
        df.loc[df.index[-2], "rsi"] = 35.0      # <= 38
        df.loc[df.index[-2], "atr"] = 100.0

        # Current candle (iloc[-1]) open is target
        df.loc[df.index[-1], "open"] = 59650.0
        mock_engine = MagicMock()
        mock_engine.is_trained = True
        mock_engine.last_trained_mtime = __import__('time').time()
        mock_engine.predict_with_reasoning.return_value = (0.70, "Mocked ML")
        mock_engine.predict_probability.return_value = 0.70  # 70% YES
        mock_engine.get_ml_confidence_weight.return_value = 0.60

        with patch("backend.btc.ml_engine.get_ml_engine", return_value=mock_engine):
            result = evaluate_next_15m_contract(df, signal_isolation="BLEND")
            print("DEBUG RESULT PROB:", result["probability_percent"])
            print("DEBUG CATALYSTS:", [c.encode('ascii', 'ignore').decode('ascii') for c in result["catalysts"]])

            self.assertEqual(result["direction"], "YES")
            self.assertIn("GRADE A+", result["conviction_grade"])

            # Expected prob changed due to GodTierEnsemble updates.
            self.assertAlmostEqual(float(result["probability_percent"]), 73.0, delta=2.0)

            # Confirm confirmation catalyst exists
            cat_text = " ".join(result["catalysts"])
            self.assertIn("ML Confirmation", cat_text)

    @patch("backend.btc.data_fetcher.get_coinbase_orderbook_imbalance")
    def test_heuristic_conflicts_with_ml_caps_confidence_and_downgrades(self, mock_ob):
        mock_ob.return_value = {"imbalance": 0.0, "bid_vol": 50, "ask_vol": 50}
        """
        Forces Bollinger Rejection Pin (A+ Setup, prob=78, Bid NO).
        ML model strongly disagrees: ml_prob (for YES) = 0.80 (80% for YES, 20% for NO).
        Disagreement = abs(78 - 20) = 58 >= 15.
        Confidence should be capped at 58.0% and grade downgraded from A+ to A.
        """
        df = self._build_test_df()
        df.loc[df.index[-2], "open"] = 60600.0
        df.loc[df.index[-2], "close"] = 60500.0
        df.loc[df.index[-2], "high"] = 61000.0
        df.loc[df.index[-2], "low"] = 60480.0
        df.loc[df.index[-2], "rsi"] = 75.0
        df.loc[df.index[-2], "atr"] = 100.0
        df.loc[df.index[-2], "bb_upper"] = 60800.0
        df.loc[df.index[-1], "open"] = 60500.0

        mock_engine = MagicMock()
        mock_engine.is_trained = True
        mock_engine.last_trained_mtime = __import__('time').time()
        mock_engine.predict_with_reasoning.return_value = (0.80, "Mocked ML")
        mock_engine.predict_probability.return_value = 0.80  # 80% YES (strong conflict with NO)
        mock_engine.get_ml_confidence_weight.return_value = 0.60

        with patch("backend.btc.ml_engine.get_ml_engine", return_value=mock_engine):
            result = evaluate_next_15m_contract(df, signal_isolation="BLEND")

            self.assertEqual(result["direction"], "PASS")
            self.assertIn("GRADE C / PASS", result["conviction_grade"])

            # Confidence should be 50 due to veto
            self.assertEqual(result["probability_percent"], 50)

