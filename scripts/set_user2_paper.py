import sqlite3
c = sqlite3.connect("backend/data/users.db")
c.execute("update users set trading_mode='PAPER' where id=2")
c.commit()
print(c.execute("select username, trading_mode, paper_balance from users where id=2").fetchone())
