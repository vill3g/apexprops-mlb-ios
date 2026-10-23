import re
with open('backend/routes/engine.py', 'r') as f:
    lines = f.readlines()

start = -1
end = -1
for i, line in enumerate(lines):
    if line.startswith('def _fetch_all_slates_for_times'):
        start = i
    if start != -1 and i > start and line.startswith('def '):
        end = i
        break

if start != -1:
    new_func = '''def _fetch_all_slates_for_times(base_url='http://127.0.0.1:8057'):
    global _SLATE_CACHE_TIME, _SLATE_CACHE
    import time
    if time.time() - _SLATE_CACHE_TIME < 300 and _SLATE_CACHE:
        return _SLATE_CACHE
    import httpx, concurrent.futures
    endpoints = [
        ('NHL', '/api/hockey/slate'), ('MLB', '/api/mlb/games'), ('NBA', '/api/nba/slate'), 
        ('NCAAF', '/api/ncaaf/slate'), ('SOC', '/api/soccer/slate'), ('TEN', '/api/tennis/slate'), 
        ('UFC', '/api/ufc/slate'), ('NPB', '/api/npb_kbo/slate'), ('KBO', '/api/npb_kbo/slate'), ('NFL', '/api/nfl/games')
    ]
    all_games = []
    def fetch_endpoint(args):
        sport, ep = args
        try:
            with httpx.Client(timeout=7.0) as c:
                r = c.get(f"{base_url}{ep}")
                if r.status_code == 200:
                    d = r.json()
                    games = d.get('games') or d.get('slate') or d.get('events') or d
                    if isinstance(games, dict) and 'games' in games:
                        games = games['games']
                    if isinstance(games, list):
                        return (sport, games)
        except Exception:
            pass
        return (sport, [])

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for res in executor.map(fetch_endpoint, endpoints):
            sport, games = res
            for g in games:
                all_games.append((sport, g))
            
    slate_map = {}
    for sport, g in all_games:
        if sport not in slate_map:
            slate_map[sport] = {}
        
        ht = g.get('home_team', {})
        at = g.get('away_team', {})
        team1 = ht.get('name') or ht.get('abbreviation') or ht.get('abbr') or g.get('name') or g.get('predicted_team')
        team2 = at.get('name') or at.get('abbreviation') or at.get('abbr') or g.get('opponent')
        
        start_time = g.get('start_time') or g.get('game_datetime') or g.get('commence_time')
        
        if sport in ('NPB', 'KBO') and start_time and 'ET' in start_time:
            if '18:00' in start_time or '13:00' in start_time or '14:00' in start_time:
                start_time = None
        
        import re
        for t in [team1, team2]:
            if t:
                t = re.sub(r'Game\s+\d+:\s*', '', str(t), flags=re.IGNORECASE)
                t_clean = re.sub(r'[^a-zA-Z0-9]', '', t).lower()

                if slate_map[sport].get(t_clean) in ('TBD', None, '') or start_time not in ('TBD', None, ''):
                    slate_map[sport][t_clean] = start_time

                parts = t.split()
                if len(parts) > 1:
                    mascot_clean = re.sub(r'[^a-zA-Z0-9]', '', parts[-1]).lower()
                    if mascot_clean:
                        if slate_map[sport].get(mascot_clean) in ('TBD', None, '') or start_time not in ('TBD', None, ''):
                            slate_map[sport][mascot_clean] = start_time

    _SLATE_CACHE = slate_map
    _SLATE_CACHE_TIME = time.time()
    return slate_map

'''
    new_lines = lines[:start] + [new_func] + lines[end:]
    with open('backend/routes/engine.py', 'w') as f:
        f.writelines(new_lines)
    print('Replaced')
else:
    print('Not found')
