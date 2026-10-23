import json, time, requests
base = "https://api.elections.kalshi.com/trade-api/v2"
for series in ("KXATPMATCH", "KXNFLGAME", "KXNHLGAME", "KXUFCFIGHT", "KXEPLGAME", "KXMLBGAME"):
    try:
        r = requests.get(f"{base}/markets", params={"series_ticker": series, "status": "settled", "limit": 100}, timeout=20)
        ms = r.json().get("markets", [])
        res = [m for m in ms if m.get("result") in ("yes", "no")]
        print(series, r.status_code, "settled markets:", len(ms), "with result:", len(res),
              "cursor" if r.json().get("cursor") else "no-more",
              "| sample:", (ms[0].get("ticker"), ms[0].get("close_time"), ms[0].get("last_price"), ms[0].get("result")) if ms else None)
    except Exception as e:
        print(series, "ERR", e)
# candlesticks for one settled tennis market
r = requests.get(f"{base}/markets", params={"series_ticker": "KXATPMATCH", "status": "settled", "limit": 5}, timeout=20)
ms = r.json().get("markets", [])
if ms:
    m = ms[0]
    end = int(time.time()); start = end - 60 * 86400
    for path in (f"/series/KXATPMATCH/markets/{m['ticker']}/candlesticks",):
        rr = requests.get(base + path, params={"start_ts": start, "end_ts": end, "period_interval": 60}, timeout=20)
        js = rr.json()
        print("candles", rr.status_code, len(js.get("candlesticks", [])), json.dumps(js)[:300])
