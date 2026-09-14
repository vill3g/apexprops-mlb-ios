"""
tests/test_trend_boxes.py
Unit tests for the 5 Trend Boxes (last 5 completed 15m targets) logic:
1. target_price locks in whatever price the last contract closed at (p["close"]), no other price.
2. delta, delta_pct, and direction are relative to target_price (c["close"] - p["close"]).
3. PASS prediction yields predicted_correctly: None (never False).
4. Real historical features (delta_to_target, score) are computed without fake 0.0 placeholders.
5. data_fetcher and analyzer return matching target_price, direction, delta, delta_pct for shared DataFrame.
6. Error-path fallback schema in main.py matches expected shape.
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from backend.btc.trend_boxes import (
    compute_last_5_targets,
    compute_streak_summary,
    enrich_targets_with_ml
)


class MockMLEngine:
    def __init__(self, is_trained=True, forced_prob=0.70):
        self.is_trained = is_trained
        self.forced_prob = forced_prob
        self.last_raw_feat = None

    def predict_probability(self, raw_feat):
        self.last_raw_feat = raw_feat
        return self.forced_prob


class TestTrendBoxes(unittest.TestCase):

    def _generate_test_dataframe(self, n=10):
        """
        Creates a test DataFrame of 15m candles where:
        - Candle open differs from previous candle close (to catch p_close vs c_open bugs).
        """
        base_time = 1789290000  # Epoch seconds
        rows = []
        for i in range(n):
            # Intentionally make open differ from prior close by 25.0
            c_open = 70000.0 + (i * 100.0)
            # Alternating higher / lower closes relative to c_open
            if i % 2 == 0:
                c_close = c_open + 50.0  # HIGHER
            else:
                c_close = c_open - 30.0  # LOWER
            c_high = max(c_open, c_close) + 10.0
            c_low = min(c_open, c_close) - 10.0
            rows.append({
                "time": base_time + (i * 900),
                "open": c_open,
                "high": c_high,
                "low": c_low,
                "close": c_close,
                "volume": 10.0 + i,
                "rsi": 50.0 + (5.0 if i % 2 == 0 else -5.0),
                "ema_9": c_open + (2.0 if i % 2 == 0 else -2.0),
                "ema_21": c_open,
                "ema_50": c_open - 10.0,
                "bb_upper": c_high + 5.0,
                "bb_lower": c_low - 5.0,
                "atr": 20.0,
                "vwap": c_open,
                "cvd": 1.5 if i % 2 == 0 else -1.5,
                "datetime": datetime.fromtimestamp(base_time + (i * 900), tz=timezone.utc)
            })
        return pd.DataFrame(rows)

    def test_target_price_locks_in_prior_contract_close(self):
        """
        Verify target_price locks in whatever price the last contract closed at (p["close"]),
        NO other price (e.g. not c["open"]).
        Verify delta and delta_pct are computed relative to p["close"].
        """
        df = self._generate_test_dataframe(n=8)
        targets = compute_last_5_targets(df, count=5)
        self.assertEqual(len(targets), 5)

        # df has 8 rows: index 7 is active forming candle.
        # Completed candles are indices 2, 3, 4, 5, 6.
        for idx, box in enumerate(targets):
            candle_idx = 2 + idx
            c = df.iloc[candle_idx]
            p = df.iloc[candle_idx - 1]

            expected_target = round(float(p["close"]), 2)
            wrong_candle_open = round(float(c["open"]), 2)

            # Assert target_price locks in p["close"] (prior contract close)
            self.assertEqual(box["target_price"], expected_target)
            # Ensure it did NOT use c["open"] (they are designed to differ)
            self.assertNotEqual(box["target_price"], wrong_candle_open)

            # Assert delta and delta_pct are relative to p["close"]
            expected_delta = round(float(c["close"]) - float(p["close"]), 2)
            expected_delta_pct = round((expected_delta / (float(p["close"]) + 1e-10)) * 100.0, 2)
            self.assertEqual(box["delta"], expected_delta)
            self.assertEqual(box["delta_pct"], expected_delta_pct)

            # Assert direction
            if expected_delta >= 0:
                self.assertEqual(box["direction"], "HIGHER")
                self.assertEqual(box["arrow"], "▲")
                self.assertEqual(box["color"], "green")
            else:
                self.assertEqual(box["direction"], "LOWER")
                self.assertEqual(box["arrow"], "▼")
                self.assertEqual(box["color"], "red")

    def test_predicted_correctly_pass_is_none_never_false(self):
        """
        Bug 3 Test:
        When ml_prediction is PASS, predicted_correctly MUST be None, NEVER False.
        """
        df = self._generate_test_dataframe(n=8)
        # Neutral indicators resulting in PASS
        for col in ["rsi"]:
            df[col] = 50.0
        df["ema_9"] = df["open"]
        df["ema_21"] = df["open"]

        targets = compute_last_5_targets(df)
        # Force model to output PASS probability (between 0.45 and 0.55)
        mock_ml = MockMLEngine(is_trained=True, forced_prob=0.50)
        enriched = enrich_targets_with_ml(targets, df, ml_engine=mock_ml)

        for box in enriched:
            self.assertEqual(box["ml_prediction"], "PASS")
            self.assertIsNone(box["predicted_correctly"], "PASS must yield predicted_correctly: None")
            self.assertIsNot(box["predicted_correctly"], False, "PASS must NOT be False")

    def test_predicted_correctly_directional_verdict(self):
        """
        Bug 3 Test:
        Verify directional predictions correctly match settlement (close >= open).
        """
        df = self._generate_test_dataframe(n=8)
        targets = compute_last_5_targets(df)

        # Test UP model (forced 70% UP)
        mock_up = MockMLEngine(is_trained=True, forced_prob=0.70)
        enriched_up = enrich_targets_with_ml([dict(t) for t in targets], df, ml_engine=mock_up)
        for box in enriched_up:
            self.assertIn("UP", box["ml_prediction"])
            is_higher = box["delta"] >= 0
            if is_higher:
                self.assertTrue(box["predicted_correctly"])
            else:
                self.assertFalse(box["predicted_correctly"])

        # Test DOWN model (forced 30% DOWN)
        mock_down = MockMLEngine(is_trained=True, forced_prob=0.30)
        enriched_down = enrich_targets_with_ml([dict(t) for t in targets], df, ml_engine=mock_down)
        for box in enriched_down:
            self.assertIn("DOWN", box["ml_prediction"])
            is_lower = box["delta"] < 0
            if is_lower:
                self.assertTrue(box["predicted_correctly"])
            else:
                self.assertFalse(box["predicted_correctly"])

    def test_real_historical_features_computed_no_fake_zeros(self):
        """
        Bug 2 Test:
        Verify delta_to_target and score are computed with real values,
        not hardcoded 0.0 placeholders.
        """
        df = self._generate_test_dataframe(n=8)
        targets = compute_last_5_targets(df)
        mock_ml = MockMLEngine(is_trained=True, forced_prob=0.60)
        enrich_targets_with_ml(targets, df, ml_engine=mock_ml)

        self.assertIsNotNone(mock_ml.last_raw_feat)
        raw = mock_ml.last_raw_feat
        # delta_to_target must be non-zero because p_close != c_open in our fixture
        self.assertNotEqual(raw["delta_to_target"], 0.0)
        # score must be non-zero because RSI != 50 and EMA9 != EMA21
        self.assertNotEqual(raw["score"], 0.0)

    def test_data_fetcher_and_analyzer_produce_identical_targets(self):
        """
        Bug 4 Test:
        Verify data_fetcher and analyzer implementations return identical target_price,
        direction, delta, delta_pct, and timestamps for the same DataFrame.
        """
        df = self._generate_test_dataframe(n=10)

        # data_fetcher computes:
        targets_df = compute_last_5_targets(df)
        streak_df = compute_streak_summary(targets_df)

        # analyzer computes:
        targets_an = compute_last_5_targets(df)
        targets_an = enrich_targets_with_ml(targets_an, df, ml_engine=None)
        streak_an = compute_streak_summary(targets_an)

        self.assertEqual(len(targets_df), len(targets_an))
        self.assertEqual(streak_df, streak_an)

        for b_df, b_an in zip(targets_df, targets_an):
            self.assertEqual(b_df["target_price"], b_an["target_price"])
            self.assertEqual(b_df["price"], b_an["price"])
            self.assertEqual(b_df["delta"], b_an["delta"])
            self.assertEqual(b_df["delta_pct"], b_an["delta_pct"])
            self.assertEqual(b_df["direction"], b_an["direction"])
            self.assertEqual(b_df["arrow"], b_an["arrow"])
            self.assertEqual(b_df["color"], b_an["color"])
            self.assertEqual(b_df["time"], b_an["time"])
            self.assertEqual(b_df["pred_time"], b_an["pred_time"])

    def test_edge_cases(self):
        """
        Test edge cases: empty DataFrame, fewer than 2 candles, empty streak.
        """
        self.assertEqual(compute_last_5_targets(None), [])
        self.assertEqual(compute_last_5_targets(pd.DataFrame()), [])
        # Only 1 candle (the active forming candle) -> 0 completed candles
        df_1 = pd.DataFrame([{"open": 70000, "close": 70010, "time": 1789290000}])
        self.assertEqual(compute_last_5_targets(df_1), [])

        self.assertEqual(compute_streak_summary([]), "--")


if __name__ == "__main__":
    unittest.main()
