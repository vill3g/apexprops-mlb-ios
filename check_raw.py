import sqlite3
import json

def fetch_raw_json():
    conn = sqlite3.connect('backend/data/trades.db')
    c = conn.cursor()
    c.execute("SELECT raw_json FROM trades WHERE exit_reason LIKE '%STOP_LOSS%' ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    if row and row[0]:
        print(json.dumps(json.loads(row[0]), indent=2))
    else:
        print("No raw_json found.")

if __name__ == '__main__':
    fetch_raw_json()
