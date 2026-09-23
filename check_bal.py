import sys
sys.path.append('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader')
from backend.btc.kalshi_trader import kalshi_trader

res = kalshi_trader.get_balance()
if res.get('success'):
    print(f"Live Balance: ${res.get('balance_dollars', 0.0):.2f}")
else:
    print('Failed to get balance:', res)
