import json, re, statistics as stat
data=json.load(open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users\7\trades_history.json'))
sl_trades=[t for t in data if isinstance(t.get('exit_reason'), str) and t['exit_reason'].startswith('STOP_LOSS')]
pct_dips=[]
abs_dips=[]
entry_prices=[]
exit_prices=[]
for t in sl_trades:
    entry=t['entry_price']
    exit=t['exit_price']
    entry_prices.append(entry)
    exit_prices.append(exit)
    abs_dips.append(entry-exit)
    match=re.search(r'STOP_LOSS \(([-\d\.]+)%\)', t['exit_reason'])
    pct=float(match.group(1)) if match else (exit-entry)/entry*100
    pct_dips.append(pct)
print(f"Count: {len(sl_trades)}")
print(f"Avg Entry: {stat.mean(entry_prices):.4f}")
print(f"Avg Exit: {stat.mean(exit_prices):.4f}")
print(f"Avg Abs Dip (cents): {stat.mean(abs_dips):.4f}")
print(f"Avg Pct Dip: {stat.mean(pct_dips):.2f}%")
print(f"Median Pct Dip: {stat.median(pct_dips):.2f}%")
print(f"Max Pct Loss: {min(pct_dips):.2f}%")
print(f"Min Pct Loss: {max(pct_dips):.2f}%")
