import sqlite3
import json

def main():
    db_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\trades.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM trades WHERE mode = 'LIVE' ORDER BY created_at DESC;")
    trades = [dict(row) for row in cursor.fetchall()]
    
    with open(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\live_trades_dump.json', 'w') as f:
        json.dump(trades, f, indent=2)

if __name__ == "__main__":
    main()
