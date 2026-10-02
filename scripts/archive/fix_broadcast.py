import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    c = f.read()

# Remove the gatekeeper condition that blocks broadcast when master is in PAPER mode
old_gate = """    def _broadcast_trade_to_users(self, ticker: str, side: str, limit_price_dollars: float, pred_info: dict = None):
        if self.mode != "LIVE":
            return"""

new_gate = """    def _broadcast_trade_to_users(self, ticker: str, side: str, limit_price_dollars: float, pred_info: dict = None):"""

if old_gate in c:
    c = c.replace(old_gate, new_gate)

# Fix hardcoded 20% size and use trade_size_pct for both LIVE and PAPER in the broadcast
c = re.sub(
    r'risk_amount = avail_bal \* 0\.20',
    r'risk_amount = avail_bal * (float(user.get("trade_size_pct", 20.0)) / 100.0)',
    c
)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(c)
