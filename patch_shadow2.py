import re

with open('backend/btc/shadow_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

# I will find trades.append(shadow_trade) and replace it with the duplicate check
new_logic = """
        # Check for duplicates
        is_dup = False
        for t in trades:
            if t.get("ticker") == ticker and t.get("status") == "OPEN":
                is_dup = True
                break
        
        if is_dup:
            return
            
        trades.append(shadow_trade)
"""

code = code.replace("        trades.append(shadow_trade)", new_logic)

with open('backend/btc/shadow_executor.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched shadow_executor.py")
