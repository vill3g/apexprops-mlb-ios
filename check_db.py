import json
import sqlite3

def check():
    conn = sqlite3.connect('backend/data/trades.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print(c.fetchall())
    c.execute("PRAGMA table_info(trades);")
    print(c.fetchall())
    
if __name__ == '__main__':
    check()
