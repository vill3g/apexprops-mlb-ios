from backend.database.trade_store import TradeStore
trades = TradeStore.get_recent_trades(2, limit=10)
for t in trades[:5]:
    print(t.get('id'), t.get('ticker'), 'status:', t.get('status'), 'pnl:', t.get('pnl'), 'live_pnl:', t.get('live_pnl'))
