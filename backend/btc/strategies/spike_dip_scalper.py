"""
15M Volatility Spike & Dip Scalper for Kalshi Crypto & Forex Contracts.
Exploits temporary wicks, market-maker liquidity vacuums, and sharp overreactions.

Core Logic:
1. Calculates theoretical probability fair-value curve based on distance from strike:
   P_fair = 1.0 / (1.0 + exp(- (spot - strike) / (ATR * volatility_scaler)))
2. Measures market book pricing vs fair-value:
   - DIP MISPRICING: When spot is structurally above/around strike, but a sudden market sell
     causes the YES ask to dump into a deep discount (e.g. 20c - 38c vs fair value 50c+).
   - SPIKE EXHAUSTION: When an aggressive buyer sweeps the book up to 80c - 90c while spot
     is still far below strike with little time left (opportunity to buy cheap NO at 10c - 20c).
3. Executes a fast-reaction mean-reversion scalp aiming for a quick +25% to +50% snapback
   or bank exit when contract reverts to fair value.
"""

import math
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class SpikeDipScalper:
    """Detects and scores intraday binary contract spike/dip mispricing opportunities."""

    @staticmethod
    def calculate_fair_value_prob(spot_price: float, strike_price: float, atr: float = 120.0, side: str = "YES") -> float:
        """Computes continuous theoretical probability based on distance to strike relative to ATR."""
        if atr <= 0:
            atr = 120.0
        diff = (spot_price - strike_price) if side == "YES" else (strike_price - spot_price)
        # Scale factor calibrated for 15M BTC/ETH/SOL contracts
        k = max(60.0, atr * 0.75)
        prob = 1.0 / (1.0 + math.exp(-diff / k))
        return round(max(0.02, min(0.98, prob)), 3)

    @classmethod
    def evaluate_opportunity(
        cls,
        ticker: str,
        spot_price: float,
        strike_price: float,
        yes_bid: float,
        yes_ask: float,
        no_bid: float,
        no_ask: float,
        seconds_left: int,
        atr: float = 120.0,
        min_edge_cents: float = 3.5
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates orderbook for an actionable Spike or Dip scalp.
        Returns trade recommendation dict or None if no edge.
        """
        # Only trade between 12 minutes left and 2 minutes left (avoid initial noise and settlement freeze)
        if seconds_left > 720 or seconds_left < 120:
            return None

        if spot_price <= 0 or strike_price <= 0:
            return None

        fair_yes = cls.calculate_fair_value_prob(spot_price, strike_price, atr, side="YES")
        fair_no = round(1.0 - fair_yes, 3)

        min_edge_dollars = min_edge_cents / 100.0

        # Opportunity 1: SPIKE EXHAUSTION FADE (YES spiked unrealistically high despite spot deficit)
        # When YES ask/bid is bid up to >= 70c but fair value is <= 45c, buying NO at <= 30c offers massive positive expectancy
        if fair_yes <= 0.45 and yes_bid >= 0.70 and 0.10 <= no_ask <= 0.30:
            edge = fair_no - no_ask
            if edge >= min_edge_dollars:
                return {
                    "action": "BUY",
                    "side": "NO",
                    "ticker": ticker,
                    "target_price": no_ask,
                    "fair_value": fair_no,
                    "edge_cents": round(edge * 100.0, 1),
                    "setup_type": "15M_SPIKE_FADE",
                    "reason": f"15M SPIKE FADE: YES spiked to ${yes_bid:.2f} while fair is ${fair_yes:.2f}; buying discounted NO @ ${no_ask:.2f}",
                    "expected_tp_price": min(0.90, round(no_ask * 1.40, 2))
                }

        # Opportunity 2: SPIKE EXHAUSTION FADE (NO spiked unrealistically high despite spot surplus)
        # When NO ask/bid is bid up to >= 70c but fair value is <= 45c, buying YES at <= 30c offers massive positive expectancy
        if fair_no <= 0.45 and no_bid >= 0.70 and 0.10 <= yes_ask <= 0.30:
            edge = fair_yes - yes_ask
            if edge >= min_edge_dollars:
                return {
                    "action": "BUY",
                    "side": "YES",
                    "ticker": ticker,
                    "target_price": yes_ask,
                    "fair_value": fair_yes,
                    "edge_cents": round(edge * 100.0, 1),
                    "setup_type": "15M_SPIKE_FADE",
                    "reason": f"15M SPIKE FADE: NO spiked to ${no_bid:.2f} while fair is ${fair_no:.2f}; buying discounted YES @ ${yes_ask:.2f}",
                    "expected_tp_price": min(0.90, round(yes_ask * 1.40, 2))
                }

        # Opportunity 3: DIP BUY SCALP (YES contract dumped on a wick, but spot still structurally supported)
        # Condition: Fair value >= 0.48 (spot above/at strike), but YES ask dropped into deep discount (<= 0.40)
        if fair_yes >= 0.48 and 0.15 <= yes_ask <= 0.40:
            edge = fair_yes - yes_ask
            if edge >= min_edge_dollars:
                return {
                    "action": "BUY",
                    "side": "YES",
                    "ticker": ticker,
                    "target_price": yes_ask,
                    "fair_value": fair_yes,
                    "edge_cents": round(edge * 100.0, 1),
                    "setup_type": "15M_DIP_SCALP",
                    "reason": f"15M DIP SCALP: YES ask at ${yes_ask:.2f} is deep discount vs fair value ${fair_yes:.2f} (+{edge*100:.1f}¢ edge)",
                    "expected_tp_price": min(0.90, round(yes_ask * 1.35, 2))
                }

        # Opportunity 4: DIP BUY SCALP (NO contract dumped on a temporary upward wick, but spot below strike)
        # Condition: Fair value NO >= 0.48 (spot below/at strike), but NO ask dropped into discount (<= 0.40)
        if fair_no >= 0.48 and 0.15 <= no_ask <= 0.40:
            edge = fair_no - no_ask
            if edge >= min_edge_dollars:
                return {
                    "action": "BUY",
                    "side": "NO",
                    "ticker": ticker,
                    "target_price": no_ask,
                    "fair_value": fair_no,
                    "edge_cents": round(edge * 100.0, 1),
                    "setup_type": "15M_DIP_SCALP",
                    "reason": f"15M DIP SCALP: NO ask at ${no_ask:.2f} is deep discount vs fair value ${fair_no:.2f} (+{edge*100:.1f}¢ edge)",
                    "expected_tp_price": min(0.90, round(no_ask * 1.35, 2))
                }

        return None
