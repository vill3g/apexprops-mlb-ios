import sqlite3
import os
db_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT id FROM users WHERE username='Vill3.G'")
uid = c.fetchone()[0]

app_db = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\app.db"
if not os.path.exists(app_db):
    app_db = db_path # maybe they are the same DB?

conn2 = sqlite3.connect(app_db)
c2 = conn2.cursor()
try:
    c2.execute("SELECT status, ticker, side FROM trades WHERE user_id = ? ORDER BY id DESC LIMIT 5", (uid,))
    print(c2.fetchall())
except Exception as e:
    print(e)
