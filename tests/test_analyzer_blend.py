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
        mock_engine.predict_probability.return_value = 0.70  # 70% YES

        with patch("backend.btc.ml_engine.get_ml_engine", return_value=mock_engine):
            result = evaluate_next_15m_contract(df)

            self.assertEqual(result["direction"], "YES")
            self.assertIn("GRADE A+", result["conviction_grade"])

            # Expected: round((78 * 0.6) + (70.0 * 0.4)) = round(74.8) = 75 or int(74.8) = 74
            expected_blended = (78.0 * HEURISTIC_WEIGHT) + (70.0 * ML_WEIGHT)
            self.assertAlmostEqual(float(result["probability_percent"]), expected_blended, delta=1.0)

            # Confirm confirmation catalyst exists
            cat_text = " ".join(result["catalysts"])
            self.assertIn("ML Confirmation", cat_text)

    def test_heuristic_conflicts_with_ml_caps_confidence_and_downgrades(self):
        """
        Forces Bollinger Rejection Hammer (A+ Setup, prob=78, Bid YES).
        ML model strongly disagrees: ml_prob = 0.20 (20% for YES, 80% for NO).
        Disagreement = abs(78 - 20) = 58 >= 15.
        Confidence should be capped at 58.0% and grade downgraded from A+ to A.
        """
        df = self._build_test_df()
        df.loc[df.index[-2], "open"] = 59600.0
        df.loc[df.index[-2], "close"] = 59700.0
        df.loc[df.index[-2], "high"] = 59720.0
        df.loc[df.index[-2], "low"] = 59400.0
        df.loc[df.index[-2], "rsi"] = 35.0
        df.loc[df.index[-2], "atr"] = 100.0
        df.loc[df.index[-1], "open"] = 59650.0

        mock_engine = MagicMock()
        mock_engine.is_trained = True
        mock_engine.predict_probability.return_value = 0.20  # 20% YES (strong conflict)

        with patch("backend.btc.ml_engine.get_ml_engine", return_value=mock_engine):
            result = evaluate_next_15m_contract(df)

            self.assertEqual(result["direction"], "YES")
            self.assertIn("GRADE A SETUP", result["conviction_grade"])
            self.assertNotIn("GRADE A+", result["conviction_grade"])

            # Confidence capped at 58.0
            self.assertLessEqual(result["probability_percent"], 58.0)

            # Conflict catalyst recorded
            cat_text = " ".join(result["catalysts"])
            self.assertIn("Model Conflict", cat_text)


if __name__ == "__main__":
    unittest.main()
