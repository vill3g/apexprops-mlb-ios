import re

with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = '''                if direction not in ["BUY YES", "BUY NO"] or conf < min_conf:
                    continue
                    
                side = "yes" if "YES" in direction else "no"'''

new_logic = '''                dir_clean = str(direction).upper().strip()
                if dir_clean in ["ABOVE", "UP", "YES", "BUY YES", "BID YES", "STRONG BULLISH (UP)", "BULLISH (UP)"]:
                    side = "yes"
                elif dir_clean in ["BELOW", "DOWN", "NO", "BUY NO", "BID NO", "STRONG BEARISH (DOWN)", "BEARISH (DOWN)"]:
                    side = "no"
                else:
                    continue
                    
                if conf < min_conf:
                    continue'''

content = content.replace(old_logic, new_logic)

with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
