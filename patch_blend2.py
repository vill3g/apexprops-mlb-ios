import codecs
import re

with codecs.open('backend/btc/analyzer.py', 'r', 'utf-8') as f:
    text = f.read()

# Replace the disagreement logic in analyzer.py
old_regex = re.compile(r'        if ml_prob_for_pred_dir < 50\.0 and disagreement >= THRESHOLDS\["model_conflict_threshold"\]:\n\s*catalysts\.append\([^\n]*\)\n\s*# If technical setup is Grade A[^\n]*\n\s*# High-conviction patterns[^\n]*\n\s*if "GRADE A" in grade:\n\s*blended_prob = max\(64\.0, min\(blended_prob, 68\.0\)\)\n\s*else:\n\s*blended_prob = min\(blended_prob, THRESHOLDS\["model_conflict_cap"\]\)\n\s*if "GRADE A\+" in grade:\n\s*grade = "GRADE A SETUP"\n')

new_replacement = r'''        if ml_prob_for_pred_dir < 50.0:
            if iso_setting == "BLEND":
                pred = "PASS"
                blended_prob = 50.0
                grade = "GRADE C / PASS"
                catalysts.append(f"🛑 Strict BLEND Isolation: Chart setup favors {pred} but ML model explicitly disagrees ({ml_prob_for_pred_dir:.1f}%). Passing to enforce 100% agreement.")
            elif disagreement >= THRESHOLDS["model_conflict_threshold"]:
                catalysts.append(f"⚠️ Model Conflict: Chart setup favors {pred} ({prob}%) but ML model disagrees ({ml_prob_for_pred_dir:.1f}% for this side) - confidence adjusted")
                if "GRADE A" in grade:
                    blended_prob = max(64.0, min(blended_prob, 68.0))
                else:
                    blended_prob = min(blended_prob, THRESHOLDS["model_conflict_cap"])
                    if "GRADE A+" in grade:
                        grade = "GRADE A SETUP"
'''

text, count = old_regex.subn(new_replacement, text)
print('Regex replaced (Strict Blend Disagreement):', count)

with codecs.open('backend/btc/analyzer.py', 'w', 'utf-8') as f:
    f.write(text)
