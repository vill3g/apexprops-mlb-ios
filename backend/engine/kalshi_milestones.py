import requests
import datetime
import time
import threading

_MILESTONE_CACHE = []
_MILESTONE_CACHE_TIME = 0
_MILESTONE_LOCK = threading.Lock()

def get_kalshi_milestones():
    global _MILESTONE_CACHE, _MILESTONE_CACHE_TIME
    now = time.time()
    with _MILESTONE_LOCK:
        if now - _MILESTONE_CACHE_TIME < 300 and _MILESTONE_CACHE:
            return _MILESTONE_CACHE
            
        try:
            # fetch 6 hours ago to ensure we capture live/recent games
            six_hrs_ago = (datetime.datetime.utcnow() - datetime.timedelta(hours=6)).isoformat() + "Z"
            milestones = []
            cursor = ""
            for _ in range(3): # paginate up to 3 pages just in case
                url = f"https://api.elections.kalshi.com/trade-api/v2/milestones?limit=500&category=Sports&minimum_start_date={six_hrs_ago}"
                if cursor:
                    url += f"&cursor={cursor}"
                
                resp = requests.get(url, timeout=10).json()
                page_milestones = resp.get("milestones", [])
                milestones.extend(page_milestones)
                cursor = resp.get("cursor")
                if not cursor or not page_milestones:
                    break
            
            _MILESTONE_CACHE = milestones
            _MILESTONE_CACHE_TIME = now
        except Exception as e:
            print(f"Error fetching milestones: {e}")
            if not _MILESTONE_CACHE:
                return []
    return _MILESTONE_CACHE

def get_event_milestone_map():
    milestones = get_kalshi_milestones()
    event_map = {}
    for m in milestones:
        for t in m.get("primary_event_tickers", []):
            event_map[t] = m
        for t in m.get("related_event_tickers", []):
            event_map[t] = m
    return event_map
