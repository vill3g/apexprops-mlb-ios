import sqlite3

conn = sqlite3.connect('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\backend\\data\\users.db')
c = conn.cursor()
c.execute("PRAGMA table_info(users)")
cols = [row[1] for row in c.fetchall()]
print('stop_loss_enabled' in cols)
