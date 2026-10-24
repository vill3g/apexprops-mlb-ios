"""One place that turns a stored trade timestamp into a real time.

Trades are stamped in two formats: the bot's own "2026-10-23 07:32:22 PM ET" (12-hour, with
AM/PM) and ISO 8601 ("2026-10-23T19:33:53-04:00"). Comparing either as text is wrong: "07:00 PM"
sorts before "11:00 AM", and an ISO stamp sorts after every 12-hour stamp on the same day.
"""
import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")


def trade_epoch(ts) -> float:
    """Unix seconds for a stored timestamp, or 0.0 if it can't be read."""
    if isinstance(ts, (int, float)):
        return float(ts)
    if not isinstance(ts, str) or not ts:
        return 0.0
    try:
        if "ET" in ts:
            return datetime.datetime.strptime(ts, "%Y-%m-%d %I:%M:%S %p ET").replace(tzinfo=_ET).timestamp()
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0
