import sqlite3
from backend.btc.kalshi_trader import KalshiTrader
from backend.auth.security import decrypt_kalshi_key
c = sqlite3.connect("backend/data/users.db")
c.row_factory = sqlite3.Row
for uid in (2, 205):
    u = dict(c.execute("select * from users where id=?", (uid,)).fetchone())
    pk = decrypt_kalshi_key(u["kalshi_priv_key_encrypted"])
    kt = KalshiTrader(key_id=u["kalshi_key_id"], private_key_pem=pk)
    print(uid, u["username"], "auth:", kt.is_authenticated())
    b = kt.get_balance()
    print("  balance:", {k: v for k, v in b.items() if "key" not in k.lower()})
