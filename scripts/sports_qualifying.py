import requests, sqlite3, time
ev = requests.get("http://127.0.0.1:8058/api/engine/sports/events?public=1", timeout=60).json().get("events", [])
c = sqlite3.connect("backend/data/users.db")
traded = {r[0]: r[1] for r in c.execute("select ticker, status from trades where user_id=7")}
now = time.time()
print("now", now)
rows = []
for e in ev:
    ap = e.get("ai_prediction") or {}
    if not ap:
        continue
    conf = float(e.get("confidence_pct") or ap.get("confidence_pct") or 0)
    edge = float(e.get("edge_pct") or ap.get("edge_pct") or 0)
    if conf >= 55 and edge >= 0 and not e.get("is_live"):
        tk = e.get("ticker")
        ya, na = e.get("yes_ask"), e.get("no_ask")
        rows.append((e.get("sport"), e.get("matchup") or e.get("title"), e.get("market_type"), round((e.get("start_epoch") or 0) - now) // 60, conf, edge, tk, traded.get(tk, "-"), ya, na, e.get("pick_side")))
print(len(rows), "qualifying for user 7 (conf>=55, edge>=0, not live)")
for r in rows:
    print(r)
