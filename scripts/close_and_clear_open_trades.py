import time
import json
from zoneinfo import ZoneInfo
from datetime import datetime
from backend.database.trade_store import TradeStore
from backend.database.models import get_all_active_users, credit_user_paper_balance, get_db_connection

now_et = datetime.now(ZoneInfo("America/New_York"))
now_ts = now_et.timestamp()
time_str = now_et.strftime("%Y-%m-%d %I:%M:%S %p ET")

users = get_all_active_users()
print(f"Checking {len(users)} active users for open trades to close and clear...")

total_cleared = 0
for u in users:
    uid = u["id"]
    username = u.get("username")
    open_trades = TradeStore.get_open_trades(uid)
    if not open_trades:
        continue
    
    print(f"\nUser {uid} ({username}): Found {len(open_trades)} open trades. Clearing...")
    for t in open_trades:
        tid = t.get("id")
        mode = (t.get("mode") or "PAPER").upper()
        ticker = t.get("ticker")
        cost = float(t.get("cost") or t.get("trade_size_dollars") or 0.0)
        if cost == 0.0:
            # Check count * entry_price
            count = int(t.get("count") or 1)
            entry_p = float(t.get("entry_price") or 0.0)
            cost = round(count * entry_p, 2)
        
        # If PAPER mode, refund the full cost back to paper balance
        if mode == "PAPER" and cost > 0:
            credit_user_paper_balance(uid, cost)
            print(f"  Refunded ${cost:.2f} paper balance to User {uid}")
        
        # Update trade to CLOSED
        updates = {
            "status": "CLOSED",
            "exit_reason": "MANUAL_CLEAR",
            "exit_price": float(t.get("entry_price") or 0.0),
            "pnl": 0.0,
            "settled_at": time_str
        }
        res = TradeStore.update_trade(tid, updates, only_if_open=False)
        print(f"  Closed trade {tid} ({ticker}) -> updated={res}")
        total_cleared += 1

print(f"\nSuccessfully cleared and refunded {total_cleared} open trades.")

# Verify no open trades remain
for u in users:
    rem = TradeStore.get_open_trades(u["id"])
    print(f"User {u['id']} remaining open trades: {len(rem)}")
