"""
Unit tests for the multi-sport Head-to-Head (H2H) statistical matrix engine.
"""

import unittest
from backend.sports_engine.h2h_matrix import HeadToHeadEngine
from backend.sports_engine.situational import SituationalEngine
from backend.sports_engine.simulators.nfl_simulator import simulate_nfl_matchup


class TestHeadToHeadEngine(unittest.TestCase):

    def test_nfl_h2h_broncos_seahawks(self):
        """Verify H2H lookup and defensive trend adjustment for Seahawks vs Broncos."""
        h2h = HeadToHeadEngine.get_h2h_stats("Seattle Seahawks", "Denver Broncos")
        self.assertIsNotNone(h2h)
        self.assertEqual(h2h["meetings"], 4)
        self.assertEqual(h2h["wins_a"], 3)  # Seattle 3 wins

        impact = HeadToHeadEngine.evaluate_h2h_impact(
            sport="NFL",
            team_a="Denver Broncos",
            team_b="Seattle Seahawks",
            target_team="Seattle Seahawks",
            market_type="TOTAL",
            market_line=44.5
        )
        self.assertTrue(impact["has_h2h_data"])
        self.assertLess(impact["total_points_delta"], 0.0)  # Defensive trend vs line
        self.assertIn("H2H", impact["h2h_summary"])

    def test_nhl_h2h_panthers_sabres(self):
        """Verify H2H lookup for Florida Panthers vs Buffalo Sabres."""
        h2h = HeadToHeadEngine.get_h2h_stats("Florida Panthers", "Buffalo Sabres")
        self.assertIsNotNone(h2h)
        self.assertEqual(h2h["meetings"], 6)

        impact = HeadToHeadEngine.evaluate_h2h_impact(
            sport="NHL",
            team_a="Florida Panthers",
            team_b="Buffalo Sabres",
            target_team="Florida Panthers",
            market_type="MONEYLINE"
        )
        self.assertTrue(impact["has_h2h_data"])
        self.assertGreater(impact["win_prob_delta_pct"], 0.0)  # Panthers dominance

    def test_soccer_derby_h2h_arsenal_chelsea(self):
        """Verify London Derby H2H for Arsenal vs Chelsea."""
        h2h = HeadToHeadEngine.get_h2h_stats("Arsenal", "Chelsea")
        self.assertIsNotNone(h2h)
        self.assertTrue(h2h.get("derby"))

        impact = HeadToHeadEngine.evaluate_h2h_impact(
            sport="SOC",
            team_a="Arsenal",
            team_b="Chelsea",
            target_team="Arsenal",
            market_type="TOTAL",
            market_line=2.5
        )
        self.assertTrue(impact["has_h2h_data"])
        self.assertGreater(impact["total_points_delta"], 0.0)  # High scoring 3.2 avg

    def test_tennis_rivalry_alcaraz_sinner(self):
        """Verify Tennis H2H for Carlos Alcaraz vs Jannik Sinner."""
        h2h = HeadToHeadEngine.get_h2h_stats("Carlos Alcaraz", "Jannik Sinner")
        self.assertIsNotNone(h2h)
        self.assertEqual(h2h["meetings"], 10)

    def test_situational_catalyst_h2h_integration(self):
        """Verify SituationalEngine extracts and includes H2H catalysts."""
        sit = SituationalEngine.evaluate_situational_catalysts(
            sport="NFL",
            matchup="Dallas Cowboys @ Philadelphia Eagles",
            team_selected="Philadelphia Eagles",
            market_type="SPREAD",
            spread_pts=6.5
        )
        self.assertIn("net_situational_delta_pct", sit)
        # Should include key number and/or H2H catalysts
        self.assertTrue(len(sit["catalysts"]) > 0)

    def test_nfl_simulator_incorporates_h2h(self):
        """Verify simulate_nfl_matchup factors in H2H total shift."""
        sim = simulate_nfl_matchup("Denver Broncos", "Seattle Seahawks", spread=-2.5, total=44.5)
        self.assertIn("h2h_stats", sim)
        self.assertTrue(sim["h2h_stats"]["has_h2h_data"])
        self.assertIn("h2h_total_shift", sim["factor_impacts"])


if __name__ == "__main__":
    unittest.main()
