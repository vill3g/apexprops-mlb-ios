import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\data\users.db')
c = conn.cursor()
c.execute("SELECT * FROM users WHERE username='Vill3.G'")
row = c.fetchone()
cols = [desc[0] for desc in c.description]
settings = dict(zip(cols, row))

if 'password_hash' in settings: del settings['password_hash']
if 'kalshi_priv_key_encrypted' in settings: del settings['kalshi_priv_key_encrypted']

print(json.dumps(settings, indent=4))
