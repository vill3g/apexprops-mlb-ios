import sqlite3
conn = sqlite3.connect(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db')
c = conn.cursor()
c.execute("SELECT username, ai_enabled FROM users WHERE username='Vill3.G'")
print(c.fetchall())
