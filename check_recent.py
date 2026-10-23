import sqlite3
import pandas as pd

conn = sqlite3.connect('backend/data/users.db')
df = pd.read_sql_query("SELECT * FROM trades WHERE user_id = 7 ORDER BY id DESC LIMIT 5", conn)
print(df)
conn.close()
