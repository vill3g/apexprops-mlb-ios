import json
from collections import defaultdict
from datetime import datetime

def main():
    with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\live_trades_dump.json', 'r') as f:
        trades = json.load(f)
    
    # Let's break into sessions based on a 4-hour gap
    sessions = []
    current_session = [trades[0]]
    for i in range(1, len(trades)):
        prev_time = trades[i-1]['created_at']
        curr_time = trades[i]['created_at']
        gap = prev_time - curr_time
        if gap > 4 * 3600:
            sessions.append(current_session)
            current_session = [trades[i]]
        else:
            current_session.append(trades[i])
    sessions.append(current_session)
    
    target_session = None
    for sess in sessions:
        if len(sess) >= 5:
            target_session = sess
            break
            
    print(f"Target session length: {len(target_session)}")
    # Print the raw_json of the first trade to understand structure
    first_trade_raw = json.loads(target_session[0].get('raw_json', '{}'))
    print(f"Raw JSON keys: {first_trade_raw.keys()}")
    print(f"Raw JSON sample: {json.dumps(first_trade_raw, indent=2)}")

if __name__ == "__main__":
    main()
