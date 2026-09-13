"""Manual Kalshi probe with safety guard."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.btc.kalshi_trader import KalshiTrader

def main():
    if "--i-understand-this-is-live" not in sys.argv:
        print("[SAFETY ABORT] Refusing order. Pass: --i-understand-this-is-live")
        sys.exit(1)
    kt = KalshiTrader()
    res = kt.place_order(ticker="KXBTC15M", side="yes", count=1, limit_price_dollars=0.50, dry_run=False)
    print("Result:", res)

if __name__ == "__main__":
    main()