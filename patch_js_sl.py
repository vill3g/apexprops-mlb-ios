import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add to generateSettingsPayload()
content = content.replace(
    "stop_loss_pct: parseFloat(document.getElementById('stop-loss-pct')?.value) || 10.0,",
    "stop_loss_pct: parseFloat(document.getElementById('stop-loss-pct')?.value) || 10.0,\n        stop_loss_enabled: document.getElementById('stop-loss-enabled')?.checked ?? true,"
)

# 2. Add to config population
content = content.replace(
    "if (payload.stop_loss_pct) document.getElementById('stop-loss-pct').value = payload.stop_loss_pct;",
    "if (payload.stop_loss_pct) document.getElementById('stop-loss-pct').value = payload.stop_loss_pct;\n        if (payload.stop_loss_enabled !== undefined) {\n            document.getElementById('stop-loss-enabled').checked = payload.stop_loss_enabled;\n            toggleStopLossPctVisibility();\n        }"
)

# 3. Add to s variable population
content = content.replace(
    "if(document.getElementById('take-profit-pct')",
    "const slEnabledToggle = document.getElementById('stop-loss-enabled');\n                    if(slEnabledToggle && s.stop_loss_enabled !== undefined && document.activeElement.id !== 'stop-loss-enabled') {\n                        slEnabledToggle.checked = s.stop_loss_enabled;\n                        toggleStopLossPctVisibility();\n                    }\n                    if(document.getElementById('take-profit-pct')"
)

# 4. Add the toggle function
content = content.replace(
    "function toggleTakeProfitPctVisibility() {",
    "window.toggleStopLossPctVisibility = function() {\n    const isEnabled = document.getElementById('stop-loss-enabled')?.checked;\n    const row = document.getElementById('stop-loss-pct-row');\n    if(row) {\n        if(isEnabled) {\n            row.style.maxHeight = row.scrollHeight + 'px';\n            row.style.opacity = '1';\n            row.style.marginTop = '0.75rem';\n        } else {\n            row.style.maxHeight = '0';\n            row.style.opacity = '0';\n            row.style.marginTop = '0';\n        }\n    }\n}\n\nfunction toggleTakeProfitPctVisibility() {"
)

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated dashboard.js!")
