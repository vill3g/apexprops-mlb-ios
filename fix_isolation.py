import re

fpath = 'backend/btc/analyzer/contract_eval.py'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Patch AI_ONLY Guardrail
ai_old = """    elif iso_setting == "AI_ONLY":
        pred = ml_pred
        prob = ml_prob_pct
        grade = "GRADE A SETUP" if prob >= 65 else "GRADE B SETUP" if prob >= 58 else "GRADE C / PASS"
        badge = ml_badge
        catalysts = [ml_catalyst]"""

ai_new = """    elif iso_setting == "AI_ONLY":
        pred = ml_pred
        prob = ml_prob_pct
        cvd_accel = float(c.get("cvd_acceleration", 0.0))
        
        is_bull_blocked = ("YES" in str(pred) or "ABOVE" in str(pred)) and cvd_accel < -0.15
        is_bear_blocked = ("NO" in str(pred) or "BELOW" in str(pred)) and cvd_accel > 0.15
        
        if is_bull_blocked or is_bear_blocked:
            dir_str = "UP" if is_bull_blocked else "DOWN"
            catalysts = [ml_catalyst, f"🛑 AI_ONLY Reality Check: ML wants {dir_str}, but live volume delta (CVD) is aggressively opposing. Trade blocked."]
            pred = "PASS / NO BID (REALITY CHECK)"
            prob = 50.0
            grade = "PASS / HIGH RISK"
            badge = "⚠️ PASS (CVD BLOCK)"
        else:
            grade = "GRADE A SETUP" if prob >= 65 else "GRADE B SETUP" if prob >= 58 else "GRADE C / PASS"
            badge = ml_badge
            catalysts = [ml_catalyst]"""

text = text.replace(ai_old, ai_new)


# 2. Patch CHART_ONLY Volumetric Edge Scaling
chart_old = """    if iso_setting == "CHART_ONLY":
        if pred:
            pass
        else:
            pred = "PASS"
            prob = 50.0
            grade = "GRADE C / PASS"
            badge = "s PASS (NO CHART CONFLUENCE)" """

chart_new = """    if iso_setting == "CHART_ONLY":
        if pred and "PASS" not in str(pred):
            cvd_accel = float(c.get("cvd_acceleration", 0.0))
            if ("YES" in str(pred) or "ABOVE" in str(pred)):
                if cvd_accel > 0.1:
                    prob = min(95.0, prob + 6.0)
                    catalysts.append(f"📈 Volumetric Boost: Strong positive CVD confirms technical pattern (+6% Edge)")
                    if prob >= 75.0: grade = "GRADE A+ SETUP"
                elif cvd_accel < -0.1:
                    prob = max(50.0, prob - 10.0)
                    catalysts.append(f"📉 Volumetric Penalty: Negative CVD conflicts with bullish pattern (-10% Edge)")
            elif ("NO" in str(pred) or "BELOW" in str(pred)):
                if cvd_accel < -0.1:
                    prob = min(95.0, prob + 6.0)
                    catalysts.append(f"📉 Volumetric Boost: Strong negative CVD confirms technical pattern (+6% Edge)")
                    if prob >= 75.0: grade = "GRADE A+ SETUP"
                elif cvd_accel > 0.1:
                    prob = max(50.0, prob - 10.0)
                    catalysts.append(f"📈 Volumetric Penalty: Positive CVD conflicts with bearish pattern (-10% Edge)")
        else:
            pred = "PASS"
            prob = 50.0
            grade = "GRADE C / PASS"
            badge = "⚖️ PASS (NO CHART CONFLUENCE)" """

# Handle the weird encoding character from the old read if present
import re
text = re.sub(r'    if iso_setting == "CHART_ONLY":\n        if pred:\n            pass\n        else:\n            pred = "PASS"\n            prob = 50\.0\n            grade = "GRADE C / PASS"\n            badge = ".*? PASS \(NO CHART CONFLUENCE\)"', chart_new, text)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Signal Isolation Upgrades Applied successfully!")
