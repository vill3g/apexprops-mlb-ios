import os
import sys
import unittest

sys.path.insert(0, r"C:\Users\Vill3\Desktop\kalshi-ai-trader")

from backend.btc.few_shot_feedback import get_recent_execution_feedback
from backend.btc.cf_synthetic_settler import record_spot_sample, evaluate_synthetic_settlement_lock
from backend.btc.kelly_scaler import calculate_dynamic_kelly_size

class TestGeminiAlphaUpgrades(unittest.TestCase):
    def test_few_shot_feedback(self):
        feedback = get_recent_execution_feedback("BTC", limit=3)
        self.assertIsInstance(feedback, list)
        for item in feedback:
            self.assertIn("outcome", item)
            self.assertIn("post_mortem_lesson", item)

    def test_synthetic_cf_settlement_lock(self):
        # Sample rising spots
        for i in range(50):
            record_spot_sample("BTC", 68000.0 + i * 2.0)
        res = evaluate_synthetic_settlement_lock("BTC", 67900.0, 40.0)
        self.assertTrue(res["is_settlement_window"])
        self.assertEqual(res["math_locked_outcome"], "LOCKED_YES")
        self.assertGreaterEqual(res["confidence_lock_pct"], 90.0)

    def test_dynamic_kelly_scaler(self):
        # Grade A+ snipe setup
        res_snipe = calculate_dynamic_kelly_size(5, 88.0, is_snipe_opportunity=True, is_unanimous_debate=True)
        self.assertGreaterEqual(res_snipe["scaled_contracts"], 10)
        self.assertIn("GRADE_A_PLUS", res_snipe["conviction_grade"])

        # Grade B standard setup
        res_std = calculate_dynamic_kelly_size(5, 74.0, is_snipe_opportunity=False, is_unanimous_debate=False)
        self.assertEqual(res_std["scaled_contracts"], 5)
        self.assertIn("GRADE_B", res_std["conviction_grade"])

if __name__ == "__main__":
    unittest.main()
