import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT * FROM users WHERE id = 205")
user = dict(c.fetchone())
print("Stop Loss Enabled:", user.get('stop_loss_enabled'))
print("Stop Loss %:", user.get('stop_loss_pct'))
print("Take Profit Enabled:", user.get('take_profit_enabled'))
print("Take Profit %:", user.get('take_profit_pct'))
print("Trading Style:", user.get('trading_style'))

