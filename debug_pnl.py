from backend.btc.auto_executor import auto_executor

trades = auto_executor.get_trades_history()
mode_trades = [t for t in trades if t.get('mode','').upper() == 'LIVE']

wins = sum(1 for t in mode_trades if 'WIN' in str(t.get('result','')).upper())
losses = sum(1 for t in mode_trades if 'LOSS' in str(t.get('result','')).upper())
total_pnl = sum(float(t.get('pnl', 0.0)) for t in mode_trades)

print("LIVE wins:   ", wins)
print("LIVE losses: ", losses)
print("Win rate:    ", round(wins / max(1, wins+losses) * 100, 1), "%")
print("Total PNL:   $", round(total_pnl, 2))

s = auto_executor.get_status()
print("--- get_status() returns ---")
print("win_rate:  ", repr(s.get('win_rate')))
print("total_pnl: ", repr(s.get('total_pnl')))

print()
print("CLOSED_FLAT trades (ghost reconcile victims):")
for t in mode_trades:
    if t.get('result') == 'CLOSED_FLAT':
        print("  id:", t.get('id')[:16], "| ticker:", t.get('ticker'))
