import sys
import os
sys.path.append(os.getcwd())
from backend.btc.kalshi_trader import KalshiTrader
kt = KalshiTrader()
res = kt.place_order(ticker="KXBTC15M", side="yes", count=1, limit_price_dollars=0.50, dry_run=False)
print(res)
