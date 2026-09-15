import json, time
with open('backend/data/trades_history.json', 'r') as f:
    trades = json.load(f)

# Fix: 01a0a397 was on 01:45 market (now expired) - let settlement handle it
# Fix: 01a0a399 is on 02:00 market which is OPEN right now on Kalshi
fixed = 0
for t in trades:
    tid = t.get('id','')
    if tid == '01a0a399-6fe8-7a74-a12a-7758dbbd10cc':
        print("02:00 trade status:", t.get('status'), t.get('result'))

    if t.get('result') == 'CLOSED_FLAT' and t.get('exit_reason') == 'KALSHI_POSITION_RECONCILED':
        print("Still ghost:", t.get('id'), t.get('ticker'), "close_epoch:", t.get('close_epoch'))
        
print("Done.")
