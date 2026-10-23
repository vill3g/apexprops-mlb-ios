"""
Unit tests for the Master Sports Capper Engine and Situational Handicapping.
"""

import unittest
from backend.sports_engine.situational import SituationalEngine
from backend.sports_engine.master_capper import MasterSportsCapper, calculate_kalshi_taker_fee


class TestMasterSportsCapper(unittest.TestCase):

    def test_kalshi_taker_fee(self):
        # On a 50 cent contract: 0.07 * 0.5 * 0.5 = 0.0175 (1.75 cents)
        fee_50 = calculate_kalshi_taker_fee(0.50)
        self.assertAlmostEqual(fee_50, 0.0175, places=4)

        # On an 80 cent contract: 0.07 * 0.8 * 0.2 = 0.0112 (1.12 cents)
        fee_80 = calculate_kalshi_taker_fee(0.80)
        self.assertAlmostEqual(fee_80, 0.0112, places=4)

    def test_situational_fatigue_and_rest(self):
        # Back-to-back with travel should impose penalty
        b2b_res = SituationalEngine.evaluate_situational_catalysts(
            sport="NHL",
            matchup="Team A vs Team B",
            team_selected="Team A",
            rest_days_team=0,
            rest_days_opp=2,
            is_travel_game=True
        )
        self.assertLess(b2b_res["net_situational_delta_pct"], 0.0)
        self.assertTrue(any("Back-to-back" in c for c in b2b_res["catalysts"]))

        # Rest advantage should boost probability
        rest_res = SituationalEngine.evaluate_situational_catalysts(
            sport="NBA",
            matchup="Team A vs Team B",
            team_selected="Team A",
            rest_days_team=3,
            rest_days_opp=1
        )
        self.assertGreater(rest_res["net_situational_delta_pct"], 0.0)
        self.assertTrue(any("Rest advantage" in c for c in rest_res["catalysts"]))

    def test_situational_key_numbers(self):
        # NFL spread landing on 3 points
        nfl_3 = SituationalEngine.evaluate_situational_catalysts(
            sport="NFL",
            matchup="KC vs BAL",
            team_selected="KC",
            spread_pts=3.0
        )
        self.assertGreater(nfl_3["key_number_edge_pct"], 2.0)
        self.assertTrue(any("3-point margin" in c for c in nfl_3["catalysts"]))

        # NHL puck line empty-net leverage
        nhl_pl = SituationalEngine.evaluate_situational_catalysts(
            sport="NHL",
            matchup="EDM vs CGY",
            team_selected="EDM",
            market_type="PUCK LINE"
        )
        self.assertGreater(nhl_pl["key_number_edge_pct"], 2.0)
        self.assertTrue(any("Puck Line" in c for c in nhl_pl["catalysts"]))

    def test_capper_conviction_grades(self):
        # 1. Institutional Lock (A+ / ⭐⭐⭐⭐⭐)
        lock = MasterSportsCapper.evaluate_capper_edge(
            sport="NFL",
            matchup="Bills vs Jets",
            pick_name="Bills",
            market_type="Moneyline",
            model_win_prob=66.0,
            kalshi_price_dollars=0.48,
            situational_factors={"rest_advantage_days": 2, "key_number_edge_pct": 2.0},
            bankroll=1000.0
        )
        self.assertEqual(lock["grade"], "A+")
        self.assertEqual(lock["stars"], "⭐⭐⭐⭐⭐")
        self.assertEqual(lock["tier_label"], "INSTITUTIONAL_LOCK")
        self.assertTrue(lock["is_plus_ev"])
        self.assertGreater(lock["net_ev_pct"], 8.0)
        self.assertGreater(lock["recommended_wager"], 20.0)  # > 2% bankroll

        # 2. Sharp Value (A / ⭐⭐⭐⭐)
        sharp = MasterSportsCapper.evaluate_capper_edge(
            sport="NHL",
            matchup="Panthers vs Bruins",
            pick_name="Panthers",
            market_type="Moneyline",
            model_win_prob=56.5,
            kalshi_price_dollars=0.50,
            bankroll=1000.0
        )
        self.assertIn(sharp["grade"], ("A", "A+"))
        self.assertTrue(sharp["is_plus_ev"])
        self.assertGreater(sharp["recommended_wager"], 0.0)

        # 3. Negative EV Pass (F / ❌)
        # Even with 51% win prob at $0.51, Kalshi taker fee makes Net EV negative
        drag_pass = MasterSportsCapper.evaluate_capper_edge(
            sport="MLB",
            matchup="Yankees vs Red Sox",
            pick_name="Yankees",
            market_type="Moneyline",
            model_win_prob=51.0,
            kalshi_price_dollars=0.51,
            bankroll=1000.0
        )
        self.assertFalse(drag_pass["is_plus_ev"])
        self.assertEqual(drag_pass["grade"], "F")
        self.assertEqual(drag_pass["tier_label"], "NEGATIVE_EV_PASS")
        self.assertEqual(drag_pass["recommended_wager"], 0.0)

    def test_capper_thesis_synthesis(self):
        eval_res = MasterSportsCapper.evaluate_capper_edge(
            sport="SOC",
            matchup="Arsenal vs Chelsea",
            pick_name="Arsenal",
            market_type="Moneyline",
            model_win_prob=62.0,
            kalshi_price_dollars=0.50,
            situational_factors={"rest_advantage_days": 1},
            bankroll=1000.0
        )
        thesis = eval_res.get("capper_thesis", "")
        self.assertTrue(len(thesis) > 40)
        self.assertIn("Arsenal", thesis)
        self.assertIn("Net EV", thesis)


if __name__ == "__main__":
    unittest.main()
