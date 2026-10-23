import re
from datetime import datetime
from zoneinfo import ZoneInfo
from backend.database.trade_store import TradeStore
from backend.database.models import get_all_active_users, credit_user_paper_balance

today = datetime.now(ZoneInfo("America/New_York")).date()
time_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M:%S %p ET")
MON = {m: i for i, m in enumerate(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"], 1)}
n = 0
for u in get_all_active_users():
    for t in TradeStore.get_open_trades(u["id"]):
        tk = t.get("ticker") or ""
        m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", tk)
        if not (tk.startswith("KX") and m and m.group(2) in MON):
            continue
        d = datetime(2000 + int(m.group(1)), MON[m.group(2)], int(m.group(3))).date()
        if d <= today:
            continue
        mode = (t.get("mode") or "PAPER").upper()
        cost = float(t.get("cost") or t.get("trade_size_dollars") or 0.0)
        if mode == "PAPER" and cost > 0:
            credit_user_paper_balance(u["id"], cost)
        TradeStore.update_trade(t["id"], {"status": "CLOSED", "exit_reason": "MANUAL_CLEAR", "exit_price": float(t.get("entry_price") or 0), "pnl": 0.0, "settled_at": time_str}, only_if_open=False)
        print(f"Cleared user {u['id']} {tk} refund ${cost:.2f} ({mode})")
        n += 1
print("Cleared", n, "future-dated trades")
