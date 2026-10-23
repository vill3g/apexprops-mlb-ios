import urllib.request
import json

req = urllib.request.Request('http://127.0.0.1:8058/api/engine/sports/events')
resp = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
data = json.loads(resp)

print(f"Total events: {len(data['events'])}")
for ev in data['events']:
    if ev['ticker'] == 'KXMLBGAME-26OCT081700CLECWS':
        print('KXMLBGAME-26OCT081700CLECWS:')
        print(f"   game_time: {ev.get('game_time')}")
        print(f"   title: {ev.get('title')}")
