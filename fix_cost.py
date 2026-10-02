import re

def fix_cost_logic(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()

    pattern1 = r'contracts = int\(risk_amount / max\(0\.01, (.*?)\)\)\n.*?while contracts > 0 and \(contracts \* \1\) > risk_amount:\n.*?contracts -= 1'
    def repl1(match):
        price_var = match.group(1)
        return f"""contracts = int(risk_amount / max(0.01, {price_var}))
                            while contracts > 0 and (contracts * {price_var} + kalshi_order_fee({price_var}, contracts)) > risk_amount:
                                contracts -= 1"""
    code = re.sub(pattern1, repl1, code)
    
    pattern2 = r'count = int\(amount / price\)\n.*?while count > 0 and \(count \* price\) > amount:\n.*?count -= 1'
    def repl2(match):
        return """count = int(amount / price)
      while count > 0 and (count * price + kalshi_order_fee(price, count)) > amount:
          count -= 1"""
    code = re.sub(pattern2, repl2, code)

    pattern3 = r'count = max\(1, int\(risk_amount / max\(0\.01, price\)\)\)'
    def repl3(match):
        return """count = max(1, int(risk_amount / max(0.01, price)))
          while count > 1 and (count * price + kalshi_order_fee(price, count)) > risk_amount:
              count -= 1"""
    code = re.sub(pattern3, repl3, code)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

fix_cost_logic("backend/btc/auto_executor/saas_broadcaster.py")
fix_cost_logic("backend/auth/routes.py")
print("Fixed cost logic!")
