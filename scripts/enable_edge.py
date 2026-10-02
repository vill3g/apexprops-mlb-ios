import sqlite3

conn = sqlite3.connect(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db')
c = conn.cursor()
c.execute("UPDATE users SET edge_gate_enabled=1, min_edge_cents=8.0")
conn.commit()
print("Edge gate enabled globally")
