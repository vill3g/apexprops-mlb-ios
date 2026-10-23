"""
Pillar 4: Self-Healing Genetic Alpha Breeder (Genetic Meta-Learning)
for ShadowTrader Quant Lab.

Treats quantitative strategies as biological organisms with genetic code:
- Chromosomes: [entry_conditions, price_corridors, take_profit, stop_loss, target_regimes, style]
- Fitness Function: (live_win_rate * 0.45) + (sharpe_ratio * 0.35) - (max_drawdown * 0.20)
- Evolutionary Operators:
  1. Tournament Selection: Selects top-performing incubating or graduated strategies.
  2. Genetic Crossover (Recombination): Slices and splices condition genes between two parent strategies.
  3. Adaptive Mutation: Injects probabilistic parameter tweaks (e.g. nudging RSI 42 -> 45, or swapping EMA fast/slow)
     to discover emergent non-linear mathematical edges without human prompt fatigue.
"""
from __future__ import annotations

import copy
import logging
import random
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("genetic_alpha_breeder")


class GeneticAlphaBreeder:
    """Evolutionary Meta-Learning Engine that breeds winning quantitative alpha."""

    MUTATION_RATE = 0.25  # 25% chance per gene to mutate

    @classmethod
    def evolve_next_generation(
        cls,
        parent_strategies: List[Dict[str, Any]],
        target_asset: str = "BTC",
        generation_size: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Takes top parent strategies and produces evolved offspring strategies
        through genetic crossover and adaptive mutation.
        """
        if not parent_strategies:
            logger.info("[GeneticBreeder] No parents available for breeding.")
            return []

        offspring_list = []
        parents = sorted(parent_strategies, key=lambda s: cls._calculate_fitness(s), reverse=True)

        for gen_idx in range(generation_size):
            # Select parents via tournament selection
            if len(parents) >= 2:
                p1, p2 = random.sample(parents[:min(5, len(parents))], 2)
            else:
                p1 = parents[0]
                p2 = copy.deepcopy(p1)

            # Crossover: Recombine genetic traits
            child = cls._crossover(p1, p2, target_asset)

            # Mutation: Adaptive parameter exploration
            child = cls._mutate(child)

            offspring_list.append(child)

        logger.info(f"[GeneticBreeder] Successfully bred {len(offspring_list)} evolved offspring for {target_asset}.")
        return offspring_list

    @classmethod
    def _calculate_fitness(cls, strategy: Dict[str, Any]) -> float:
        """Computes multi-objective fitness score from live/walk-forward performance."""
        wr = float(strategy.get("live_win_rate") or strategy.get("win_rate") or 0.50)
        sharpe = float(strategy.get("sharpe") or strategy.get("sharpe_ratio") or 1.0)
        dd = float(strategy.get("max_drawdown") or strategy.get("drawdown") or 0.10)
        return (wr * 0.50) + (min(3.0, max(0.0, sharpe)) * 0.30) - (dd * 0.20)

    @classmethod
    def _crossover(cls, parent_a: Dict[str, Any], parent_b: Dict[str, Any], asset: str) -> Dict[str, Any]:
        """Slices and splices chromosomes between two parent trading strategies."""
        conds_a = parent_a.get("entry_conditions") or []
        conds_b = parent_b.get("entry_conditions") or []

        # Splice entry conditions (half from parent A, half from parent B)
        combined_conds = []
        if conds_a:
            combined_conds.append(copy.deepcopy(random.choice(conds_a)))
        if conds_b:
            b_cand = copy.deepcopy(random.choice(conds_b))
            if not any(c.get("indicator") == b_cand.get("indicator") for c in combined_conds):
                combined_conds.append(b_cand)

        if not combined_conds:
            combined_conds = conds_a[:2] if conds_a else [{"indicator": "rsi", "operator": "<", "threshold": 42.0}]

        # Recombine corridors and risk parameters
        min_p = round((float(parent_a.get("min_entry_price", 0.15)) + float(parent_b.get("min_entry_price", 0.15))) / 2.0, 2)
        max_p = round((float(parent_a.get("max_entry_price", 0.85)) + float(parent_b.get("max_entry_price", 0.85))) / 2.0, 2)
        tp = round((float(parent_a.get("take_profit_pct", 35.0)) + float(parent_b.get("take_profit_pct", 35.0))) / 2.0, 1)
        sl = round((float(parent_a.get("stop_loss_pct", 25.0)) + float(parent_b.get("stop_loss_pct", 25.0))) / 2.0, 1)

        name_prefix = random.choice([parent_a.get("name", "Alpha"), parent_b.get("name", "Beta")]).split(" - ")[0]
        child_id = f"gen_{uuid.uuid4().hex[:8]}"

        return {
            "strategy_id": child_id,
            "name": f"Cosmic {name_prefix} Evolved Mk.{random.randint(2, 9)}",
            "hypothesis": f"Evolved genetic recombination of {parent_a.get('name', 'Parent A')} and {parent_b.get('name', 'Parent B')}.",
            "asset": str(asset).upper(),
            "target_interval": parent_a.get("target_interval", "15m"),
            "style": random.choice([parent_a.get("style", "MOMENTUM"), parent_b.get("style", "MOMENTUM")]),
            "target_side": random.choice([parent_a.get("target_side", "YES"), parent_b.get("target_side", "YES")]),
            "entry_conditions": combined_conds,
            "min_entry_price": min(0.25, min_p),
            "max_entry_price": max(0.75, max_p),
            "take_profit_pct": tp,
            "stop_loss_pct": sl,
            "target_regimes": parent_a.get("target_regimes") or ["TREND_EXPANSION_MOMENTUM", "COMPRESSION_MEAN_REVERSION"],
            "base_edge": 0.08,
            "generation": max(int(parent_a.get("generation", 1)), int(parent_b.get("generation", 1))) + 1
        }

    @classmethod
    def _mutate(cls, child: Dict[str, Any]) -> Dict[str, Any]:
        """Applies random Gaussian mutation to condition thresholds and corridors."""
        conds = child.get("entry_conditions", [])
        for c in conds:
            if random.random() < cls.MUTATION_RATE:
                ind = str(c.get("indicator", "")).lower()
                thresh = c.get("threshold")
                if isinstance(thresh, (int, float)):
                    if ind == "rsi":
                        # Nudge RSI threshold by +/- 2.0 to 4.0 points
                        delta = random.choice([-3.0, -2.0, 2.0, 3.0])
                        c["threshold"] = max(20.0, min(80.0, round(thresh + delta, 1)))
                    elif ind == "atr":
                        c["threshold"] = round(thresh * random.choice([0.90, 1.10]), 2)
                    elif ind == "spread":
                        c["threshold"] = max(1, min(6, int(thresh + random.choice([-1, 1]))))

        # Mutation on entry price corridors
        if random.random() < cls.MUTATION_RATE:
            child["max_entry_price"] = min(0.85, max(0.70, round(float(child["max_entry_price"]) + random.choice([-0.05, 0.05]), 2)))
        if random.random() < cls.MUTATION_RATE:
            child["min_entry_price"] = max(0.10, min(0.30, round(float(child["min_entry_price"]) + random.choice([-0.05, 0.05]), 2)))

        return child
