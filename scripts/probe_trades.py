import sqlite3, json
c = sqlite3.connect('backend/data/users.db')
cols = [r[1] for r in c.execute("pragma table_info(trades)")]
print(cols)
rows = c.execute("select * from trades where status!='OPEN' and raw_json is not null order by rowid desc limit 400").fetchall()
print(len(rows))
import collections
cnt = collections.Counter()
for r in rows:
    d = dict(zip(cols, r))
    try:
        j = json.loads(d['raw_json'])
    except Exception:
        continue
    ind = (j.get('market_snapshot') or {})
    if isinstance(ind, str):
        try: ind = json.loads(ind)
        except Exception: ind = {}
    ind = ind.get('indicators') or {}
    cnt[(d.get('asset') or d['ticker'][:6], 'ai_win_prob' in ind)] += 1
print(cnt.most_common(20))
d = dict(zip(cols, rows[0])); print({k: d[k] for k in cols if k != 'raw_json'}); print(str(d['raw_json'])[:600])
