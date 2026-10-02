import json

last_date = ""
with open('backend/data/kalshi_btc15m_history.jsonl', 'r') as f:
    for line in f:
        data = json.loads(line)
        if 'ts' in data:
            last_date = data['ts']
        elif 'timestamp' in data:
            last_date = data['timestamp']
            
print("Last date:", last_date)
