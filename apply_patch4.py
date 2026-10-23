import re

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

# Fix sizing inside PAPER
paper_sizing_old = '''                max_p = min(0.99, max(0.01, float(price) + 0.04))
                count = max(1, int(wager / max_p))
                cost = round(price * count, 2)
                
                # Deduct unified paper balance'''
paper_sizing_new = '''                count, worst_cost = _size_sports_order(wager, price)
                if count < 1:
                    continue
                cost = round(price * count + kalshi_order_fee(price, count), 2)
                
                # Deduct unified paper balance'''

if paper_sizing_old in code:
    code = code.replace(paper_sizing_old, paper_sizing_new)

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)
