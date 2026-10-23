import urllib.request, json
sports = ['NFL', 'MLB', 'NHL', 'NBA', 'NCAAF', 'SOC', 'TEN', 'UFC', 'NPB']

for sport in sports:
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8058/api/engine/sports/events?sport={sport}', headers={'Authorization': 'Bearer 7'})
        resp = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
        data = json.loads(resp)
        print(f"\n--- {sport} ---")
        found = False
        for e in data.get('events', []):
            title = e.get('title')
            ticker = e.get('event_ticker')
            if not ticker: continue
            
            # just pick the first main one
            print(f"Ticker: {ticker}")
            print(f"Title: {title}")
            print(f"Our game_time: {e.get('game_time')}")
            found = True
            break
        if not found:
            print("No events found")
    except Exception as e:
        print(f"ERROR for {sport}: {e}")
