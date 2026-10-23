import urllib.request
import json
req = urllib.request.Request("http://127.0.0.1:8058/api/engine/sports/events?sport=NFL")
req.add_header("Authorization", "Bearer 1")
try:
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode())
    c={'t':0,'ta':0,'s':0,'sa':0,'m':0,'ma':0}
    for e in data.get("events", []):
        pt = e.get("prop_type")
        ha = e.get("has_ai_prediction")
        if pt == "Total (O/U)":
            c['ta'] += 1
            if ha: c['t'] += 1
        elif pt == "Spread":
            c['sa'] += 1
            if ha: c['s'] += 1
        elif pt == "Moneyline":
            c['ma'] += 1
            if ha: c['m'] += 1
    print(f"Total: {c['t']}/{c['ta']}, Spread: {c['s']}/{c['sa']}, ML: {c['m']}/{c['ma']}")
except Exception as e:
    print(e)
