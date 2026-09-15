from backend.btc.kalshi_trader import kalshi_trader
pos_res = kalshi_trader.get_positions()
pos_list = pos_res.get("positions", [])
kalshi_pos_map = {p.get("ticker"): float(p.get("position_fp", 0.0) or 0.0) for p in pos_list}
print(kalshi_pos_map)
