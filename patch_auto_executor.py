with open('backend/btc/auto_executor.py', 'r', encoding='utf-8') as f:
    text = f.read()

old = '''                            hist.append({
                                "id": trade_id,
                                "timestamp": now_est,
                                "ticker": current_interval_id,
                                "direction": side.upper(),
                                "side": side.upper(),
                                "prediction_direction": side.upper(),
                                "probability_percent": conf,
                                "entry_price": filled_price,
                                "count": contracts,
                                "status": "OPEN",
                                "mode": user_mode,
                                "reason": f"AI_COPY ({eff_style})"
                            })'''

new = '''                            hist.append({
                                "id": trade_id,
                                "timestamp": now_est,
                                "ticker": current_interval_id,
                                "direction": side.upper(),
                                "side": side.upper(),
                                "prediction_direction": side.upper(),
                                "probability_percent": conf,
                                "entry_price": filled_price,
                                "count": contracts,
                                "status": "OPEN",
                                "pnl": 0.0,
                                "close_epoch": active_m.get("close_epoch", 0.0),
                                "mode": user_mode,
                                "reason": f"AI_COPY ({eff_style})"
                            })'''

text = text.replace(old, new)
with open('backend/btc/auto_executor.py', 'w', encoding='utf-8') as f:
    f.write(text)
