import sqlite3
import json
import math

def audit_users_db():
    conn = sqlite3.connect('C:/Users/Vill3/Desktop/ShadowTraderAi/backend/data/users.db')
    c = conn.cursor()
    c.execute("SELECT id, user_id, symbol, ticker, side, count, entry_price, exit_price, pnl, status, exit_reason, mode, probability_percent, timestamp FROM trades")
    rows = c.fetchall()
    
    # Filter settled/closed trades
    trades = [r for r in rows if r[9] in ('SETTLED', 'CLOSED')]
    print(f"Total trades in users.db: {len(rows)}, Closed/Settled: {len(trades)}")
    
    # Global metrics
    wins = [t for t in trades if t[8] is not None and t[8] > 0]
    losses = [t for t in trades if t[8] is not None and t[8] < 0]
    flats = [t for t in trades if t[8] is not None and t[8] == 0]
    
    gross_profit = sum(t[8] for t in wins)
    gross_loss = sum(abs(t[8]) for t in losses)
    net_pnl = sum(t[8] for t in trades if t[8] is not None)
    wr = len(wins) / (len(wins) + len(losses)) * 100 if (wins or losses) else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    
    print(f"users.db Global: Wins={len(wins)}, Losses={len(losses)}, Flats={len(flats)}, WR={wr:.2f}%")
    print(f"Gross Profit=${gross_profit:.2f}, Gross Loss=${gross_loss:.2f}, Net PnL=${net_pnl:.2f}, PF={pf:.2f}")

    # By exit reason
    reasons = {}
    for t in trades:
        r = t[10] or "UNSPECIFIED"
        reasons.setdefault(r, []).append(t)
        
    print("\n--- By Exit Reason (users.db) ---")
    for r, r_trades in sorted(reasons.items(), key=lambda x: len(x[1]), reverse=True):
        r_wins = [t for t in r_trades if t[8] and t[8] > 0]
        r_losses = [t for t in r_trades if t[8] and t[8] < 0]
        r_gp = sum(t[8] for t in r_wins)
        r_gl = sum(abs(t[8]) for t in r_losses)
        r_net = sum(t[8] for t in r_trades if t[8] is not None)
        r_wr = len(r_wins) / (len(r_wins) + len(r_losses)) * 100 if (r_wins or r_losses) else 0
        r_pf = r_gp / r_gl if r_gl > 0 else (999.0 if r_gp > 0 else 0.0)
        print(f"{r:20s}: Count={len(r_trades):4d}, WR={r_wr:5.2f}%, Net=${r_net:8.2f}, GP=${r_gp:8.2f}, GL=${r_gl:8.2f}, PF={r_pf:5.2f}")

def audit_trades_db():
    conn = sqlite3.connect('C:/Users/Vill3/Desktop/ShadowTraderAi/backend/data/trades.db')
    c = conn.cursor()
    c.execute("SELECT id, symbol, side, count, entry_price, exit_price, pnl, status, exit_reason, mode, timestamp FROM trades")
    trades = c.fetchall()
    
    wins = [t for t in trades if t[6] is not None and t[6] > 0]
    losses = [t for t in trades if t[6] is not None and t[6] < 0]
    flats = [t for t in trades if t[6] is not None and t[6] == 0]
    
    gross_profit = sum(t[6] for t in wins)
    gross_loss = sum(abs(t[6]) for t in losses)
    net_pnl = sum(t[6] for t in trades if t[6] is not None)
    wr = len(wins) / (len(wins) + len(losses)) * 100 if (wins or losses) else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else 0
    
    print(f"\ntrades.db Global: Count={len(trades)}, Wins={len(wins)}, Losses={len(losses)}, Flats={len(flats)}, WR={wr:.2f}%")
    print(f"Gross Profit=${gross_profit:.2f}, Gross Loss=${gross_loss:.2f}, Net PnL=${net_pnl:.2f}, PF={pf:.2f}")

if __name__ == "__main__":
    audit_users_db()
    audit_trades_db()
