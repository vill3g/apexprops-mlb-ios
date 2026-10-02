import json
import statistics

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users\205\trades_history.json'
with open(file_path, 'r') as f:
    trades = json.load(f)

closed_trades = [t for t in trades if t.get('status') == 'CLOSED']

print("\nLoss trades sample:")
for t in [x for x in closed_trades if float(x.get('pnl', 0)) < 0][:5]:
    print(f"  Entry: ${t.get('entry_price')}, Exit: ${t.get('exit_price')}, Count: {t.get('count')}, PNL: ${t.get('pnl')}")

print("\nWin trades sample:")
for t in [x for x in closed_trades if float(x.get('pnl', 0)) > 0][:5]:
    print(f"  Entry: ${t.get('entry_price')}, Exit: ${t.get('exit_price')}, Count: {t.get('count')}, PNL: ${t.get('pnl')}")

