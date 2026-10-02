import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

pattern = r"else if \(res === 'MANUAL EXIT'\) \{([\s\S]*?)\} else \{"

def replacer(match):
    return """else if (res === 'MANUAL EXIT') {""" + match.group(1) + """} else if (isWin || isLoss) {
                        const settledDir = (side === 'YES') ? (isWin ? 'YES' : 'NO') : (isWin ? 'NO' : 'YES');
                        targetResultEl.innerText = 'SETTLED ' + settledDir;
                        targetResultEl.className = 'text-sm font-black uppercase ' + (isWin ? 'text-emerald-400' : 'text-rose-400');
                    } else {"""

new_js = re.sub(pattern, replacer, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(new_js)
print("Added fallback for final market result!")
