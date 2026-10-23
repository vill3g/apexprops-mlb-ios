import sqlite3
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo('America/New_York'))
cutoff_24h = now - timedelta(hours=24)

conn = sqlite3.connect('backend/data/users.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute('SELECT * FROM trades WHERE user_id=2')
all_rows = [dict(r) for r in c.fetchall()]

trades_24h = []
for r in all_rows:
    ts_str = str(r.get('timestamp') or '')
    dt = None
    for fmt in ['%Y-%m-%d %I:%M:%S %p ET', '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S']:
        try:
            dt = datetime.strptime(ts_str, fmt)
            break
        except:
            pass
    if dt:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo('America/New_York'))
        if dt >= cutoff_24h:
            trades_24h.append((dt, r))

trades_24h.sort(key=lambda x: x[0], reverse=True)

print(f"AUDIT REPORT FOR USER 2 (IppoLang60)")
print(f"Window: Last 24 Hours ({cutoff_24h.strftime('%b %d, %I:%M %p ET')} -> {now.strftime('%b %d, %I:%M %p ET')})")
print("=" * 110)

total_trades = len(trades_24h)
wins = [t for t in trades_24h if (t[1]['pnl'] or 0) > 0]
losses = [t for t in trades_24h if (t[1]['pnl'] or 0) < 0]
breakeven = [t for t in trades_24h if (t[1]['pnl'] or 0) == 0]

net_pnl = sum(t[1]['pnl'] or 0 for t in trades_24h)
total_win_pnl = sum(t[1]['pnl'] or 0 for t in wins)
total_loss_pnl = sum(t[1]['pnl'] or 0 for t in losses)

financial_trades = [t for t in trades_24h if t[1]['trading_style'] != 'SPORTS_AI']
sports_trades = [t for t in trades_24h if t[1]['trading_style'] == 'SPORTS_AI']

print(f"Total Executed Trades : {total_trades}")
print(f"Wins / Losses / Push  : {len(wins)} Wins | {len(losses)} Losses | {len(breakeven)} Breakeven")
print(f"Win Rate              : {(len(wins)/total_trades)*100:.1f}%")
print(f"Net Realized PnL      : ${net_pnl:.2f} (Gross Gains: +${total_win_pnl:.2f} | Gross Losses: ${total_loss_pnl:.2f})")
print(f"Profit Factor         : {abs(total_win_pnl/total_loss_pnl):.2f}" if total_loss_pnl != 0 else "N/A")
print("-" * 110)

print(f"\n--- BREAKDOWN BY TRADING UNIVERSE ---")
fin_pnl = sum(t[1]['pnl'] or 0 for t in financial_trades)
fin_wins = len([t for t in financial_trades if (t[1]['pnl'] or 0) > 0])
print(f"Financial Universe (Crypto BTC/ETH): {len(financial_trades)} Trades | {fin_wins} Wins / {len(financial_trades)-fin_wins} Losses ({(fin_wins/len(financial_trades))*100:.1f}% Win Rate) | Net PnL: ${fin_pnl:.2f}")

sports_pnl = sum(t[1]['pnl'] or 0 for t in sports_trades)
sports_wins = len([t for t in sports_trades if (t[1]['pnl'] or 0) > 0])
print(f"Sports Universe (NFL/Tennis WTA)    : {len(sports_trades)} Trades | {sports_wins} Wins / {len(sports_trades)-sports_wins} Losses ({(sports_wins/len(sports_trades))*100:.1f}% Win Rate) | Net PnL: ${sports_pnl:.2f}")

print("\n" + "=" * 110)
print(f"{'TIME (ET)':<20} | {'TICKER':<30} | {'SIDE':<4} | {'STYLE':<15} | {'ENTRY':<6} | {'EXIT':<6} | {'CNT':<4} | {'PNL':<8} | {'EXIT REASON'}")
print("-" * 110)
for dt, r in trades_24h:
    time_str = dt.strftime('%b %d %I:%M:%S %p')
    ticker = r['ticker']
    side = r['side']
    style = r['trading_style']
    entry = f"${r['entry_price']:.2f}" if r['entry_price'] is not None else "-"
    exit_p = f"${r['exit_price']:.2f}" if r['exit_price'] is not None else "-"
    cnt = str(r['count'])
    pnl_str = f"${r['pnl']:+.2f}"
    exit_r = r['exit_reason'] or r['status']
    print(f"{time_str:<20} | {ticker:<30} | {side:<4} | {style:<15} | {entry:<6} | {exit_p:<6} | {cnt:<4} | {pnl_str:<8} | {exit_r}")
