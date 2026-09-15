import os
import re

def fix():
    file_path = 'backend/btc/auto_executor.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We need to replace the logic that defines contracts_to_buy
    
    # 1. First occurrence in check_and_execute_rollover
    pattern_1 = r'# Determine affordable contract count for live or paper\s*# ML Settings Overrides\s*contracts_to_buy = self\.max_contracts'
    replacement_1 = '''# Determine affordable contract count for live or paper
        
        # ML Settings Overrides: Use maxCap to size position
        max_cap = float(self.ai_settings.get("maxCap", 0.0))
        unit_price_est = min(0.99, max(0.01, float(market_price) + 0.04))
        
        if max_cap > 0:
            contracts_to_buy = int(max_cap // unit_price_est)
            if contracts_to_buy < 1:
                contracts_to_buy = 1
        else:
            contracts_to_buy = self.max_contracts'''
    
    content = re.sub(pattern_1, replacement_1, content)
    
    # 2. Second occurrence in execute_manual_trade
    pattern_2 = r'# Determine affordable contract count for live or paper\s*# ML Settings Overrides\s*contracts_to_buy = self\.max_contracts'
    content = re.sub(pattern_2, replacement_1, content) # It's exactly the same! Wait, let's just do a blanket replace if it matches twice. Wait, the pattern might not match the second one exactly because of lack of "Determine affordable contract count for live or paper".
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Fixed contracts_to_buy logic!")
