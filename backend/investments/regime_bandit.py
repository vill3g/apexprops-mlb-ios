"""
backend.investments.regime_bandit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Frontier 3: Market Regime Detection & Thompson Sampling Multi-Armed Bandit RL Capital Sizing.
"""

import math
import random
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class RegimeBanditEngine:
    """Classifies Market Regimes & dynamically samples optimal strategy allocations."""

    SETUPS = ["ORB_BREAKOUT", "VWAP_RECLAIM", "SQUEEZE_IGNITION"]

    @staticmethod
    def detect_market_regime(
        bars: List[Dict[str, Any]],
        adx: float = 24.0,
        atr: float = 1.5,
        rvol: float = 1.2
    ) -> Dict[str, Any]:
        """
        Classifies current market tape into:
        1. TREND_EXPANSION_BULL
        2. TREND_EXPANSION_BEAR
        3. COMPRESSION_MEAN_REVERT
        4. HIGH_VOLATILITY_CHOP
        """
        if not bars:
            return {"regime": "COMPRESSION_MEAN_REVERT", "allowed_setups": ["VWAP_RECLAIM"], "volatility_score": 1.0}

        close_prices = [float(b.get("close", 0)) for b in bars if b.get("close")]
        if not close_prices:
            return {"regime": "COMPRESSION_MEAN_REVERT", "allowed_setups": ["VWAP_RECLAIM"], "volatility_score": 1.0}

        recent_return = (close_prices[-1] - close_prices[0]) / max(close_prices[0], 0.01)

        if adx >= 28.0 and recent_return > 0.005:
            regime = "TREND_EXPANSION_BULL"
            allowed_setups = ["ORB_BREAKOUT", "VWAP_RECLAIM"]
            mult = 1.2
        elif adx >= 28.0 and recent_return < -0.005:
            regime = "TREND_EXPANSION_BEAR"
            allowed_setups = ["ORB_BREAKOUT", "VWAP_RECLAIM"]
            mult = 1.2
        elif atr > 3.0 and adx < 20.0:
            regime = "HIGH_VOLATILITY_CHOP"
            allowed_setups = []  # Mutes breakout entries during chop
            mult = 0.5
        else:
            regime = "COMPRESSION_MEAN_REVERT"
            allowed_setups = ["VWAP_RECLAIM", "SQUEEZE_IGNITION"]
            mult = 1.0

        return {
            "regime": regime,
            "allowed_setups": allowed_setups,
            "adx": round(adx, 1),
            "atr": round(atr, 2),
            "rvol": round(rvol, 2),
            "confidence_multiplier": mult,
            "guidance": f"Market state {regime} with ADX {adx:.1f}. Active setups: {', '.join(allowed_setups) or 'NONE (CHOP)'}."
        }

    @staticmethod
    def sample_thompson_allocations(
        setup_stats: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Applies Bayesian Thompson Sampling using Beta(alpha, beta) distribution.
        alpha = 1 + wins, beta = 1 + losses.
        Returns sampled score and prioritized setup hierarchy.
        """
        sampled_weights = {}

        for setup in RegimeBanditEngine.SETUPS:
            stats = setup_stats.get(setup, {})
            wins = int(stats.get("wins", 0))
            losses = int(stats.get("losses", 0))

            # Beta distribution parameters (Laplace smoothing prior)
            alpha = max(1.0, 1.0 + wins)
            beta = max(1.0, 1.0 + losses)

            # Draw sample from Beta distribution
            sample = random.betavariate(alpha, beta)
            sampled_weights[setup] = round(sample, 4)

        # Rank setups by sampled draw
        ranked = sorted(sampled_weights.items(), key=lambda x: x[1], reverse=True)

        return {
            "top_setup": ranked[0][0],
            "top_weight": ranked[0][1],
            "sampled_weights": sampled_weights,
            "ranking": [r[0] for r in ranked]
        }
