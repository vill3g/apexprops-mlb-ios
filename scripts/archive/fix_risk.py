import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

helper = """    def _compute_effective_daily_risk(self, today_trades: list) -> tuple:
        \"\"\"Returns (today_net_pnl, open_collateral, effective_risk) for a list of
        today's trades already filtered to the current mode. Shared by
        check_risk_budget() and get_status() so pause/block logic never diverges.
        \"\"\"
        today_net_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades if t.get("status") in ["SETTLED", "CLOSED"])
        open_collateral = sum(
            float(t.get("entry_price", 0.50)) * int(t.get("count", 1))
            for t in today_trades
            if t.get("status") in ["OPEN", "PENDING"]
        )
        effective_risk = today_net_pnl - open_collateral
        return today_net_pnl, open_collateral, effective_risk

    def check_risk_budget"""

content = content.replace("    def check_risk_budget", helper)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
