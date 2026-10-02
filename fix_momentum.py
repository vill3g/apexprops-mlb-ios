import re

fpath = 'backend/btc/analyzer/contract_eval.py'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

# Instead of relying on exact emoji matches, use a regex
pattern = re.compile(
    r'(if ml_prob_for_pred_dir < 50\.0 and disagreement >= THRESHOLDS\["model_conflict_threshold"\]:)\n'
    r'(\s+catalysts\.append\(f".*?Model Conflict.*?)\n'
    r'(\s+# If technical setup is Grade A or A\+.*?\n'
    r'\s+# High-conviction patterns.*?\n'
    r'\s+if "GRADE A" in grade:\n'
    r'\s+blended_prob = max\(64\.0, min\(blended_prob, 68\.0\)\)\n'
    r'\s+else:\n'
    r'\s+blended_prob = min\(blended_prob, THRESHOLDS\["model_conflict_cap"\]\)\n'
    r'\s+if "GRADE A\+" in grade:\n'
    r'\s+grade = "GRADE A SETUP"\n)'
    r'(\s+else:\n'
    r'\s+catalysts\.append\()',
    re.MULTILINE | re.DOTALL
)

def replacer(match):
    return (
        match.group(1) + '\n' +
        '            if trading_style == "MOMENTUM_SURFER":\n' +
        '                catalysts.append(f"🏄 Momentum Override: Chart setup favors {pred} ({prob}%). Ignoring ML model disagreement ({ml_prob_for_pred_dir:.1f}%) due to active momentum regime.")\n' +
        '                blended_prob = prob\n' +
        '            else:\n' +
        '    ' + match.group(2) + '\n' +
        match.group(3).replace('\n            ', '\n                ') +
        match.group(4)
    )

new_text = pattern.sub(replacer, text)

if new_text != text:
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Momentum override successfully injected.")
else:
    print("Regex failed to match. Let's print out what we see.")
