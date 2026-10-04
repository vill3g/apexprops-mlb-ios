import os
import sqlite3
import glob

PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

print("=== SQLITE DATABASES AND TABLES ===")
paths = [
    os.path.join(PROJECT_ROOT, "backend", "data", "*.db"),
    os.path.join(PROJECT_ROOT, "backend", "data", "*.sqlite*"),
    os.path.join(PROJECT_ROOT, "backend", "database", "*.db"),
    os.path.join(PROJECT_ROOT, "backend", "*.db"),
    os.path.join(PROJECT_ROOT, "data", "*.db"),
    os.path.join(PROJECT_ROOT, "*.db")
]

all_dbs = []
for p in paths:
    all_dbs.extend(glob.glob(p))

for db in sorted(set(all_dbs)):
    rel = os.path.relpath(db, PROJECT_ROOT)
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cur.fetchall()]
        print(f"\n{rel}:")
        for t in tables:
            cur.execute(f"SELECT COUNT(*) FROM `{t}`;")
            cnt = cur.fetchone()[0]
            print(f"  table: {t} -> {cnt} rows")
        conn.close()
    except Exception as e:
        print(f"\n{rel}: Error {e}")
