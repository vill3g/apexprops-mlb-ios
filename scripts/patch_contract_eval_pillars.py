import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject the Strike Pin Filter
strike_pin_logic = """    # 0. Empirical Strike Pin / Dead-Zone Filter (Directly addresses 32.5% of historical losses)
    # When price is pinned within $15 of the strike and volatility is low (ATR <= $45),
    # the contract expiration second is an unpredictable coin-flip on single-tick noise.
    delta_dollars = abs(c_close - target)
    delta_to_target = float(((c_close - target) / max(target, 1e-9)) * 100)
    avg_vol_20 = float(df_ind["volume"].tail(20).mean()) if "volume" in df_ind.columns and len(df_ind) >= 20 else 1.0
    curr_vol = float(c.get("volume", 0.0) or 0.0)
    is_strong_breakout = (curr_vol > avg_vol_20 * 1.8) and (abs(c_close - c_open) > atr * 0.75)
    
    if delta_dollars <= 18.0 and atr <= 45.0 and not is_strong_breakout:
        return {
            "direction": "PASS",
            "recommendation": "PASS / STRIKE PIN (DEAD-ZONE)",
            "conviction_badge": "🛑 PASS (STRIKE PIN)",
            "primary_edge": f"Spot ${c_close:,.2f} is within ${delta_dollars:.1f} of strike ${target:,.2f} under low ATR (${atr:.1f}). Skipping coin-flip.",
            "ml_probability": 50.0,
            "kalshi_strike": target,
            "catalysts": ["Dead zone filter: Price pinned near strike with low volatility."]
        }
"""

content = re.sub(
    r"    # 0\. Empirical Strike Pin.*?is_strong_breakout = \(curr_vol > avg_vol_20 \* 1\.8\) and \(abs\(c_close - c_open\) > atr \* 0\.75\)\n",
    strike_pin_logic,
    content,
    flags=re.DOTALL
)

# 2. Modify the EV Block
ev_block_old = r"""    if trading_style == "SNIPER" and iso_setting != "AI_ONLY" and kalshi_m and direction in \["ABOVE", "BELOW", "YES", "NO"\]:
        side_key = "yes_ask" if direction in \["ABOVE", "YES"\] else "no_ask"
        try:
            kalshi_ask = float\(kalshi_m\.get\(side_key\) or 0\.50\)
        except \(ValueError, TypeError\) as e:
            logger\.warning\(f"Kalshi ask fetch error: \{e\}"\)
            kalshi_ask = 0\.50

        min_ev = kalshi_ask \+ 0\.05
        current_prob = float\(prob\) / 100\.0
        
        if current_prob <= min_ev:
            catalysts\.insert\(0, f"ǽ\?\?\? Negative EV Block: ML Prob \(\{current_prob\*100:\.1f\}%\) <= Kalshi Ask \(\{kalshi_ask\*100:\.0f\}c\) \+ 5% Edge\."\)
            pred = "PASS / NO BID \(NEGATIVE EV\)"
            direction = "PASS"
            grade = "PASS / POOR RISK REWARD"
            badge = "ǽ PASS \(NEGATIVE EV\)"
            prob = 50\.0"""

ev_block_new = """    # PILLAR 1 & 2: UNIVERSAL EV GATE & SWEET SPOT PRICING
    if kalshi_m and direction in ["ABOVE", "BELOW", "YES", "NO"]:
        side_key = "yes_ask" if direction in ["ABOVE", "YES"] else "no_ask"
        try:
            kalshi_ask = float(kalshi_m.get(side_key) or 0.50)
        except (ValueError, TypeError) as e:
            logger.warning(f"Kalshi ask fetch error: {e}")
            kalshi_ask = 0.50

        min_ev = kalshi_ask + 0.05
        current_prob = float(prob) / 100.0
        
        # Pillar 1: Mathematical EV Gate
        if current_prob <= min_ev:
            catalysts.insert(0, f"⛔ Negative EV Block: ML Prob ({current_prob*100:.1f}%) <= Kalshi Ask ({kalshi_ask*100:.0f}c) + 5% Edge.")
            pred = "PASS / NO BID (NEGATIVE EV)"
            direction = "PASS"
            grade = "PASS / POOR RISK REWARD"
            badge = "⛔ PASS (NEGATIVE EV)"
            prob = 50.0
        
        # Pillar 2: Sweet Spot Pricing Limit (Avoid buying tops/bottoms unless institutional conviction)
        elif kalshi_ask > 0.62 and current_prob < 0.78:
            catalysts.insert(0, f"⏳ Overpriced Premium: Ask is {kalshi_ask*100:.0f}c but conviction ({current_prob*100:.1f}%) < 78%.")
            pred = "PASS / NO BID (OVERPRICED)"
            direction = "PASS"
            grade = "PASS / POOR RISK REWARD"
            badge = "⏳ PASS (OVERPRICED)"
            prob = 50.0"""

content = re.sub(ev_block_old, ev_block_new, content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched contract_eval.py successfully.")
