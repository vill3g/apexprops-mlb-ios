import re

with open('backend/saas_settler.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''                if not market or market.get("status") != "active" or market.get("ticker") != ticker:
                    exit_price = 1.0 if t.get("probability_percent", 50) > 50 else 0.0
                    t["status"] = "CLOSED"
                    t["reason"] = "SETTLEMENT"
                    t["pnl"] = (exit_price - entry) * count
                    modified = True
                    
                    if mode == "PAPER":
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("SELECT paper_balance FROM users WHERE id = ?", (user_id,))
                        row = c.fetchone()
                        if row:
                            new_bal = row[0] + (count * exit_price)
                            c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (new_bal, user_id))
                            conn.commit()
                        conn.close()
                    continue'''

new_block = '''                if not market or market.get("status") != "active" or market.get("ticker") != ticker:
                    from backend.btc.kalshi_trader import kalshi_trader
                    res = kalshi_trader.get_market_result(ticker)
                    ans = res.get("result", "").lower()
                    
                    exit_price = 0.0
                    if ans == "yes":
                        exit_price = 1.0 if side.upper() == "YES" else 0.0
                    elif ans == "no":
                        exit_price = 1.0 if side.upper() == "NO" else 0.0
                    else:
                        # Unresolved or synthetic. Try to fallback to probability just to close it out if it's super old, but for now we'll wait.
                        # Wait, we don't want to get stuck forever if synthetic.
                        if "SYNTH" in ticker.upper() or res.get("success") == False:
                            # Use synthetic resolution (just random fallback for now so it doesn't get stuck)
                            exit_price = 1.0 if float(t.get("probability_percent", 50)) > 50 else 0.0
                        else:
                            continue # Wait for official Kalshi resolution
                            
                    t["status"] = "CLOSED"
                    t["reason"] = "SETTLEMENT"
                    t["pnl"] = (exit_price - entry) * count
                    modified = True
                    
                    if mode == "PAPER":
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("SELECT paper_balance FROM users WHERE id = ?", (user_id,))
                        row = c.fetchone()
                        if row:
                            new_bal = row[0] + (count * exit_price)
                            c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (new_bal, user_id))
                            conn.commit()
                        conn.close()
                    continue'''

content = content.replace(old_block, new_block)

with open('backend/saas_settler.py', 'w', encoding='utf-8') as f:
    f.write(content)
