import re

with open('backend/routes/engine.py', 'r') as f:
    c = f.read()

import_stmt = "from backend.engine.market_matcher import find_best_market_for_pick\n"
if import_stmt not in c:
    idx = c.find("import logging")
    c = c[:idx] + import_stmt + c[idx:]

# Let's replace the whole matching block
pattern = r"edge = 0\.0\s+if conf > 0 and has_valid_pick:.*?# Extract market odds / prices from first market if available"
replacement = """
                    is_alt_line = False
                    is_yes_side = True
                    if conf > 0 and has_valid_pick:
                        best_mkt, is_yes_side, edge, conf, is_alt_line = find_best_market_for_pick(markets, best_pick, milestone)
                        if best_mkt:
                            markets = [best_mkt] + [m for m in markets if m != best_mkt]
                            
                    # Extract market odds / prices from first market if available"""
                    
c = re.sub(pattern, replacement, c, flags=re.DOTALL)

with open('backend/routes/engine.py', 'w') as f:
    f.write(c)
