import re

with open('backend/database/models.py', 'r', encoding='utf-8') as f:
    code = f.read()

trades_table = """
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                ticker TEXT,
                side TEXT,
                entry_price REAL,
                exit_price REAL,
                count INTEGER DEFAULT 0,
                pnl REAL DEFAULT 0.0,
                status TEXT DEFAULT 'OPEN',
                mode TEXT DEFAULT 'PAPER',
                reason TEXT,
                exit_reason TEXT,
                trading_style TEXT,
                signal_source TEXT,
                timestamp REAL,
                settled_at REAL,
                ml_reasoning TEXT,
                catalysts TEXT,
                raw_json TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_user_status ON trades(user_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_user_mode ON trades(user_id, mode)')
"""

# Insert right after cursor = conn.cursor() in init_db
code = code.replace('cursor = conn.cursor()', 'cursor = conn.cursor()' + trades_table, 1)

with open('backend/database/models.py', 'w', encoding='utf-8') as f:
    f.write(code)
