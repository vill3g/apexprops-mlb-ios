import requests
base = "https://api.elections.kalshi.com/trade-api/v2"
r = requests.get(f"{base}/markets", params={"series_ticker": "KXWTAMATCH", "status": "settled", "limit": 4}, timeout=20).json()
for m in r["markets"]:
    print({k: m.get(k) for k in ("ticker", "title", "yes_sub_title", "no_sub_title", "close_time", "expected_expiration_time", "open_time", "result")})
r = requests.get(f"{base}/markets", params={"series_ticker": "KXATPMATCH", "status": "settled", "limit": 4}, timeout=20).json()
for m in r["markets"]:
    print({k: m.get(k) for k in ("ticker", "title", "yes_sub_title", "no_sub_title", "close_time", "expected_expiration_time", "open_time", "result")})
