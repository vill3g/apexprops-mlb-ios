import sys
import os
import requests
sys.path.append(os.getcwd())
from backend.btc.kalshi_trader import KalshiTrader

kt = KalshiTrader()

ticker = "KXBTC15M"
count = 1
est_price = 0.50
side_clean = "yes"
v2_side = "bid" if side_clean == "yes" else "ask"
client_order_id = "test-1234-abcd"

v2_payload = {
    "ticker": ticker,
    "client_order_id": client_order_id,
    "side": v2_side,
    "count": f"{int(count)}.00",
    "price": f"{est_price:.4f}",
    "time_in_force": "immediate_or_cancel",
    "self_trade_prevention_type": "taker_at_cross"
}

path = "/trade-api/v2/portfolio/orders"
headers = kt._sign_headers("POST", path)

from backend.btc.kalshi_client import BASE_URL
resp = requests.post(f"{BASE_URL}{path}", json=v2_payload, headers=headers)
print(resp.status_code)
print(resp.text)
