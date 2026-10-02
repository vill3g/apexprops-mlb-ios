import codecs
import re

with codecs.open('backend/btc/analyzer.py', 'r', 'utf-8') as f:
    text = f.read()

old_regex = re.compile(r'    else:\s*# No heuristic setup fired at all [^\n]*\s*pred = ml_pred\s*prob = ml_prob_pct\s*badge = ml_badge\s*catalysts\.append\(ml_catalyst\)')

new_replacement = r'''    else:
        # No heuristic setup fired at all.
        if iso_setting == "BLEND":
            pred = "PASS"
            prob = 50.0
            grade = "GRADE C / PASS"
            badge = "⚪ PASS (NO CHART CONFLUENCE)"
            catalysts.append("🛑 Strict BLEND Isolation: ML Model generated a signal, but Chart Technicals are neutral. Passing to enforce 100% agreement.")
        else:
            pred = ml_pred
            prob = ml_prob_pct
            badge = ml_badge
            catalysts.append(ml_catalyst)'''

text, count = old_regex.subn(new_replacement, text)
print('Regex replaced (Strict Blend):', count)

with codecs.open('backend/btc/analyzer.py', 'w', 'utf-8') as f:
    f.write(text)
