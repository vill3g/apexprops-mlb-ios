import sqlite3
from backend.btc.kalshi_trader import get_authenticated_trader_for_user

conn = sqlite3.connect("backend/data/users.db")
c = conn.cursor()
c.execute("SELECT * FROM users WHERE id = 7")
col_names = [d[0] for d in c.description]
user = dict(zip(col_names, c.fetchone()))
kt = get_authenticated_trader_for_user(user)

settlements = kt.session.get("https://external-api.kalshi.com/trade-api/v2/portfolio/settlements", headers=kt._sign_headers("GET", "/trade-api/v2/portfolio/settlements")).json().get("settlements", [])
settled_map = {s.get("ticker"): s for s in settlements}

c.execute("SELECT id, ticker, status, count, entry_price FROM trades WHERE user_id = 7 AND status = 'OPEN'")
for row in c.fetchall():
    t_id, ticker, status, count, entry_price = row
    if ticker in settled_map:
        s = settled_map[ticker]
        print("MATCH SETTLED:", ticker, "Result:", s.get("market_result"), "Revenue:", s.get("revenue"), "Settled Time:", s.get("settled_time"))
    else:
        print("Open on Kalshi:", ticker)
