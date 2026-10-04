import os
import sqlite3
import json
import glob

PROJECT_ROOT = r"C:\Users\Vill3\Desktop\ShadowTraderAi"

print("=== INSPECTING SQLITE DATABASES ===")
db_patterns = [
    os.path.join(PROJECT_ROOT, "backend", "data", "*.db"),
    os.path.join(PROJECT_ROOT, "backend", "data", "*.sqlite*"),
    os.path.join(PROJECT_ROOT, "backend", "database", "*.db"),
    os.path.join(PROJECT_ROOT, "backend", "*.db"),
    os.path.join(PROJECT_ROOT, "data", "*.db"),
    os.path.join(PROJECT_ROOT, "*.db")
]

all_dbs = []
for p in db_patterns:
    all_dbs.extend(glob.glob(p))

all_dbs = sorted(list(set(all_dbs)))

for db_path in all_dbs:
    rel_path = os.path.relpath(db_path, PROJECT_ROOT)
    size = os.path.getsize(db_path)
    print(f"\n--- Database: {rel_path} ({size} bytes) ---")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"Tables: {tables}")
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{t}`;")
            cnt = cursor.fetchone()[0]
            cursor.execute(f"PRAGMA table_info(`{t}`);")
            cols = [c[1] for c in cursor.fetchall()]
            print(f"  Table: {t} | Rows: {cnt} | Columns: {cols}")
            if cnt > 0 and any(keyword in t.lower() for keyword in ["trade", "order", "position", "fill", "history", "kalshi"]):
                cursor.execute(f"SELECT * FROM `{t}` LIMIT 2;")
                samples = cursor.fetchall()
                print(f"    Sample: {samples}")
        conn.close()
    except Exception as e:
        print(f"  Error reading {rel_path}: {e}")

print("\n=== INSPECTING JSON TRADE FILES ===")
json_files = glob.glob(os.path.join(PROJECT_ROOT, "backend", "**", "*trade*.json"), recursive=True)
json_files.extend(glob.glob(os.path.join(PROJECT_ROOT, "backend", "**", "*backtest*.json"), recursive=True))

for jf in sorted(list(set(json_files))):
    rel_path = os.path.relpath(jf, PROJECT_ROOT)
    size = os.path.getsize(jf)
    print(f"\n--- JSON: {rel_path} ({size} bytes) ---")
    try:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"  Type: List, Count: {len(data)}")
                if len(data) > 0:
                    sample = data[0]
                    if isinstance(sample, dict):
                        print(f"  Keys: {list(sample.keys())}")
                        print(f"  Sample record: {json.dumps(sample, indent=2)[:300]}...")
                    else:
                        print(f"  Sample: {sample}")
            elif isinstance(data, dict):
                print(f"  Type: Dict, Keys: {list(data.keys())[:10]}")
                for k in list(data.keys())[:3]:
                    val = data[k]
                    if isinstance(val, list):
                        print(f"    Key '{k}' has {len(val)} items")
                        if len(val) > 0 and isinstance(val[0], dict):
                            print(f"      Keys of first item: {list(val[0].keys())}")
                    elif isinstance(val, dict):
                        print(f"    Key '{k}' is dict with keys {list(val.keys())[:5]}")
                    else:
                        print(f"    Key '{k}': {str(val)[:100]}")
    except Exception as e:
        print(f"  Error reading {rel_path}: {e}")
