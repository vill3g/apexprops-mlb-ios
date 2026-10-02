import re
path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer\contract_eval.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'    else:\n        # No heuristic setup fired at all\.\n        if iso_setting == "BLEND":\n            pred = "PASS"\n            prob = 50\.0\n            grade = "GRADE C / PASS"\n            badge = "[^\"]+" PASS \(NO CHART CONFLUENCE\)"\n            catalysts\.append\("[^\"]+ Strict BLEND Isolation: ML Model generated a signal, but Chart Technicals are neutral\. Passing to enforce 100% agreement\."\)\n        else:'

new_block = """    else:
        # No heuristic setup fired at all.
        if iso_setting == "BLEND":
            if 0.45 <= ml_prob <= 0.55:
                pred = "PASS"
                prob = 50.0
                grade = "GRADE C / PASS"
                badge = "⚪ PASS (LOW ML CONVICTION)"
                catalysts.append("🛑 Fake Edge Suppression: No chart setup fired and ML conviction is weak (Neutral). Passing.")
            else:
                pred = ml_pred
                prob = ml_prob_pct
                badge = ml_badge
                catalysts.append(f"🤖 ML Conviction: No chart setup fired, but ML generated strong signal ({ml_prob_pct:.1f}%). Trusting ML.")
                if ml_catalyst:
                    catalysts.append(ml_catalyst)
        else:"""

new_text = re.sub(pattern, new_block, text)

if new_text != text:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print('Patched contract_eval.py BLEND logic.')
else:
    print('Pattern not found!')
