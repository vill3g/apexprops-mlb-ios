import sqlite3

db_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Update User 205's risk settings
c.execute('''
    UPDATE users 
    SET stop_loss_pct = 25.0, 
        take_profit_enabled = 0, 
        take_profit_pct = 90.0 
    WHERE id = 205
''')

conn.commit()

# Verify the changes
c.execute("SELECT stop_loss_pct, take_profit_enabled, take_profit_pct FROM users WHERE id = 205")
row = c.fetchone()
print(f"Updated User 205 Settings -> Stop Loss %: {row[0]}, Take Profit Enabled: {row[1]}, Take Profit %: {row[2]}")

conn.close()
