"""
Unit tests for the Native In-Process Sports AI Engine in ShadowTrader.
"""

import unittest
from backend.sports_engine.math.devig import (
    american_to_decimal,
    american_to_implied,
    calculate_ev,
    calculate_kelly_criterion,
    shin_devig
)
from backend.sports_engine.math.calibrator import (
    two_way_devig,
    three_way_devig
)
from backend.sports_engine.simulators.mlb_simulator import simulate_mlb_game, regress_pitcher_era
from backend.sports_engine.simulators.nhl_simulator import simulate_hockey_match
from backend.sports_engine.simulators.nfl_simulator import simulate_nfl_matchup, nfl_spread_to_win_prob
from backend.sports_engine.simulators.soccer_simulator import simulate_soccer_match
from backend.sports_engine.simulators.tennis_simulator import simulate_tennis_match
from backend.sports_engine.simulators.ufc_simulator import simulate_ufc_fight
from backend.sports_engine.explainer import generate_pick_explanation
from backend.sports_engine.native_client import get_native_sports_client
from backend.sports_bridge.prediction_client import SportsPredictionClient


class TestSportsNativeEngine(unittest.TestCase):

    def test_devig_and_math(self):
        # American to Decimal
        self.assertAlmostEqual(american_to_decimal("+150"), 2.50)
        self.assertAlmostEqual(american_to_decimal("-200"), 1.50)

        # American to Implied
        self.assertAlmostEqual(american_to_implied("-110"), 110.0 / 210.0, places=3)
        self.assertAlmostEqual(american_to_implied("+110"), 100.0 / 210.0, places=3)

        # EV calculation
        ev = calculate_ev(model_win_prob=60.0, decimal_odds=2.0)  # 60% @ +100 -> +20% EV
        self.assertEqual(ev, 20.0)

        # Kelly Criterion
        kelly = calculate_kelly_criterion(model_win_prob=60.0, american_odds="+100", kelly_fraction=0.25)
        self.assertTrue(kelly["is_plus_ev"])
        self.assertGreater(kelly["bankroll_pct"], 0.0)

        # 2-way devig (-110 / -110)
        fair_1, fair_2, margin = two_way_devig(-110, -110)
        self.assertEqual(fair_1, 50.0)
        self.assertEqual(fair_2, 50.0)

    def test_mlb_simulator(self):
        # Pitcher regression
        reg_era = regress_pitcher_era(era=2.50, ip=80.0)
        self.assertGreater(reg_era, 2.50)  # Regresses upwards towards 4.15
        self.assertLess(reg_era, 4.15)

        # MLB Game simulation
        res = simulate_mlb_game("NYY", "BOS", home_starter_era=3.20, away_starter_era=4.50)
        self.assertIn("home_win_prob", res)
        self.assertIn("away_win_prob", res)
        self.assertGreater(res["home_win_prob"], res["away_win_prob"])
        self.assertAlmostEqual(res["home_win_prob"] + res["away_win_prob"], 100.0, places=1)
        self.assertIn("factor_impacts", res)

    def test_nhl_simulator(self):
        res = simulate_hockey_match("EDM", "BOS", total_line=5.5)
        self.assertIn("home_win_prob", res)
        self.assertIn("away_win_prob", res)
        self.assertIn("home_puck_line_prob", res)
        self.assertAlmostEqual(res["home_win_prob"] + res["away_win_prob"], 100.0, places=1)

    def test_nfl_simulator(self):
        # Win prob from spread
        fav_prob = nfl_spread_to_win_prob(3.0, is_favorite=True)
        und_prob = nfl_spread_to_win_prob(3.0, is_favorite=False)
        self.assertGreater(fav_prob, 55.0)
        self.assertLess(und_prob, 45.0)

        res = simulate_nfl_matchup("KC", "DAL", spread=-3.0, total=47.5)
        self.assertIn("home_cover_spread_prob", res)
        self.assertIn("projected_total", res)

    def test_soccer_simulator(self):
        res = simulate_soccer_match("Arsenal", "Chelsea", league="EPL")
        self.assertIn("home_win_prob", res)
        self.assertIn("draw_prob", res)
        self.assertIn("away_win_prob", res)
        total_p = res["home_win_prob"] + res["draw_prob"] + res["away_win_prob"]
        self.assertAlmostEqual(total_p, 100.0, delta=1.5)

    def test_tennis_simulator(self):
        res = simulate_tennis_match("Carlos Alcaraz", "Daniil Medvedev", player_a_rank=2, player_b_rank=5, surface="HARD")
        self.assertIn("player_a_win_prob", res)
        self.assertIn("player_b_win_prob", res)
        self.assertGreater(res["player_a_win_prob"], res["player_b_win_prob"])

    def test_ufc_simulator(self):
        res = simulate_ufc_fight("Fighter A", "Fighter B", division="MIDDLEWEIGHT")
        self.assertIn("fighter_a_win_prob", res)
        self.assertIn("inside_distance_prob", res)
        self.assertIn("goes_to_decision_prob", res)

    def test_explainer(self):
        exp = generate_pick_explanation(
            sport="NHL",
            matchup="Edmonton Oilers vs Boston Bruins",
            pick="Edmonton Oilers",
            win_prob=58.2,
            edge_pct=6.5
        )
        self.assertTrue(exp["success"])
        self.assertIn("primary_factors", exp)
        self.assertGreater(len(exp["primary_factors"]), 0)
        self.assertIn("narrative", exp)
        self.assertTrue(len(exp["narrative"]) > 20)

    def test_native_client(self):
        client = get_native_sports_client()
        pred = client.predict_for_event("KXNHLGAME-EDMBOS", title="Edmonton Oilers vs Boston Bruins", sport="NHL")
        self.assertIsNotNone(pred)
        self.assertEqual(pred["sport"], "NHL")
        self.assertIn("confidence_pct", pred)
        self.assertIn("explain", pred["metadata"])

        # Test delegating SportsPredictionClient
        bridge_client = SportsPredictionClient()
        bridge_pred = bridge_client.predict_for_event("KXNHLGAME-EDMBOS", title="Edmonton Oilers vs Boston Bruins", sport="NHL")
        self.assertIsNotNone(bridge_pred)
        self.assertEqual(bridge_pred["sport"], "NHL")
        self.assertIn("capper_grade", bridge_pred["metadata"])
        self.assertIn("capper_stars", bridge_pred["metadata"])

    def test_master_sports_capper(self):
        from backend.sports_engine.master_capper import MasterSportsCapper, calculate_kalshi_taker_fee
        fee = calculate_kalshi_taker_fee(0.50)
        self.assertAlmostEqual(fee, 0.0175, places=4)

        # High edge lock (65% model win prob vs $0.48 Kalshi price)
        capper_res = MasterSportsCapper.evaluate_capper_edge(
            sport="NFL",
            matchup="KC Chiefs vs Dallas Cowboys",
            pick_name="KC Chiefs",
            market_type="Moneyline",
            model_win_prob=65.0,
            kalshi_price_dollars=0.48,
            situational_factors={"rest_advantage_days": 2, "key_number_edge_pct": 2.0},
            bankroll=1000.0
        )
        self.assertTrue(capper_res["is_plus_ev"])
        self.assertGreater(capper_res["net_ev_dollars"], 0.0)
        self.assertIn(capper_res["grade"], ("A+", "A"))
        self.assertGreater(capper_res["recommended_wager"], 0.0)
        self.assertIn("capper_thesis", capper_res)

        # Negative EV pass (42% model win prob vs $0.55 Kalshi price)
        bad_res = MasterSportsCapper.evaluate_capper_edge(
            sport="NHL",
            matchup="Team A vs Team B",
            pick_name="Team A",
            market_type="Moneyline",
            model_win_prob=42.0,
            kalshi_price_dollars=0.55,
            bankroll=1000.0
        )
        self.assertFalse(bad_res["is_plus_ev"])
        self.assertEqual(bad_res["grade"], "F")
        self.assertEqual(bad_res["recommended_wager"], 0.0)


if __name__ == "__main__":
    unittest.main()
