import json
import statistics

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users\205\trades_history.json'
with open(file_path, 'r') as f:
    trades = json.load(f)

closed_trades = [t for t in trades if t.get('status') == 'CLOSED']

win_entries = []
loss_entries = []

for t in closed_trades:
    pnl = float(t.get('pnl', 0.0))
    entry_price = float(t.get('entry_price', 0.0))
    if pnl > 0:
        win_entries.append(entry_price)
    elif pnl < 0:
        loss_entries.append(entry_price)

print(f"Avg Entry Price for Wins: {statistics.mean(win_entries):.2f}" if win_entries else "No wins")
print(f"Avg Entry Price for Losses: {statistics.mean(loss_entries):.2f}" if loss_entries else "No losses")

# Let's also look at exit reasons
exit_reasons = {}
for t in closed_trades:
    reason = t.get('exit_reason', 'UNKNOWN')
    exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
print("Exit Reasons:", exit_reasons)

