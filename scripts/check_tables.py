import sqlite3
conn = sqlite3.connect(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", c.fetchall())

c.execute("SELECT * FROM trades LIMIT 5")
print(c.fetchall())
