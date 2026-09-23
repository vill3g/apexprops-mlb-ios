import requests
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta
import pytz
import logging
import threading

logger = logging.getLogger(__name__)

FF_XML_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
_news_cache = {"events": [], "last_fetched": 0.0}
_cache_lock = threading.Lock()

# Currencies we care about filtering
RELEVANT_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD"}
# Time buffer to avoid trading before/after high-impact news (in minutes)
NEWS_BUFFER_MINUTES = 30

def fetch_weekly_news():
    """Fetch and parse ForexFactory XML for High Impact ('High') events."""
    now = time.time()
    with _cache_lock:
        # Cache for 4 hours to avoid spamming the XML endpoint
        if _news_cache["events"] and (now - _news_cache["last_fetched"] < 14400):
            return _news_cache["events"]

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(FF_XML_URL, headers=headers, timeout=5)
        r.raise_for_status()
        
        root = ET.fromstring(r.content)
        high_impact_events = []
        
        # FF timezone is EST in the XML by default, formatted like: 
        # <date>09-22-2026</date>
        # <time>8:30am</time>
        
        est_tz = pytz.timezone("America/New_York")
        
        for event in root.findall("event"):
            impact = event.find("impact").text if event.find("impact") is not None else ""
            if impact != "High":
                continue
                
            currency = event.find("country").text if event.find("country") is not None else ""
            if currency not in RELEVANT_CURRENCIES:
                continue
                
            date_str = event.find("date").text
            time_str = event.find("time").text
            title = event.find("title").text
            
            # Handle "All Day" or undefined times
            if not time_str or "All Day" in time_str or "Tentative" in time_str:
                continue
                
            # Parse datetime
            try:
                dt_str = f"{date_str} {time_str}"
                event_dt_naive = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                event_dt_est = est_tz.localize(event_dt_naive)
                
                high_impact_events.append({
                    "title": title,
                    "currency": currency,
                    "timestamp": event_dt_est.timestamp(),
                    "datetime": event_dt_est.isoformat()
                })
            except Exception as e:
                logger.debug(f"Failed to parse news time '{date_str} {time_str}': {e}")
                
        with _cache_lock:
            _news_cache["events"] = high_impact_events
            _news_cache["last_fetched"] = now
            
        logger.info(f"Refreshed economic calendar. Found {len(high_impact_events)} upcoming high-impact events.")
        return high_impact_events
        
    except Exception as e:
        logger.error(f"Failed to fetch ForexFactory calendar: {e}")
        # Return whatever is in cache
        return _news_cache["events"]

def is_safe_to_trade(pair: str) -> dict:
    """
    Checks if we are within the NEWS_BUFFER_MINUTES of a high-impact event
    relevant to the given currency pair.
    """
    events = fetch_weekly_news()
    if not events:
        return {"safe": True, "reason": "No news data"}
        
    now = time.time()
    
    # Extract the two currencies from the pair (e.g. "EURUSD" -> ["EUR", "USD"])
    currencies = [pair[:3], pair[3:]]
    
    for event in events:
        if event["currency"] in currencies:
            time_diff = event["timestamp"] - now
            minutes_to_event = time_diff / 60.0
            
            # If the event is in the past, time_diff is negative.
            # We want to block if we are within [-30, +30] minutes of the event.
            if -NEWS_BUFFER_MINUTES <= minutes_to_event <= NEWS_BUFFER_MINUTES:
                return {
                    "safe": False,
                    "reason": f"High Impact News ({event['title']} for {event['currency']})",
                    "minutes_to_event": round(minutes_to_event, 1)
                }
                
    return {"safe": True, "reason": "Clear"}

if __name__ == "__main__":
    # Test the module
    print("Fetching calendar...")
    status = is_safe_to_trade("EURUSD")
    print(f"Safe to trade EURUSD? {status}")
