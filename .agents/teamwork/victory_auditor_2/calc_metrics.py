import sqlite3
import os

db_path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\backend\data\users.db"
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
print(f"Avg win: {gross_win/wins:.2f}")
print(f"Avg loss: {gross_loss/losses:.2f}")
print(f"Payoff ratio: {(gross_win/wins)/abs(gross_loss/losses):.2f}")

# Exit categories
print("\n--- Exit Reason Breakdown ---")
c.execute("""
    SELECT 
        CASE 
            WHEN exit_reason LIKE 'SETTLE%' THEN 'SETTLEMENT'
            WHEN exit_reason LIKE 'TAKE_PROFIT%' THEN 'TAKE_PROFIT'
            WHEN exit_reason LIKE 'STOP_LOSS%' OR exit_reason LIKE 'CONTRACT_STOP%' OR exit_reason LIKE 'TRAILING_STOP%' THEN 'STOP_LOSS'
            WHEN exit_reason LIKE 'MANUAL%' THEN 'MANUAL_CLOSE'
            ELSE 'OTHER'
        END as cat,
        count(*), 
        sum(case when pnl > 0 then 1 else 0 end),
        sum(case when pnl > 0 then pnl else 0 end),
        sum(case when pnl < 0 then pnl else 0 end),
        sum(pnl)
    FROM trades
    GROUP BY cat
""")
for cat, cnt, w, gw, gl, net in c.fetchall():
    wr = (w / cnt) * 100
    pf = (gw / abs(gl)) if gl else 999.0
    print(f"{cat}: count={cnt}, win_rate={wr:.2f}%, net_pnl={net:.2f}, PF={pf:.2f}")

conn.close()
