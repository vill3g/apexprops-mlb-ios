import json
import statistics

file_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users\205\trades_history.json'
with open(file_path, 'r') as f:
    trades = json.load(f)

closed_trades = [t for t in trades if t.get('status') == 'CLOSED']

wins = []
losses = []

pnl_list = []
fees_list = []

for t in closed_trades:
    pnl = float(t.get('pnl', 0.0))
    pnl_list.append(pnl)
    # The JSON might have fee information, let's just look at PNL for now
    if pnl > 0:
        wins.append(pnl)
    elif pnl < 0:
        losses.append(pnl)

win_rate = len(wins) / len(closed_trades) if closed_trades else 0
avg_win = sum(wins) / len(wins) if wins else 0
avg_loss = sum(losses) / len(losses) if losses else 0
total_pnl = sum(pnl_list)

print(f"Total Closed Trades: {len(closed_trades)}")
print(f"Wins: {len(wins)} ({win_rate*100:.1f}%)")
print(f"Losses: {len(losses)} ({(1-win_rate)*100:.1f}%)")
print(f"Average Win: ")
print(f"Average Loss: ")
print(f"Total Net PnL: ")

if avg_win > 0 and avg_loss < 0:
    print(f"Risk/Reward Ratio: 1 : {avg_win / abs(avg_loss):.2f}")

