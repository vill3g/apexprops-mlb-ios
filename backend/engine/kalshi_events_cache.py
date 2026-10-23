import time
import requests
import threading
import traceback
import logging

logger = logging.getLogger(__name__)

_GLOBAL_EVENTS_CACHE = {}
_GLOBAL_EVENTS_LOCK = threading.Lock()
_LAST_FETCH_TIME = 0

_MILESTONES_CACHE = []
_MILESTONES_MAP = {}
_LAST_MILESTONE_TIME = 0

def update_events_cache():
    global _GLOBAL_EVENTS_CACHE, _LAST_FETCH_TIME
    try:
        from backend.routes.engine_sports import _SPORTS_SERIES_MAP
        import concurrent.futures
        
        all_series = []
        for series_list in _SPORTS_SERIES_MAP.values():
            all_series.extend(series_list)
            
        events_by_series = {}
        
        def fetch_series(s):
            url = f"https://external-api.kalshi.com/trade-api/v2/events?series_ticker={s}&status=open&with_nested_markets=true"
            for attempt in range(5):
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        evs = r.json().get("events", [])
                        cursor = r.json().get("cursor")
                        if cursor:
                            r2 = requests.get(url + f"&cursor={cursor}", timeout=10)
                            if r2.status_code == 200:
                                evs.extend(r2.json().get("events", []))
                        return s, evs
                    elif r.status_code == 429:
                        import time
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        break
                except:
                    import time
                    time.sleep(0.5 * (attempt + 1))
            return s, []

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            for s, evs in executor.map(fetch_series, set(all_series)):
                events_by_series[s] = evs
                
        with _GLOBAL_EVENTS_LOCK:
            _GLOBAL_EVENTS_CACHE = events_by_series
            
    except Exception as e:
        logger.error(f"Error fetching global Kalshi events: {e}"); import traceback; traceback.print_exc()

def update_milestones_cache():
    global _MILESTONES_MAP
    try:
        import requests
        from datetime import datetime, timezone, timedelta
        start_iso = (datetime.now(timezone.utc) - timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ")
        m_map = {}
        cursor = None
        for _ in range(12):
            url = f"https://external-api.kalshi.com/trade-api/v2/milestones?limit=500&category=Sports&minimum_start_date={start_iso}"
            if cursor:
                url += f"&cursor={cursor}"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            ms = data.get("milestones", [])
            for m in ms:
                mid = m.get("id") or m.get("milestone_id")
                if mid:
                    m_map[mid] = m
                for ev in m.get("primary_event_tickers", []) or []:
                    m_map[ev] = m
                    if "-" in ev:
                        suf = ev.split("-", 1)[1]
                        if suf and f"SUFFIX:{suf}" not in m_map:
                            m_map[f"SUFFIX:{suf}"] = m
                for ev in m.get("related_event_tickers", []) or []:
                    m_map[ev] = m
                    if "-" in ev:
                        suf = ev.split("-", 1)[1]
                        if suf and f"SUFFIX:{suf}" not in m_map:
                            m_map[f"SUFFIX:{suf}"] = m
                details = m.get("details", {})
                if isinstance(details, dict):
                    main_tk = details.get("main_game_event_ticker")
                    if main_tk:
                        m_map[main_tk] = m
                        if "-" in main_tk:
                            suf = main_tk.split("-", 1)[1]
                            if suf:
                                m_map[f"SUFFIX:{suf}"] = m
            cursor = data.get("cursor")
            if not cursor or not ms:
                break
        if m_map:
            _MILESTONES_MAP = m_map
    except Exception as e:
        logger.debug(f"[EventsCache] Milestone fetch error: {e}")

_FETCH_LOCK = threading.Lock()

def get_series_events(series_ticker: str) -> list:
    try:
        from backend.engine.kalshi_market_cache import get_market_cache_instance, USE_MARKET_CACHE
        if USE_MARKET_CACHE:
            cache = get_market_cache_instance()
            if cache.is_cache_healthy() or len(cache._markets) > 0:
                return cache.get_series_events(series_ticker)
    except Exception as e:
        logger.debug(f"[EventsCache] Error querying live market cache: {e}")

    global _LAST_FETCH_TIME, _GLOBAL_EVENTS_CACHE
    if time.time() - _LAST_FETCH_TIME > 60:
        _LAST_FETCH_TIME = time.time()
        threading.Thread(target=update_events_cache, daemon=True).start()

    with _GLOBAL_EVENTS_LOCK:
        return list(_GLOBAL_EVENTS_CACHE.get(series_ticker, []))


_FETCH_LOCK2 = threading.Lock()

def get_milestone_map():
    try:
        from backend.engine.kalshi_market_cache import get_market_cache_instance, USE_MARKET_CACHE
        if USE_MARKET_CACHE:
            cache = get_market_cache_instance()
            m_map = cache.get_milestone_map()
            if m_map:
                return m_map
            if cache.is_cache_healthy() or len(cache._markets) > 0:
                return dict(_MILESTONES_MAP)
    except Exception as e:
        logger.debug(f"[EventsCache] Error querying live milestone cache: {e}")

    global _LAST_MILESTONE_TIME
    if time.time() - _LAST_MILESTONE_TIME > 300:
        _LAST_MILESTONE_TIME = time.time()
        threading.Thread(target=update_milestones_cache, daemon=True).start()

    return dict(_MILESTONES_MAP)

