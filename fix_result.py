import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

pattern = r"(if \(res === 'WIN'\) \{)([\s\S]*?)(else if \(res === 'LOSS'\) \{)([\s\S]*?)(else if \(res === 'STOP OUT'\))"

def replacer(match):
    return """if (res === 'WIN' || (!res && isWin)) {
                        const settledDir = side.toUpperCase();
                        targetResultEl.innerText = 'SETTLED ' + settledDir + ' (WIN)';
                        targetResultEl.className = 'text-sm font-black uppercase text-emerald-400';
                    } else if (res === 'LOSS' || (!res && isLoss)) {
                        const settledDir = side.toUpperCase() === 'YES' ? 'NO' : 'YES';
                        targetResultEl.innerText = 'SETTLED ' + settledDir + ' (LOSS)';
                        targetResultEl.className = 'text-sm font-black uppercase text-rose-400';
                    } """ + match.group(5)

new_js = re.sub(pattern, replacer, js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(new_js)
print("Updated dashboard.js to show SETTLED direction!")
