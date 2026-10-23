import time
import requests
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

# Caches
_MILESTONES_CACHE = {}
_LAST_MILESTONE_FETCH = 0
_EVENTS_CACHE = {}
_LAST_EVENTS_FETCH = 0

_LOCK = threading.Lock()

def fetch_all_milestones():
    # fetch milestones for sports
    dt = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://api.elections.kalshi.com/trade-api/v2/milestones?limit=500&category=Sports&minimum_start_date={dt}"
    milestones = []
    
    while url:
        success = False
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    milestones.extend(data.get("milestones", []))
                    cursor = data.get("cursor")
                    if cursor:
                        url = f"https://api.elections.kalshi.com/trade-api/v2/milestones?limit=500&category=Sports&minimum_start_date={dt}&cursor={cursor}"
                    else:
                        url = None
                    success = True
                    break
                elif r.status_code == 429:
                    time.sleep(1)
                else:
                    url = None
                    success = True
                    break
            except Exception:
                time.sleep(1)
        if not success:
            url = None
            
    return milestones

def get_milestones(force_refresh=False):
    global _MILESTONES_CACHE, _LAST_MILESTONE_FETCH
    now = time.time()
    
    with _LOCK:
        if force_refresh or now - _LAST_MILESTONE_FETCH > 600 or not _MILESTONES_CACHE:
            m_list = fetch_all_milestones()
            if m_list:
                _MILESTONES_CACHE = {m["id"]: m for m in m_list}
                _LAST_MILESTONE_FETCH = now
        return _MILESTONES_CACHE

def fetch_event(ticker: str):
    url = f"https://api.elections.kalshi.com/trade-api/v2/events/{ticker}?with_nested_markets=true"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                event = r.json().get("event")
                if event and "markets" in event:
                    for mkt in event["markets"]:
                        for field in ["yes_ask", "no_ask", "yes_bid", "no_bid", "last_price", "volume", "open_interest"]:
                            # parse _dollars or _fp if exists
                            if f"{field}_dollars" in mkt:
                                try: mkt[f"{field}_dollars_parsed"] = float(mkt[f"{field}_dollars"])
                                except: pass
                            if f"{field}_fp" in mkt:
                                try: mkt[f"{field}_fp_parsed"] = float(mkt[f"{field}_fp"])
                                except: pass
                return event
            elif r.status_code == 429:
                time.sleep(1)
        except Exception:
            pass
    return None

def get_events_for_tickers(tickers: List[str], force_refresh=False):
    global _EVENTS_CACHE, _LAST_EVENTS_FETCH
    now = time.time()
    
    with _LOCK:
        if force_refresh or now - _LAST_EVENTS_FETCH > 300:
            _EVENTS_CACHE.clear()
            _LAST_EVENTS_FETCH = now

    missing_tickers = []
    results = {}
    with _LOCK:
        for t in tickers:
            if t in _EVENTS_CACHE:
                results[t] = _EVENTS_CACHE[t]
            else:
                missing_tickers.append(t)
                
    if not missing_tickers:
        return results
        
    series_map = {}
    for t in missing_tickers:
        series = t.split("-")[0]
        if series not in series_map:
            series_map[series] = []
        series_map[series].append(t)
        
    for series, ts in series_map.items():
        url = f"https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={series}&with_nested_markets=true&limit=200"
        while url:
            success = False
            for attempt in range(3):
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        data = r.json()
                        for event in data.get("events", []):
                            if event and "markets" in event:
                                for mkt in event["markets"]:
                                    for field in ["yes_ask", "no_ask", "yes_bid", "no_bid", "last_price", "volume", "open_interest"]:
                                        if f"{field}_dollars" in mkt:
                                            try: mkt[f"{field}_dollars_parsed"] = float(mkt[f"{field}_dollars"])
                                            except: pass
                                        if f"{field}_fp" in mkt:
                                            try: mkt[f"{field}_fp_parsed"] = float(mkt[f"{field}_fp"])
                                            except: pass
                            with _LOCK:
                                _EVENTS_CACHE[event["ticker"]] = event
                        cursor = data.get("cursor")
                        if cursor:
                            url = f"https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={series}&with_nested_markets=true&limit=200&cursor={cursor}"
                        else:
                            url = None
                        success = True
                        break
                    elif r.status_code == 429:
                        time.sleep(1)
                    else:
                        url = None
                        success = True
                        break
                except Exception:
                    time.sleep(1)
            if not success:
                url = None
        
        for t in ts:
            if t in _EVENTS_CACHE:
                results[t] = _EVENTS_CACHE[t]
            else:
                with _LOCK:
                    _EVENTS_CACHE[t] = None
                
    return results

def detect_sport(m: dict) -> str:
    mt = m.get("type", "").lower()
    if "hockey" in mt: return "NHL"
    if "football" in mt and "nfl" in mt: return "NFL"
    if "football" in mt and "ncaa" in mt: return "NCAAF"
    if "basketball" in mt and "nba" in mt: return "NBA"
    if "basketball" in mt and "ncaa" in mt: return "NCAAB"
    if "baseball" in mt: return "MLB"
    if "soccer" in mt: return "SOCCER"
    if "tennis" in mt: return "TEN"
    if "ufc" in mt or "mma" in mt: return "UFC"
    # fallback to inspecting tickers
    tickers = m.get("primary_event_tickers", [])
    if not tickers: return "UNKNOWN"
    tk = tickers[0].upper()
    if "NHL" in tk: return "NHL"
    if "NFL" in tk: return "NFL"
    if "NBA" in tk: return "NBA"
    if "MLB" in tk: return "MLB"
    if "EPL" in tk or "MLS" in tk or "UCL" in tk or "LIGA" in tk or "SOCCER" in tk: return "SOCCER"
    if "UFC" in tk: return "UFC"
    if "ATP" in tk or "WTA" in tk or "ITF" in tk: return "TEN"
    if "NPB" in tk or "KBO" in tk: return "NPB_KBO"
    return "UNKNOWN"

def build_canonical_games() -> List[dict]:
    milestones = get_milestones()
    games = []
    for mid, m in milestones.items():
        det = m.get("details", {})
        sport = detect_sport(m)
        
        home_id = det.get("home_team_id") or det.get("first_competitor_id")
        away_id = det.get("away_team_id") or det.get("second_competitor_id")
        
        # sometimes names are in title "Away at Home" or "Home vs Away"
        # we will leave names blank if not explicitly available, we match Kalshi by exact IDs!
        
        # get status from details if live_data not queried
        status = det.get("status", "scheduled")
        
        all_tickers = list(set(m.get("primary_event_tickers", []) + m.get("related_event_tickers", [])))
        
        games.append({
            "milestone_id": mid,
            "sport": sport,
            "start_time_utc": m.get("start_date"),
            "status": status,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "event_tickers": all_tickers,
            "title": m.get("title", ""),
            "kalshi_listed": True
        })
    return games
