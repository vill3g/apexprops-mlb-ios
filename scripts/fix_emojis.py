import os

# Fix admin_users.js
file1 = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\admin_users.js"
with open(file1, "r", encoding="utf-8") as f:
    c1 = f.read()

replacements1 = {
    "?? Bot Settings": "🤖 Bot Settings",
    "<span>??</span> ?? Mode & Account State": "<span>⚙️</span> 📊 Mode & Account State",
    "?? PAPER": "📄 PAPER",
    "title=\"Reset balance to $500\"> ?? $500</button>": "title=\"Reset balance to $500\"> 🔄 $500</button>",
    "<span>??</span> ?? Autonomous Execution Toggles": "<span>⚡</span> ⚙️ Autonomous Execution Toggles"
}
for k, v in replacements1.items():
    c1 = c1.replace(k, v)
with open(file1, "w", encoding="utf-8") as f:
    f.write(c1)

# Fix saas_dashboard.html
file2 = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(file2, "r", encoding="utf-8") as f:
    c2 = f.read()

replacements2 = {
    "?? BLEND": "⚖️ BLEND",
    "?? AI ONLY": "🧠 AI ONLY",
    "?? CHART ONLY": "📊 CHART ONLY",
    "?? God-Tier Swarm": "🤖 God-Tier Swarm",
    "?? God-Tier Swarm (Ensemble)": "🤖 God-Tier Swarm (Ensemble)"
}
for k, v in replacements2.items():
    c2 = c2.replace(k, v)
with open(file2, "w", encoding="utf-8") as f:
    f.write(c2)

# Fix trades.html if it exists
file3 = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\trades.html"
if os.path.exists(file3):
    with open(file3, "r", encoding="utf-8") as f:
        c3 = f.read()
    for k, v in replacements2.items():
        c3 = c3.replace(k, v)
    with open(file3, "w", encoding="utf-8") as f:
        f.write(c3)

print("Restored emojis successfully!")
