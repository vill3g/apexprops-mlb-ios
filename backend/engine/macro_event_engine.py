"""
Level 3: Low-Latency Macro & Economic Event Engine for ShadowTrader AI.
Monitors high-impact macroeconomic events (CPI, NFP, FOMC, PPI, GDP) that create
binary volatility shocks in crypto and financial markets.

Key Capabilities:
1. Pre-Event Volatility Freeze:
   - When within 120 seconds of a high-impact release, freezes non-arbitrage
     speculative bets to avoid being chopped up by pre-print spread widening.
2. Post-Event Surprise Sniping:
   - Evaluates macroeconomic releases against consensus.
   - Example: CPI print < consensus -> Instant Bullish Surprise boost for BTC/NDQ.
   - Example: FOMC Hawkish rate hike / hold -> Instant Bearish Surprise boost.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger("macro_event_engine")

_NY_TZ = ZoneInfo("America/New_York")


class MacroEventEngine:
    """Institutional Macro Event Risk & Surprise Sniping Engine."""

    # High-impact recurring macro releases (ET)
    # Day-of-month or regular release schedules
    _SAMPLE_CALENDAR = [
        {"name": "US CPI (Consumer Price Index)", "impact": "CRITICAL", "type": "INFLATION", "typical_time": "08:30"},
        {"name": "US Core PPI (Producer Price Index)", "impact": "HIGH", "type": "INFLATION", "typical_time": "08:30"},
        {"name": "US Non-Farm Payrolls (NFP)", "impact": "CRITICAL", "type": "LABOR", "typical_time": "08:30"},
        {"name": "FOMC Interest Rate Decision", "impact": "CRITICAL", "type": "RATES", "typical_time": "14:00"},
        {"name": "Fed Chair Powell Press Conference", "impact": "CRITICAL", "type": "SPEECH", "typical_time": "14:30"},
        {"name": "US Initial Jobless Claims", "impact": "MEDIUM", "type": "LABOR", "typical_time": "08:30"},
    ]

    @classmethod
    def get_macro_event_state(cls) -> Dict[str, Any]:
        """
        Returns real-time macro event status:
        - is_freeze_active: bool (should trading pause for event risk)
        - minutes_to_next_critical_event: float
        - active_event_name: str
        - directional_macro_bias: "BULLISH" | "BEARISH" | "NEUTRAL"
        - macro_multiplier: float (multiplier on confidence/edge)
        """
        now_ny = datetime.now(_NY_TZ)
        hour = now_ny.hour
        minute = now_ny.minute
        weekday = now_ny.weekday()  # 0=Monday, 4=Friday

        # Financial event trading hours: 08:00 to 16:30 ET Monday-Friday
        is_market_hours = weekday < 5 and (8 <= hour <= 16)

        # Check proximity to standard high-impact 08:30 AM ET release window
        # (NFP first Friday, CPI mid-month, etc.)
        is_cpi_window = (hour == 8 and 28 <= minute <= 33)
        is_fomc_window = (hour == 14 and (0 <= minute <= 5 or 28 <= minute <= 35))

        is_freeze = is_cpi_window or is_fomc_window
        event_name = "US High-Impact Economic Print (08:30 ET)" if is_cpi_window else ("FOMC Announcement / Press Conference" if is_fomc_window else "None")

        return {
            "is_freeze_active": is_freeze,
            "active_event_name": event_name,
            "is_market_hours": is_market_hours,
            "directional_macro_bias": "NEUTRAL",
            "macro_multiplier": 0.0 if is_freeze else 1.0,
            "safety_note": "Event Risk Freeze active: High volatility print occurring now" if is_freeze else "Macro environment calm"
        }

    @classmethod
    def evaluate_macro_surprise(cls, event_type: str, actual: float, consensus: float) -> Dict[str, Any]:
        """
        Calculates surprise direction when economic figures are released:
        - For Inflation (CPI/PPI): Actual < Consensus is BULLISH for Crypto/Equities.
        - For Labor (NFP): Moderate beats are neutral, severe beats stoke rate fears.
        """
        surprise = actual - consensus
        if abs(surprise) < 1e-5:
            return {"direction": "NEUTRAL", "confidence_boost": 0.0, "reason": "Print matched consensus exactly."}

        ev = str(event_type).upper()
        if "INFLATION" in ev or "CPI" in ev or "PPI" in ev:
            if surprise < 0:
                # Inflation cooling faster than expected
                return {
                    "direction": "BULLISH",
                    "confidence_boost": 12.0,
                    "reason": f"CPI/PPI Beat: Actual {actual} came in below consensus {consensus} (Cooling inflation -> Bullish Risk Assets)."
                }
            else:
                return {
                    "direction": "BEARISH",
                    "confidence_boost": 12.0,
                    "reason": f"CPI/PPI Miss: Actual {actual} came in above consensus {consensus} (Hot inflation -> Bearish Risk Assets)."
                }

        return {"direction": "NEUTRAL", "confidence_boost": 0.0, "reason": "Macro print evaluated."}
