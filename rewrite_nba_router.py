import re
with open("C:\\Users\\Vill3\\.gemini\\antigravity\\scratch\\apexprops-mlb-ios\\backend\\nba_router.py", "r", encoding="utf-8") as f:
    c = f.read()

replacement = """def get_nba_slate() -> Dict[str, Any]:
    global _slate_cache, _slate_cache_time
    import time
    import requests
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
    except:
        from datetime import timezone, timedelta
        ET = timezone(timedelta(hours=-4))
        
    now = time.time()
    if _slate_cache and (now - _slate_cache_time < 300):
        return _slate_cache
        
    # 1. Fetch ESPN slate
    espn_games = []
    is_today = False
    try:
        r = requests.get('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard', timeout=10)
        events = r.json().get('events', [])
        for e in events:
            comp = e.get('competitions', [{}])[0]
            status_desc = e.get('status', {}).get('type', {}).get('description', 'Upcoming')
            is_final = e.get('status', {}).get('type', {}).get('completed', False)
            date_str = e.get('date')
            
            start_time = "TBD"
            if date_str:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                local = dt.astimezone(ET)
                start_time = local.strftime("%I:%M %p ET").lstrip("0")
                if local.date() == datetime.now(ET).date():
                    is_today = True
                
            home = {}
            away = {}
            for c in comp.get('competitors', []):
                t = {
                    "name": c['team']['displayName'],
                    "abbr": c['team']['abbreviation'],
                    "score": c.get('score', "0")
                }
                if c['homeAway'] == 'home':
                    home = t
                else:
                    away = t
            if "Scheduled" in status_desc:
                status_desc = "Upcoming"
                    
            espn_games.append({
                "game_id": e.get("id"),
                "home_team": home,
                "away_team": away,
                "status": status_desc,
                "is_final": is_final,
                "start_time": start_time,
                "ml_pick": None,
                "spread_pick": None,
                "props": []
            })
    except Exception as e:
        print(f"ESPN NBA failed: {e}")
        
    # Filter out finished games if not today, or maybe just leave them and let frontend filter
    
    # 2. Match Kalshi markets to get models
    events = kalshi_client.get_nba_events()
    markets = kalshi_client.get_nba_markets()
    
    market_probs = {}
    for m in markets:
        evt_ticker = m.get("event_ticker")
        yes_ask = float(m.get("yes_ask_dollars", 0))
        yes_bid = float(m.get("yes_bid_dollars", 0))
        mid = (yes_ask + yes_bid) / 2.0
        if mid > 0:
            if evt_ticker not in market_probs:
                market_probs[evt_ticker] = {}
            market_probs[evt_ticker][m.get("yes_sub_title")] = mid * 100.0
            
    # For ESPN games, try to generate picks
    for g in espn_games:
        home_team = g["home_team"]["name"]
        away_team = g["away_team"]["name"]
        
        # Try to find matching Kalshi event
        evt_ticker = None
        market_implied_home = None
        
        # Simple name match hack
        for e in events:
            t = e.get("title", "")
            if home_team.split()[-1] in t and away_team.split()[-1] in t:
                evt_ticker = e.get("event_ticker")
                break
                
        if evt_ticker and evt_ticker in market_probs:
            for k, v in market_probs[evt_ticker].items():
                if home_team.split()[-1] in k:
                    market_implied_home = v
                    break
        
        if not g["is_final"]:
            sim = nba_model.simulate_matchup(home_team, away_team, market_implied_home_prob=market_implied_home)
            if sim:
                h_prob = sim["home_win_prob"]
                a_prob = sim["away_win_prob"]
                pick_home = h_prob >= a_prob
                
                pick_team = home_team if pick_home else away_team
                pick_prob = h_prob if pick_home else a_prob
                
                ev = sim["edges"]["home_expected_value"] if pick_home else sim["edges"]["away_expected_value"]
                prob_delta = sim["edges"]["home_probability_delta"] if pick_home else sim["edges"]["away_probability_delta"]
                kelly = sim["kelly_criterion_pct"]["home"] if pick_home else sim["kelly_criterion_pct"]["away"]
                
                g["ml_pick"] = {
                    "team": pick_team,
                    "prob": pick_prob,
                    "edge": ev,
                    "ev": ev,
                    "probability_delta": prob_delta,
                    "kelly": kelly,
                    "odds": "-110",
                    "conf": "MED"
                }
                g["spread_pick"] = {
                    "pick": f"{pick_team} -1.5",
                    "prob": 50.0,
                    "edge": 0.0,
                    "ev": 0.0,
                    "kelly": 0.0,
                    "odds": "-110"
                }
        
    res = {"status": "success", "count": len(espn_games), "games": espn_games, "is_today": is_today}
    _slate_cache = res
    _slate_cache_time = now
    return res"""

import re
c = re.sub(r'def get_nba_slate\(\) -> Dict\[str, Any\]:.*?(?=\n@nba_router\.get\("/top_picks"\))', replacement + "\n", c, flags=re.DOTALL)

with open("C:\\Users\\Vill3\\.gemini\\antigravity\\scratch\\apexprops-mlb-ios\\backend\\nba_router.py", "w", encoding="utf-8") as f:
    f.write(c)
    
print("Patched nba_router.py!")
