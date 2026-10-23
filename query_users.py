import sqlite3
conn = sqlite3.connect('backend/data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT id, username, trading_universe, ai_enabled FROM users WHERE trading_universe IN ('SPORTS', 'BOTH', 'ALL') AND ai_enabled = 1")
rows = c.fetchall()
for r in rows:
    print(dict(r))
