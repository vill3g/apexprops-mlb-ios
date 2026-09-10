"""
Correlated Monte Carlo Simulation Engine for MLB Hits + Runs + RBIs (H+R+RBI).
Simulates plate appearances, correlated scoring events, and computes win probabilities
against sportsbook prop lines (1.5, 2.5).
"""

import numpy as np
from typing import Dict, Any, List, Tuple

# Baseline PA expected values by batting order position (1-9)
BASE_PA_BY_ORDER = {
    1: 4.65,
    2: 4.52,
    3: 4.38,
    4: 4.22,
    5: 4.08,
    6: 3.92,
    7: 3.80,
    8: 3.68,
    9: 3.58
}

class HRRBISimulator:
    def __init__(self, num_simulations: int = 10000, seed: int = 42):
        self.num_simulations = num_simulations
        self.rng = np.random.default_rng(seed)

    def calculate_implied_team_total(self, over_under: float, spread: float, is_home: bool) -> float:
        """
        Derive implied team total runs from game Over/Under and spread.
        e.g., O/U 8.5, Home Spread -1.5 -> Home total = 5.0, Away total = 3.5
        """
        margin = abs(spread)
        if spread < 0: # Home is favorite
            home_total = (over_under + margin) / 2.0
            away_total = (over_under - margin) / 2.0
        else: # Away is favorite
            away_total = (over_under + margin) / 2.0
            home_total = (over_under - margin) / 2.0
        
        return max(2.5, min(8.0, home_total if is_home else away_total))

    def project_plate_appearances(
        self,
        order: int,
        team_itt: float,
        is_home: bool
    ) -> np.ndarray:
        """
        Generates simulated plate appearances for 10,000 games.
        """
        base_pa = BASE_PA_BY_ORDER.get(order, 4.0)
        # Adjust for team offense volume
        itt_adj = (team_itt - 4.2) * 0.14
        # Visiting team guaranteed 9th inning
        away_adj = 0.15 if not is_home else -0.05
        expected_pa = max(3.2, base_pa + itt_adj + away_adj)

        # PA integer distribution centered around expected_pa
        # e.g., if expected_pa = 4.6, ~50% get 5, ~40% get 4, ~10% get 3 or 6
        pa_noise = self.rng.normal(0, 0.65, self.num_simulations)
        simulated_pa = np.clip(np.round(expected_pa + pa_noise).astype(int), 2, 7)
        return simulated_pa

    def simulate_player_prop(
        self,
        name: str,
        team: str,
        order: int,
        is_home: bool,
        avg: float = 0.270,
        obp: float = 0.340,
        slg: float = 0.450,
        pitcher_era: float = 4.20,
        park_factor: float = 1.00,
        target_line: float = 1.5
    ) -> Dict[str, Any]:
        """
        Executes 10,000 Monte Carlo game simulations for a single batter.
        Simulates correlated hits, runs, and RBIs.
        """
        # Pitcher adjustment multiplier (baseline ERA 4.10)
        pitcher_mod = min(1.30, max(0.75, pitcher_era / 4.10))
        effective_avg = min(0.380, max(0.180, avg * pitcher_mod * (park_factor ** 0.5)))
        effective_obp = min(0.460, max(0.240, obp * pitcher_mod * (park_factor ** 0.4)))
        effective_slg = min(0.650, max(0.300, slg * pitcher_mod * park_factor))

        # Event probabilities within a single Plate Appearance
        # Single, Double, Triple, Home Run, Walk, Out
        iso = max(0.08, effective_slg - effective_avg)
        p_hr = min(0.10, max(0.015, (iso * 0.35) * park_factor))
        p_triple = 0.006
        p_double = min(0.085, max(0.035, (iso * 0.38)))
        p_single = max(0.10, effective_avg - (p_double + p_triple + p_hr))
        p_hit = p_single + p_double + p_triple + p_hr

        p_walk = max(0.05, effective_obp - effective_avg)
        p_out = max(0.40, 1.0 - (p_hit + p_walk))

        # Normalize event probabilities
        pa_probs = np.array([p_single, p_double, p_triple, p_hr, p_walk, p_out])
        pa_probs = pa_probs / pa_probs.sum()

        # Simulate Plate Appearances
        team_itt = 4.5 * park_factor
        sim_pa_counts = self.project_plate_appearances(order, team_itt, is_home)

        # High-performance Vectorized Game Simulations
        sim_outcomes = np.zeros((self.num_simulations, 6), dtype=int)
        for pa_val in np.unique(sim_pa_counts):
            mask = (sim_pa_counts == pa_val)
            cnt = np.count_nonzero(mask)
            if cnt > 0:
                sim_outcomes[mask] = self.rng.multinomial(pa_val, pa_probs, size=cnt)

        singles = sim_outcomes[:, 0]
        doubles = sim_outcomes[:, 1]
        triples = sim_outcomes[:, 2]
        hrs     = sim_outcomes[:, 3]
        walks   = sim_outcomes[:, 4]

        sim_hits = singles + doubles + triples + hrs

        # Additional runners driven in on HR (solo vs 2-run vs 3-run)
        hr_extra_rbis = self.rng.binomial(hrs, 0.48) + self.rng.binomial(hrs, 0.16)
        hr_rbis = hrs + hr_extra_rbis

        # Base scoring probabilities
        p_run_given_single = min(0.55, 0.36 * park_factor)
        p_run_given_double = min(0.75, 0.56 * park_factor)
        p_run_given_triple = min(0.88, 0.75 * park_factor)
        p_run_given_walk = min(0.48, 0.32 * park_factor)

        # Middle of order (3, 4, 5) get far more RBI opportunities
        rbi_boost = 1.35 if order in [3, 4, 5] else (1.10 if order in [2] else 0.85)

        # Non-HR Runs
        non_hr_runs = (
            self.rng.binomial(singles, p_run_given_single) +
            self.rng.binomial(doubles, p_run_given_double) +
            self.rng.binomial(triples, p_run_given_triple) +
            self.rng.binomial(walks, p_run_given_walk)
        )
        sim_runs = hrs + non_hr_runs

        # Non-HR RBIs (hits with runners in scoring position)
        non_hr_rbis = (
            self.rng.binomial(singles, min(0.45, 0.24 * rbi_boost)) +
            self.rng.binomial(doubles, min(0.65, 0.42 * rbi_boost)) +
            self.rng.binomial(triples, min(0.75, 0.52 * rbi_boost))
        )
        sim_rbis = hr_rbis + non_hr_rbis

        total_hrrbi = sim_hits + sim_runs + sim_rbis

        # Probability metrics
        threshold = 1 if target_line <= 1.0 else (target_line + 0.5 if target_line % 1 == 0.5 else target_line)
        win_count = np.count_nonzero(total_hrrbi >= threshold)
        win_prob = round(float((win_count / self.num_simulations) * 100.0), 1)

        # Expected component values
        exp_hits = round(float(np.mean(sim_hits)), 2)
        exp_runs = round(float(np.mean(sim_runs)), 2)
        exp_rbis = round(float(np.mean(sim_rbis)), 2)
        proj_total = round(float(np.mean(total_hrrbi)), 2)

        # Outcome distribution: 0, 1, 2, 3, 4, 5+
        dist = []
        for val in range(5):
            pct = round(float((np.count_nonzero(total_hrrbi == val) / self.num_simulations) * 100.0), 1)
            dist.append({"val": val, "pct": pct})
        pct_5_plus = round(float((np.count_nonzero(total_hrrbi >= 5) / self.num_simulations) * 100.0), 1)
        dist.append({"val": "5+", "pct": pct_5_plus})

        # Calculate sportsbook edge comparison
        if target_line <= 1.0:
            implied_book_prob = 68.0
            book_odds = "-190"
        elif target_line == 1.5:
            implied_book_prob = 56.5
            book_odds = "-130"
        else:
            implied_book_prob = 48.0
            book_odds = "+105"
        edge = round(win_prob - implied_book_prob, 1)

        return {
            "name": name,
            "team": team,
            "order": order,
            "line": target_line,
            "type": "Over",
            "win_prob": win_prob,
            "proj_total": proj_total,
            "exp_hits": exp_hits,
            "exp_runs": exp_runs,
            "exp_rbis": exp_rbis,
            "book_odds": book_odds,
            "implied_prob": implied_book_prob,
            "edge": edge,
            "dist": dist
        }
