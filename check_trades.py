import sys
sys.path.append('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader')
from backend.database.trade_store import TradeStore
trades = TradeStore.get_open_trades(7)
for t in trades:
    print({k: v for k, v in t.items() if k in ['id', 'ticker', 'status', 'mode', 'count']})
