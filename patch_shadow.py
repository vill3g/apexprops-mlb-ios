import re

with open('backend/btc/shadow_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# I need to find the place where it reads rl_shadow_trades.json and check if ticker is already open.
# Wait, it reads trades AFTER generating the shadow_trade object!
old_logic = """        # Write to rl_shadow_trades.json
        trades = []
        if os.path.exists(SHADOW_TRADES_FILE):
            with open(SHADOW_TRADES_FILE, 'r') as f:
                try:
                    trades = json.load(f)
                except json.JSONDecodeError:
                    trades = []


        # Keep last 500
        if len(trades) > 500:
            trades = trades[-500:]

        with open(SHADOW_TRADES_FILE, 'w') as f:
            json.dump(trades, f, indent=2)"""

new_logic = """        # Write to rl_shadow_trades.json
        trades = []
        if os.path.exists(SHADOW_TRADES_FILE):
            with open(SHADOW_TRADES_FILE, 'r') as f:
                try:
                    trades = json.load(f)
                except json.JSONDecodeError:
                    trades = []

        # Check for duplicates
        for t in trades:
            if t.get("ticker") == ticker and t.get("status") == "OPEN":
                return # Already have an open trade for this interval

        trades.append(shadow_trade)

        # Keep last 500
        if len(trades) > 500:
            trades = trades[-500:]

        with open(SHADOW_TRADES_FILE, 'w') as f:
            json.dump(trades, f, indent=2)"""

code = code.replace(old_logic, new_logic)

with open('backend/btc/shadow_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed duplicate trades in shadow_executor")
