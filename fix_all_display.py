import json, time
from datetime import datetime
from zoneinfo import ZoneInfo

with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

fixed = 0
for t in trades:
    if t.get('result') == 'CLOSED_FLAT' and t.get('exit_reason') == 'KALSHI_POSITION_RECONCILED':
        close_epoch = float(t.get('close_epoch') or 0)
        # If market has expired, let settlement pick it up, not the ghost reconciler
        if close_epoch > 0 and time.time() > close_epoch:
            # Mark for re-settlement - leave as OPEN so check_settlements can assign proper result
            t['status'] = 'OPEN'
            t['result'] = 'PENDING'
            del t['exit_reason']
            if 'closed_at' in t: del t['closed_at']
            fixed += 1
        else:
            # Market still active but was wrongly closed - restore
            t['status'] = 'OPEN'
            t['result'] = 'PENDING'
            del t['exit_reason']
            if 'closed_at' in t: del t['closed_at']
            fixed += 1

print(f"Restored {fixed} ghost-closed trades back to OPEN/PENDING for re-settlement")

with open('backend/data/trades_history.json', 'w') as f:
    json.dump(trades, f, indent=2)

# Now run settlement
from backend.btc.auto_executor import auto_executor
auto_executor._last_settlement_check_ts = 0  # reset the throttle
auto_executor.check_settlements()

# Report final stats
trades2 = auto_executor.get_trades_history()
live = [t for t in trades2 if t.get('mode','').upper() == 'LIVE']
wins = sum(1 for t in live if 'WIN' in str(t.get('result','')).upper())
losses = sum(1 for t in live if 'LOSS' in str(t.get('result','')).upper())
closed_flat = sum(1 for t in live if t.get('result') == 'CLOSED_FLAT')
total_pnl = sum(float(t.get('pnl', 0.0)) for t in live)

print(f"LIVE Wins:        {wins}")
print(f"LIVE Losses:      {losses}")
print(f"Win Rate:         {round(wins / max(1, wins+losses) * 100, 1)}%")
print("Total PNL:        $" + str(round(total_pnl, 2)))
print(f"Still CLOSED_FLAT: {closed_flat}")
