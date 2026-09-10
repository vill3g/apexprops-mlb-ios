import sys
import os
import requests
sys.path.append(os.getcwd())
from backend.btc.kalshi_trader import KalshiTrader

kt = KalshiTrader()

ticker = "KXBTC15M" # We can just use an invalid ticker, we want to see if the route is valid (400 vs 404)
count = 1
est_price = 0.50
side_clean = "yes"
v2_side = "bid" if side_clean == "yes" else "ask"
client_order_id = "test-1234-abcd"

v2_payload = {
    "ticker": ticker,
    "client_order_id": client_order_id,
    "side": v2_side,
    "count": 1,
    "price": int(est_price * 100),
    "time_in_force": "immediate_or_cancel",
    "action": "buy"
}

path = "/trade-api/v2/portfolio/orders"
headers = kt._sign_headers("POST", path)

import backend.btc.kalshi_trader
resp = requests.post(f"{backend.btc.kalshi_trader.BASE_URL}{path}", json=v2_payload, headers=headers)
print(f"URL: {backend.btc.kalshi_trader.BASE_URL}{path}")
print(resp.status_code)
print(resp.text)
