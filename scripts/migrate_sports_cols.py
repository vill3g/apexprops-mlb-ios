import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "data", "users.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

cols = [
    ('sports_active_leagues', "TEXT DEFAULT 'NFL,MLB,NPB/KBO,SOC,UFC,TEN,NHL'"),
    ('sports_min_price', "REAL DEFAULT 0.20"),
    ('sports_max_price', "REAL DEFAULT 0.80"),
    ('sports_max_daily_trades', "INTEGER DEFAULT 10"),
    ('sports_max_daily_risk', "REAL DEFAULT 100.0"),
    ('sports_tp_enabled', "BOOLEAN DEFAULT 0"),
    ('sports_tp_pct', "REAL DEFAULT 35.0"),
    ('sports_use_kelly', "BOOLEAN DEFAULT 0"),
    ('sports_market_types', "TEXT DEFAULT 'GAME,SPREAD,TOTAL'")
]

for name, typ in cols:
    try:
        c.execute(f"ALTER TABLE users ADD COLUMN {name} {typ}")
        print(f"Added {name}")
    except Exception as e:
        print(f"{name}: {e}")

conn.commit()
conn.close()
print("Migration completed.")
