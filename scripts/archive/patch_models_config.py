with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    c = f.read()

old_init = """        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            kalshi_key_id TEXT,
            kalshi_priv_key_encrypted TEXT,
            is_active BOOLEAN DEFAULT 1,
            role TEXT DEFAULT 'user',
            trading_mode TEXT DEFAULT 'PAPER',
            paper_balance REAL DEFAULT 500.0,
            ai_enabled BOOLEAN DEFAULT 1
        )"""

new_init = """        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            kalshi_key_id TEXT,
            kalshi_priv_key_encrypted TEXT,
            is_active BOOLEAN DEFAULT 1,
            role TEXT DEFAULT 'user',
            trading_mode TEXT DEFAULT 'PAPER',
            paper_balance REAL DEFAULT 500.0,
            ai_enabled BOOLEAN DEFAULT 1,
            trade_size_pct REAL DEFAULT 20.0,
            stop_loss_pct REAL DEFAULT 10.0,
            one_click_trade BOOLEAN DEFAULT 0
        )"""

c = c.replace(old_init, new_init)

# We also need a function to update user config
update_fn = """
def update_user_config(user_id: int, size: float, sl: float, one_click: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET trade_size_pct = ?, stop_loss_pct = ?, one_click_trade = ?
        WHERE id = ?
    ''', (size, sl, 1 if one_click else 0, user_id))
    conn.commit()
    conn.close()
"""
c += update_fn

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(c)
