import sqlite3
import json

def analyze():
    conn = sqlite3.connect('backend/data/trades.db')
    c = conn.cursor()
    c.execute("SELECT raw_json FROM trades WHERE exit_reason LIKE '%TAKE_PROFIT%' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row and row[0]:
        data = json.loads(row[0])
        print("min_seen_bid in data:", 'min_seen_bid' in data)
        print("max_seen_bid in data:", 'max_seen_bid' in data)
        
        # Let's get the average max drawdown of the last 100 WINNING trades!
        c.execute("SELECT entry_price, raw_json FROM trades WHERE exit_reason LIKE '%TAKE_PROFIT%' OR pnl > 0 ORDER BY id DESC LIMIT 100")
        winners = c.fetchall()
        
        dips = []
        for w in winners:
            entry = w[0]
            j = json.loads(w[1])
            min_bid = j.get('min_seen_bid', entry)  # fallback to entry if missing
            if min_bid is not None and entry is not None and entry > 0:
                dip = entry - min_bid
                if dip > 0:
                    dips.append(dip)
                    
        if dips:
            avg_dip = sum(dips) / len(dips)
            print(f"Analyzed {len(dips)} winning trades with dips.")
            print(f"Average dip of WINNING trades: {avg_dip:.4f} cents")
        else:
            print("No valid dips found for winning trades.")

if __name__ == '__main__':
    analyze()
