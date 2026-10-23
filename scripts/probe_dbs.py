import sqlite3, os
D = r"C:\Users\Vill3\.gemini\antigravity\scratch\apexprops-mlb-ios\backend\data"
for f in ["soccer_matches.db", "nhl_games.db", "ufc_bouts.db", "international_baseball.db"]:
    p = os.path.join(D, f)
    print("==", f, os.path.getsize(p) if os.path.exists(p) else "missing")
    if not os.path.exists(p):
        continue
    c = sqlite3.connect(p)
    for (t,) in c.execute("select name from sqlite_master where type='table'"):
        n = c.execute(f"select count(*) from {t}").fetchone()[0]
        cols = [r[1] for r in c.execute(f"pragma table_info({t})")]
        print(" ", t, n, cols[:18])
