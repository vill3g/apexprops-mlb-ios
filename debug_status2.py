from backend.btc.auto_executor import auto_executor
trades = auto_executor.get_trades_history()
mode_trades = [t for t in trades if t.get("mode", auto_executor.mode).upper() == auto_executor.mode]
open_trades = [t for t in mode_trades if t.get("status") == "OPEN"]
print(f"Open trades in DB: {len(open_trades)}")
for t in open_trades: print(t.get('id'), t.get('ticker'))
