import sqlite3
import json

def analyze():
    conn = sqlite3.connect('backend/data/trades.db')
    c = conn.cursor()
    c.execute("SELECT id, entry_price, exit_price, exit_reason, ticker FROM trades WHERE exit_reason LIKE '%STOP_LOSS%' ORDER BY id DESC")
    trades = c.fetchall()
    
    valid_trades = [t for t in trades if t[1] is not None and t[2] is not None]
    last_100 = valid_trades[:100]
    
    print(f"Found {len(last_100)} valid stop loss trades (out of {len(valid_trades)} total).")
    
    if len(last_100) > 0:
        avg_entry = sum(t[1] for t in last_100) / len(last_100)
        avg_exit = sum(t[2] for t in last_100) / len(last_100)
        avg_dip = sum((t[1]-t[2]) for t in last_100) / len(last_100)
        avg_dip_percent = sum((t[1]-t[2])/t[1] for t in last_100) / len(last_100)
        
        print(f"Avg Entry: {avg_entry:.4f}")
        print(f"Avg Exit: {avg_exit:.4f}")
        print(f"Avg Dip: {avg_dip:.4f} (cents)")
        print(f"Avg Dip Percent: {avg_dip_percent * 100:.2f}%")

if __name__ == '__main__':
    analyze()
