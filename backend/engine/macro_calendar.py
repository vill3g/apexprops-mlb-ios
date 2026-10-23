"""
backend/engine/macro_calendar.py
High-Impact Macro Economic Event Calendar Horizon for Gemini 15M Gate.

Tracks major market-moving catalysts (FOMC Rate Decisions, FOMC Press Conferences,
CPI, PPI, NFP / Jobs, Core PCE, and GDP) to warn Gemini when entering trades inside
volatile macro event horizons.
"""

from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Canonical schedule of Tier-1 US economic releases (ET hours)
# Format: (DayOfWeek 0=Mon..4=Fri, Hour, Minute, EventName, Description)
# CPI: Typically 8:30 AM ET on release days
# FOMC: Typically 2:00 PM ET statement, 2:30 PM ET press conference
# NFP: Typically First Friday 8:30 AM ET
TIER_1_STANDARD_TIMES = [
    (8, 30, "MORNING_MACRO_DATA_CPI_NFP_PPI", "8:30 AM ET Tier-1 Economic Release (CPI/NFP/PPI/Jobless Claims)"),
    (10, 0, "CONSUMER_SENTIMENT_ISM_PMI", "10:00 AM ET ISM / PMI / Consumer Confidence Release"),
    (14, 0, "FOMC_RATE_DECISION", "2:00 PM ET FOMC Rate Decision / Statement Release"),
    (14, 30, "FOMC_PRESS_CONFERENCE", "2:30 PM ET Fed Chair Press Conference"),
]


def check_macro_event_horizon(dt_now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Checks if the current moment is near a Tier-1 high-volatility macro release window.
    Returns:
      - is_event_window: bool (True if within +-20 minutes of a Tier-1 release)
      - minutes_to_nearest_event: float (positive if ahead, negative if just passed)
      - nearest_event_name: str
      - volatility_freeze_recommended: bool
      - risk_warning: str
    """
    try:
        now_et = dt_now or datetime.now(ZoneInfo("America/New_York"))
        weekday = now_et.weekday()  # 0=Monday, 6=Sunday

        # Weekend check (crypto trades 24/7 but macro data releases happen Mon-Fri)
        if weekday >= 5:
            return {
                "is_event_window": False,
                "minutes_to_nearest_event": 999.0,
                "nearest_event_name": "NONE (WEEKEND)",
                "volatility_freeze_recommended": False,
                "risk_warning": "CLEAR (Weekend - No Major US Macro Data)",
            }

        now_minutes = now_et.hour * 60 + now_et.minute + now_et.second / 60.0

        min_diff = 999.0
        nearest_event = None
        nearest_name = "NONE"

        for h, m, code, desc in TIER_1_STANDARD_TIMES:
            target_minutes = h * 60 + m
            diff = target_minutes - now_minutes
            if abs(diff) < abs(min_diff):
                min_diff = diff
                nearest_event = desc
                nearest_name = code

        # High Volatility Event Window: 15 minutes before to 20 minutes after event
        is_event_window = (-20.0 <= min_diff <= 15.0)
        vol_freeze = (-10.0 <= min_diff <= 10.0)

        warning = "CLEAR"
        if vol_freeze:
            warning = f"HIGH_ALERT: Within 10m of {nearest_event}. Extreme volatility/whipsaw risk."
        elif is_event_window:
            warning = f"CAUTION: Inside 20m window of {nearest_event}."

        return {
            "is_event_window": is_event_window,
            "minutes_to_nearest_event": round(min_diff, 1),
            "nearest_event_name": nearest_name,
            "volatility_freeze_recommended": vol_freeze,
            "risk_warning": warning,
        }
    except Exception as e:
        logger.debug(f"[MacroCalendar] Error checking macro horizon: {e}")
        return {
            "is_event_window": False,
            "minutes_to_nearest_event": 999.0,
            "nearest_event_name": "ERROR",
            "volatility_freeze_recommended": False,
            "risk_warning": "CLEAR (Calendar unavailable)",
        }
