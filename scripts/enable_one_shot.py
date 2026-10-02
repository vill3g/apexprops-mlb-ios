import sqlite3
import json
conn = sqlite3.connect(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db')
c = conn.cursor()
c.execute("UPDATE users SET one_click_trade=1, one_shot_ai=1 WHERE username='Vill3.G'")
conn.commit()
print("Enabled 1-click trading and one-shot AI for Vill3.G")
