import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_calc = """        today_net_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades if t.get("status") in ["SETTLED", "CLOSED"])
        open_collateral = sum(
            float(t.get("entry_price", 0.50)) * int(t.get("count", 1))
            for t in today_trades
            if t.get("status") in ["OPEN", "PENDING"]
        )
        effective_risk = today_net_pnl - open_collateral
        if effective_risk <= -abs(self.max_daily_risk):
            return (
                f"Max daily risk limit reached (Settled PnL: ${today_net_pnl:.2f}, "
                f"Open Collateral: ${open_collateral:.2f}, Effective: ${effective_risk:.2f} <= -${self.max_daily_risk:.2f})"
            )
        return None"""

new_calc = """        today_net_pnl, open_collateral, effective_risk = self._compute_effective_daily_risk(today_trades)
        if effective_risk <= -abs(self.max_daily_risk):
            return (
                f"Max daily risk limit reached (Settled PnL: ${today_net_pnl:.2f}, "
                f"Open Collateral: ${open_collateral:.2f}, Effective: ${effective_risk:.2f} <= -${self.max_daily_risk:.2f})"
            )
        return None"""

content = content.replace(old_calc, new_calc)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
