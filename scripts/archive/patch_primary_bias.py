import re

with open('backend/btc/analyzer.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_block3 = """    if primary_bias == "UP":
        sl_distance = max(1.2 * atr, curr_price - near_support)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price - sl_distance, 2)
        
        # M2: Constrain TP1 to structural resistance if closer than standard 1.5R
        raw_tp1 = curr_price + (1.5 * sl_distance)
        if near_resistance > curr_price:
            tp1_val = min(raw_tp1, near_resistance)
            tp1_val = max(tp1_val, curr_price + (0.5 * atr)) # Ensure minimum viable profit distance
        else:
            tp1_val = raw_tp1
        tp1 = round(tp1_val, 2)
        tp2 = round(max(tp1 + (1.0 * sl_distance), curr_price + (2.5 * sl_distance)), 2)
        
        rr1 = round(abs(tp1 - curr_price) / max(sl_distance, 1e-9), 2)
        rr2 = round(abs(tp2 - curr_price) / max(sl_distance, 1e-9), 2)
        risk_pct = round((sl_distance / max(curr_price, 1e-9)) * 100, 2)
        setup = {
            "direction": "BUY (UP)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    elif primary_bias == "DOWN":
        sl_distance = max(1.2 * atr, near_resistance - curr_price)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price + sl_distance, 2)
        
        # M2: Constrain TP1 to structural support if closer than standard 1.5R
        raw_tp1 = curr_price - (1.5 * sl_distance)
        if near_support < curr_price:
            tp1_val = max(raw_tp1, near_support)
            tp1_val = min(tp1_val, curr_price - (0.5 * atr)) # Ensure minimum viable profit distance
        else:
            tp1_val = raw_tp1
        tp1 = round(tp1_val, 2)
        tp2 = round(min(tp1 - (1.0 * sl_distance), curr_price - (2.5 * sl_distance)), 2)
        
        rr1 = round(abs(curr_price - tp1) / max(sl_distance, 1e-9), 2)
        rr2 = round(abs(curr_price - tp2) / max(sl_distance, 1e-9), 2)
        risk_pct = round((sl_distance / max(curr_price, 1e-9)) * 100, 2)
        setup = {
            "direction": "SELL (DOWN)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    else:"""

new_block3 = """    if primary_bias == "UP":
        sl_distance = max(1.2 * atr, curr_price - near_support)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price - sl_distance, 2)
        
        # M2: Constrain TP1 to structural resistance if closer than standard 1.5R
        raw_tp1 = curr_price + (1.5 * sl_distance)
        if near_resistance > curr_price:
            tp1_val = min(raw_tp1, near_resistance)
            tp1_val = max(tp1_val, curr_price + (0.5 * atr)) # Ensure minimum viable profit distance
        else:
            tp1_val = raw_tp1
        tp1 = round(tp1_val, 2)
        tp2 = round(max(tp1 + (1.0 * sl_distance), curr_price + (2.5 * sl_distance)), 2)
        
        rr1 = round(abs(tp1 - curr_price) / max(sl_distance, 1e-9), 2)
        rr2 = round(abs(tp2 - curr_price) / max(sl_distance, 1e-9), 2)
        risk_pct = round((sl_distance / max(curr_price, 1e-9)) * 100, 2)
        setup = {
            "direction": "BUY (UP)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    elif primary_bias == "DOWN":
        sl_distance = max(1.2 * atr, near_resistance - curr_price)
        sl_distance = min(sl_distance, 2.5 * atr)
        stop_loss = round(curr_price + sl_distance, 2)
        
        # M2: Constrain TP1 to structural support if closer than standard 1.5R
        raw_tp1 = curr_price - (1.5 * sl_distance)
        if near_support < curr_price:
            tp1_val = max(raw_tp1, near_support)
            tp1_val = min(tp1_val, curr_price - (0.5 * atr)) # Ensure minimum viable profit distance
        else:
            tp1_val = raw_tp1
        tp1 = round(tp1_val, 2)
        tp2 = round(min(tp1 - (1.0 * sl_distance), curr_price - (2.5 * sl_distance)), 2)
        
        rr1 = round(abs(curr_price - tp1) / max(sl_distance, 1e-9), 2)
        rr2 = round(abs(curr_price - tp2) / max(sl_distance, 1e-9), 2)
        risk_pct = round((sl_distance / max(curr_price, 1e-9)) * 100, 2)
        setup = {
            "direction": "SELL (DOWN)",
            "entry_price": round(curr_price, 2),
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "risk_reward_1": rr1,
            "risk_reward_2": rr2,
            "risk_amount": round(sl_distance, 2),
            "risk_percent": risk_pct,
            "breakeven_rule": f"Move SL to Breakeven (${round(curr_price, 2)}) after TP1 hit"
        }
    else:
        direction = "PASS"
        action = "PASS" """

code = code.replace(old_block3, new_block3)

with open('backend/btc/analyzer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched heuristic direction bug!")
