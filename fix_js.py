import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

# 1. Update _executeSaveUserConfig
pattern1 = r"(const tp = parseFloat\(document\.getElementById\('take-profit-pct'\)\?\.value\) \|\| 50\.0;)"
replace1 = r"\1\n                const tpEnabled = document.getElementById('take-profit-enabled')?.checked ?? true;"
js = re.sub(pattern1, replace1, js)

pattern1_payload = r"(take_profit_pct: tp,)"
replace1_payload = r"\1\n                    take_profit_enabled: tpEnabled,"
js = re.sub(pattern1_payload, replace1_payload, js)

# 2. Update populate payload loop (updateDashboard)
pattern2 = r"(if\(document\.getElementById\('take-profit-pct'\) && document\.activeElement\.id !== 'take-profit-pct'\) \{\s*document\.getElementById\('take-profit-pct'\)\.value = s\.take_profit_pct !== undefined \? s\.take_profit_pct : 50;\s*\})"
replace2 = r"\1\n                    const tpEnabledToggle = document.getElementById('take-profit-enabled');\n                    if(tpEnabledToggle && s.take_profit_enabled !== undefined && document.activeElement.id !== 'take-profit-enabled') {\n                        tpEnabledToggle.checked = s.take_profit_enabled;\n                        toggleTakeProfitPctVisibility();\n                    }"
js = re.sub(pattern2, replace2, js)

# 3. Update create profile (payload creation)
pattern3 = r"(take_profit_pct: parseFloat\(document\.getElementById\('take-profit-pct'\)\?\.value\) \|\| 50\.0,)"
replace3 = r"\1\n        take_profit_enabled: document.getElementById('take-profit-enabled')?.checked ?? true,"
js = re.sub(pattern3, replace3, js)

# 4. Update load profile
pattern4 = r"(if \(payload\.take_profit_pct\) document\.getElementById\('take-profit-pct'\)\.value = payload\.take_profit_pct;)"
replace4 = r"\1\n        if (payload.take_profit_enabled !== undefined) {\n            document.getElementById('take-profit-enabled').checked = payload.take_profit_enabled;\n            toggleTakeProfitPctVisibility();\n        }"
js = re.sub(pattern4, replace4, js)

# 5. Add toggleTakeProfitPctVisibility function
func = """
function toggleTakeProfitPctVisibility() {
    const isEnabled = document.getElementById('take-profit-enabled')?.checked;
    const row = document.getElementById('take-profit-pct-row');
    if(row) {
        if(isEnabled) {
            row.style.height = row.scrollHeight + "px";
            row.style.opacity = "1";
            row.style.marginTop = "0.75rem";
            row.style.pointerEvents = "auto";
        } else {
            row.style.height = "0px";
            row.style.opacity = "0";
            row.style.marginTop = "0px";
            row.style.pointerEvents = "none";
        }
    }
}
window.toggleTakeProfitPctVisibility = toggleTakeProfitPctVisibility;
"""
js += func

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated dashboard.js for take profit toggle!")
