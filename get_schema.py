import sqlite3
import json
import sys

def main():
    db_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\trades.db'
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table';")
        schema = [dict(row) for row in cursor.fetchall()]
        print(json.dumps(schema, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
