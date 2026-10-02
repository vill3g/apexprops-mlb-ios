import re

with open('backend/saas_settler.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''                tp_pct = float(user.get("take_profit_pct", 50.0)) / 100.0
                if market and market.get("ticker") == ticker:
                    curr_bid = market.get(f"{side}_bid", 0.0)
                    if entry > 0:
                        profit_pct = (curr_bid - entry) / entry
                        loss_pct = (entry - curr_bid) / entry
                        
                        trigger_exit = False
                        reason = ""
                        
                        if loss_pct >= sl_pct:
                            trigger_exit = True
                            reason = f"STOP_LOSS (-{loss_pct*100:.1f}%)"
                        elif profit_pct >= tp_pct:
                            trigger_exit = True
                            reason = f"TAKE_PROFIT (+{profit_pct*100:.1f}%)"'''

new_block = '''                tp_pct = float(user.get("take_profit_pct", 50.0)) / 100.0
                ts_enabled = bool(user.get("trailing_stop_enabled", 0))
                ts_activation = float(user.get("trailing_stop_activation_pct", 35.0)) / 100.0
                ts_distance = float(user.get("trailing_stop_distance_pct", 6.0)) / 100.0
                
                if market and market.get("ticker") == ticker:
                    curr_bid = market.get(f"{side}_bid", 0.0)
                    if entry > 0:
                        profit_pct = (curr_bid - entry) / entry
                        loss_pct = (entry - curr_bid) / entry
                        
                        max_seen_bid = float(t.get("max_seen_bid", entry))
                        if curr_bid > max_seen_bid:
                            max_seen_bid = curr_bid
                            t["max_seen_bid"] = max_seen_bid
                            modified = True
                        
                        max_seen_profit_pct = (max_seen_bid - entry) / entry
                        
                        trigger_exit = False
                        reason = ""
                        
                        if ts_enabled and max_seen_profit_pct >= ts_activation:
                            trail_threshold = max(max_seen_bid - ts_distance, max_seen_bid * (1.0 - ts_distance))
                            trail_threshold = max(trail_threshold, entry * 1.02)
                            if curr_bid <= trail_threshold:
                                trigger_exit = True
                                reason = f"TRAILING_STOP (+{profit_pct*100:.1f}%)"
                        
                        if not trigger_exit:
                            if loss_pct >= sl_pct:
                                trigger_exit = True
                                reason = f"STOP_LOSS (-{loss_pct*100:.1f}%)"
                            elif profit_pct >= tp_pct:
                                trigger_exit = True
                                reason = f"TAKE_PROFIT (+{profit_pct*100:.1f}%)"'''

content = content.replace(old_block, new_block)

with open('backend/saas_settler.py', 'w', encoding='utf-8') as f:
    f.write(content)
