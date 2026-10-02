with open('backend/auth/routes.py', 'r', encoding='utf-8') as f:
    c = f.read()
target = '''                if m.get(\"ticker\") == tk:
                    exit_price = float(m.get(\"yes_bid\", entry) if side == \"YES\" else m.get(\"no_bid\", entry))
                    if exit_price <= 0:
                        prob = float(m.get(\"yes_prob\" if side == \"YES\" else \"no_prob\", 50.0)) / 100.0
                        exit_price = prob if prob > 0 else entry'''
replacement = '''                if m.get(\"ticker\") == tk:
                    if m.get(\"status\") == \"synthetic\" and \"strike\" in t:
                        spot = float(m.get(\"target_price\", 0.0))
                        strike = float(t.get(\"strike\", 0.0))
                        if spot > 0 and strike > 0:
                            pct_move = (spot - strike) / strike
                            sign = 1 if side == \"YES\" else -1
                            edge = (pct_move * sign) * 500.0
                            exit_price = max(0.01, min(0.99, entry + edge))
                        else:
                            exit_price = float(m.get(\"yes_bid\", entry) if side == \"YES\" else m.get(\"no_bid\", entry))
                    else:
                        exit_price = float(m.get(\"yes_bid\", entry) if side == \"YES\" else m.get(\"no_bid\", entry))
                        if exit_price <= 0:
                            prob = float(m.get(\"yes_prob\" if side == \"YES\" else \"no_prob\", 50.0)) / 100.0
                            exit_price = prob if prob > 0 else entry'''
c = c.replace(target, replacement)
with open('backend/auth/routes.py', 'w', encoding='utf-8') as f:
    f.write(c)
print('Replaced PnL calculation')
