import urllib.request, json
sports = ['NFL', 'MLB', 'NHL', 'NBA', 'NCAAF', 'SOC', 'TEN', 'UFC', 'NPB']

out = []
for sport in sports:
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8058/api/engine/sports/events?sport={sport}', headers={'Authorization': 'Bearer 7'})
        resp = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        data = json.loads(resp)
        found = False
        for e in data.get('events', []):
            if e.get('event_ticker'):
                out.append(f"{sport}: {e.get('event_ticker')} | {e.get('game_time')}")
                found = True
                break
        if not found:
            out.append(f"{sport}: No events")
    except Exception as e:
        out.append(f"{sport}: ERROR {e}")

print('\n'.join(out))
