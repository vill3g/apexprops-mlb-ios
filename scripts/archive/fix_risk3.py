import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace today_realized_pnl calculation
old_calc = """        today_trade_count = len(today_trades)
        today_realized_pnl = sum(float(t.get("pnl", 0.0)) for t in today_trades)"""

new_calc = """        today_trade_count = len(today_trades)
        today_realized_pnl, today_open_collateral, today_effective_risk = self._compute_effective_daily_risk(today_trades)"""

content = content.replace(old_calc, new_calc)

# Replace pause_reason block
old_pause = """        is_risk_paused = False
        pause_reason = ""
        if self.enabled:
            if today_trade_count >= self.max_daily_trades:
                is_risk_paused = True
                pause_reason = f"Daily trade limit reached ({today_trade_count}/{self.max_daily_trades})"
            elif today_realized_pnl <= -abs(self.max_daily_risk):
                is_risk_paused = True
                pause_reason = f"Daily loss limit reached (-${abs(today_realized_pnl):.2f}/-${abs(self.max_daily_risk):.2f})\""""

new_pause = """        is_risk_paused = False
        pause_reason = ""
        if self.enabled:
            if today_trade_count >= self.max_daily_trades:
                is_risk_paused = True
                pause_reason = f"Daily trade limit reached ({today_trade_count}/{self.max_daily_trades})"
            elif today_effective_risk <= -abs(self.max_daily_risk):
                is_risk_paused = True
                pause_reason = (
                    f"Daily loss limit reached (Settled: ${today_realized_pnl:.2f}, "
                    f"Open Collateral: ${today_open_collateral:.2f}, Effective: ${today_effective_risk:.2f} "
                    f"<= -${self.max_daily_risk:.2f})"
                )\""""

content = content.replace(old_pause, new_pause)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
