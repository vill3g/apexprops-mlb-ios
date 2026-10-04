import sqlite3
import os

db_path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\backend\data\trades.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT count(*), sum(case when pnl > 0 then pnl else 0 end), sum(case when pnl < 0 then pnl else 0 end), sum(pnl) FROM trades")
total, gross_win, gross_loss, net_pnl = c.fetchone()
print(f"Total trades: {total}")
print(f"Gross profit: {gross_win:.2f}")
print(f"Gross loss: {gross_loss:.2f}")
print(f"Net PnL: {net_pnl:.2f}")

c.execute("SELECT count(*) FROM trades WHERE pnl > 0")
wins = c.fetchone()[0]
c.execute("SELECT count(*) FROM trades WHERE pnl < 0")
losses = c.fetchone()[0]
c.execute("SELECT count(*) FROM trades WHERE pnl == 0")
flats = c.fetchone()[0]

print(f"Wins: {wins}, Losses: {losses}, Flats: {flats}")
print(f"Win rate: {wins/total*100:.2f}%")
print(f"Profit factor: {gross_win/abs(gross_loss):.2f}")

conn.close()
