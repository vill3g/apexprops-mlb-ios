import sqlite3, os
base = r"C:\Users\Vill3\.gemini\antigravity\scratch\apexprops-mlb-ios\backend\data"
c = sqlite3.connect(os.path.join(base, "tennis_matches.db"))
for (name,) in c.execute("select name from sqlite_master where type='table'"):
    cols = [r[1] for r in c.execute(f"pragma table_info({name})")]
    n = c.execute(f"select count(*) from {name}").fetchone()[0]
    print(name, n, cols[:30])
for (name,) in c.execute("select name from sqlite_master where type='table'"):
    try:
        r = c.execute(f"select * from {name} order by rowid desc limit 1").fetchone()
        print("LAST", name, str(r)[:300])
    except Exception as e:
        print(name, e)
