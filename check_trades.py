import sqlite3

conn = sqlite3.connect('backend/data/users.db')
cur = conn.cursor()
cur.execute("SELECT id, ticker, status FROM trades WHERE user_id = 7 AND status = 'OPEN'")
print(cur.fetchall())
conn.close()
