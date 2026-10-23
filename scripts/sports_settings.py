import sqlite3
c = sqlite3.connect("backend/data/users.db"); c.row_factory = sqlite3.Row
cols = [r[1] for r in c.execute("pragma table_info(users)")]
keys = [k for k in cols if k.startswith("sports_") or k in ("min_sports_confidence", "min_sports_edge", "allow_simulation_trades", "include_live", "sports_include_live")]
for uid in (2, 7, 205):
    u = dict(c.execute("select * from users where id=?", (uid,)).fetchone())
    print(uid, u["username"], {k: u[k] for k in keys})
