import sqlite3
conn = sqlite3.connect('backend/data/users.db')
conn.execute("UPDATE users SET ai_enabled=1, trading_mode='PAPER', signal_source='RL_SCALPER', paper_balance=5000.0")
conn.commit()
print("Updated successfully")
