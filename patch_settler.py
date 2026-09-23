with open('backend/saas_settler.py', 'r', encoding='utf-8') as f:
    text = f.read()

old = '''            history.append({
                "id": trade_id,
                "ticker": ticker,
                "side": direction,
                "direction": direction,
                "prediction_direction": direction,
                "count": count,
                "entry_price": price,
                "status": "OPEN",
                "timestamp": now_est,
                "mode": mode,
                "reason": "AUTO_FORCE_TRADE"
            })'''

new = '''            history.append({
                "id": trade_id,
                "ticker": ticker,
                "side": direction,
                "direction": direction,
                "prediction_direction": direction,
                "count": count,
                "entry_price": price,
                "status": "OPEN",
                "pnl": 0.0,
                "timestamp": now_est,
                "mode": mode,
                "reason": "AUTO_FORCE_TRADE"
            })'''

text = text.replace(old, new)
with open('backend/saas_settler.py', 'w', encoding='utf-8') as f:
    f.write(text)
