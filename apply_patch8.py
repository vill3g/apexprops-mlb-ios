import re

with open('backend/sports_bridge/executor.py', 'r') as f:
    code = f.read()

patt_sizing = r'max_p\s*=\s*min\(0\.99,\s*max\(0\.01,\s*float\(price\)\s*\+\s*0\.04\)\).*?cost\s*=\s*round\(price\s*\*\s*count,\s*2\)'

new_sizing = '''count, worst_cost = _size_sports_order(wager, price)
                if count < 1:
                    continue
                cost = round(price * count + kalshi_order_fee(price, count), 2)'''

code = re.sub(patt_sizing, new_sizing, code, flags=re.DOTALL)

with open('backend/sports_bridge/executor.py', 'w') as f:
    f.write(code)
