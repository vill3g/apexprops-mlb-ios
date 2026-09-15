"""
tests/test_backtest.py
Unit tests for the walk-forward backtest harness and shared feature extraction.
"""

import unittest
import numpy as np
import pandas as pd
import tempfile
import os

from backend.btc.ml_engine import MLEngine, build_feature_row, FEATURE_KEYS
from backend.btc.indicators import add_all_indicators
from backend.btc.backtest import run_walkforward_backtest, analyze_calibration_overconfidence


class TestBacktestHarness(unittest.TestCase):

    def _generate_synthetic_candles(self, n=350, seed=42):
        """Generates n synthetic 15m OHLCV bars using a fixed random seed."""
        np.random.seed(seed)
        base_time = 1700000000
        records = []
        cur_close = 50000.0

        for i in range(n):
            step = np.random.normal(0, 30.0)
            c_open = cur_close
            c_close = c_open + step
            c_high = max(c_open, c_close) + abs(np.random.normal(10, 5))
            c_low = min(c_open, c_close) - abs(np.random.normal(10, 5))
            vol = float(np.random.uniform(1.0, 50.0))

            records.append({
                "time": base_time + (i * 900),
                "open": c_open,
                "high": c_high,
                "low": c_low,
                "close": c_close,
                "volume": vol
            })
            cur_close = c_close

        df = pd.DataFrame(records)
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df

    def test_build_feature_row_returns_all_keys(self):
        """Verify build_feature_row returns every key in MLEngine.feature_keys."""
        df_raw = self._generate_synthetic_candles(n=120)
        df_ind = add_all_indicators(df_raw)

        # Inspect row 80 (well past indicator warmup)
        feat_dict = build_feature_row(df_ind, 80)
        self.assertIsInstance(feat_dict, dict)

        engine = MLEngine(data_dir=tempfile.gettempdir())
        for key in engine.feature_keys:
            self.assertIn(key, feat_dict, f"Missing key '{key}' in build_feature_row() result")
            self.assertIsNotNone(feat_dict[key])

    def test_run_walkforward_backtest_synthetic(self):
        """Verify run_walkforward_backtest runs without error on synthetic data."""
        df_raw = self._generate_synthetic_candles(n=350)
        df_ind = add_all_indicators(df_raw)

        # Test small window sizes that fit within 300 post-warmup bars
        windows = [100, 150]
        results = run_walkforward_backtest(df_ind, window_sizes=windows, step=1, retrain_every=24)

        self.assertIn("100", results)
        self.assertIn("150", results)

        res_100 = results["100"]
        self.assertEqual(res_100["window_size"], 100)
        self.assertGreater(res_100["test_samples"], 50)
        self.assertGreaterEqual(res_100["brier_score"], 0.0)
        self.assertLessEqual(res_100["brier_score"], 1.0)
        self.assertGreater(res_100["log_loss"], 0.0)
        self.assertGreaterEqual(res_100["accuracy"], 0.0)
        self.assertLessEqual(res_100["accuracy"], 1.0)

        cal_table = res_100["calibration_table"]
        self.assertEqual(len(cal_table), 10)
        self.assertIn("bucket", cal_table[0])

    def test_calibration_overconfidence_analysis(self):
        """Verify overconfidence detector flags tables with systematic bias."""
        balanced_table = [{"count": 20, "diff": 0.02} for _ in range(10)]
        has_warn, _ = analyze_calibration_overconfidence(balanced_table)
        self.assertFalse(has_warn)

        overconfident_table = [{"count": 20, "diff": 0.12} for _ in range(5)] + [{"count": 20, "diff": 0.01} for _ in range(5)]
        has_warn, msg = analyze_calibration_overconfidence(overconfident_table)
        self.assertTrue(has_warn)
        self.assertIn("OVERCONFIDENCE", msg)


    def test_task5_task6_feature_keys_and_fallbacks(self):
        """Verify Task 5 (minutes_remaining) and Task 6 (kalshi market features) exist and handle legacy/missing values safely."""
        engine = MLEngine(data_dir=tempfile.gettempdir())
        self.assertIn("minutes_remaining", engine.feature_keys)
        self.assertIn("kalshi_yes_prob", engine.feature_keys)
        self.assertIn("kalshi_book_imbalance", engine.feature_keys)

        # Legacy raw features missing the new keys
        legacy_raw_features = {
            "rsi": 55.0,
            "macd": 1.2,
            "adx": 22.0
        }
        # Engine prediction should not fail or throw KeyError
        prob = engine.predict_probability(legacy_raw_features)
        self.assertIsInstance(prob, float)
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 100.0)


if __name__ == "__main__":
    unittest.main()

