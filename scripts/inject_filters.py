import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Locate the spot just before:
#     # For mid-candle styles (MOMENTUM_SURFER, AMBUSH, BLEND) or AUTO during mid-candle, evaluate the live active candle.
search_str = "    # For mid-candle styles (MOMENTUM_SURFER"

injection = """
    # --- TEAMWORK AUDIT FIX 1: Diurnal Accuracy Collapse (Night Session) ---
    import time
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        now_ny = datetime.now(ZoneInfo("America/New_York"))
        if 0 <= now_ny.hour < 7:
            return {
                "recommendation": "PASS / NO BID (NIGHT SESSION)",
                "direction": "PASS",
                "action_type": "PASS",
                "probability_percent": 50.0,
                "predicted_probability": 0.5,
                "ml_prob": 0.5,
                "pre_gate_direction": "PASS",
                "pre_gate_prob": 50.0,
                "pre_gate_grade": "GRADE C / PASS",
                "conviction_grade": "PASS / NO BID (NIGHT SESSION)",
                "conviction_badge": "🌙 PASS (NIGHT SESSION)",
                "target_settlement_zone": "--",
                "primary_edge": "Low-liquidity night session (00:00 - 06:59 ET). Bypassing to avoid chop.",
                "catalysts": ["Night Session circuit breaker active"],
                "raw_features": [],
            }
    except Exception as e:
        pass

    # --- TEAMWORK AUDIT FIX 2: Strike Pinning Basis Risk ---
    if target_price:
        c_close_check = float(df_ind.iloc[-1]["close"])
        atr_check = float(df_ind.iloc[-1].get("atr", 50.0))
        delta_check = abs(c_close_check - target_price)
        if delta_check <= 18.0 and atr_check <= 45.0:
            return {
                "recommendation": "PASS / NO BID (STRIKE PINNING)",
                "direction": "PASS",
                "action_type": "PASS",
                "probability_percent": 50.0,
                "predicted_probability": 0.5,
                "ml_prob": 0.5,
                "pre_gate_direction": "PASS",
                "pre_gate_prob": 50.0,
                "pre_gate_grade": "GRADE C / PASS",
                "conviction_grade": "PASS / NO BID (STRIKE PINNING)",
                "conviction_badge": "🧲 PASS (STRIKE PINNING)",
                "target_settlement_zone": "--",
                "primary_edge": f"Strike pinning risk. Price oscillating directly on strike (|Delta| ${delta_check:.2f} <= $18).",
                "catalysts": ["Strike Pinning circuit breaker active"],
                "raw_features": [],
            }

"""

if "TEAMWORK AUDIT FIX 1" not in content:
    content = content.replace(search_str, injection + search_str)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Injected fixes 1 & 2")
else:
    print("Already injected")
