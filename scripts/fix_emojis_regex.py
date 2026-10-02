import re
import os

files = [
    r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html",
    r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\trades.html",
    r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\admin_users.js"
]

def fix_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # The emojis got corrupted into things like Y or s-?
    # We will use regex to find and replace them based on the text following them.

    # 1. Trading Styles
    content = re.sub(r"[^\x00-\x7F]* AUTO", "🤖 AUTO", content)
    content = re.sub(r"[^\x00-\x7F]* PREDICTION", "🔮 PREDICTION", content)
    content = re.sub(r"[^\x00-\x7F]* SNIPER", "🎯 SNIPER", content)
    content = re.sub(r"[^\x00-\x7F]* MOMENTUM_SURFER", "🏄 MOMENTUM", content)
    content = re.sub(r"[^\x00-\x7F]* MOMENTUM", "🏄 MOMENTUM", content)
    content = re.sub(r"[^\x00-\x7F]* AMBUSH", "🥷 AMBUSH", content)
    content = re.sub(r"[^\x00-\x7F]* CHOP", "🪓 CHOP", content)
    content = re.sub(r"[^\x00-\x7F]* CAP. GUARD", "🛡️ CAP. GUARD", content)
    content = re.sub(r"[^\x00-\x7F]* CAPITAL_GUARD", "🛡️ CAP. GUARD", content)
    
    # 2. Signal Sources
    content = re.sub(r"[^\x00-\x7F]* BLEND", "⚖️ BLEND", content)
    content = re.sub(r"[^\x00-\x7F]* AI ONLY", "🧠 AI ONLY", content)
    content = re.sub(r"[^\x00-\x7F]* CHART ONLY", "📊 CHART ONLY", content)

    # 3. Models
    content = re.sub(r"[^\x00-\x7F]* God-Tier Swarm", "🤖 God-Tier Swarm", content)
    content = re.sub(r"[^\x00-\x7F]* Deep Q-Network", "🧠 Deep Q-Network", content)
    content = re.sub(r"[^\x00-\x7F]* Priced Q-Network", "💸 Priced Q-Network", content)
    content = re.sub(r"[^\x00-\x7F]* XGBoost Trees", "🌲 XGBoost Trees", content)
    content = re.sub(r"[^\x00-\x7F]* Logistic Reg.", "📈 Logistic Reg.", content)

    # 4. Others
    content = re.sub(r"[^\x00-\x7F]* Balanced", "⚖️ Balanced", content)
    content = re.sub(r"[^\x00-\x7F]* None", "🚫 None", content)

    # Note: re.sub will replace e.g. "🤖 AUTO" if it was already fixed, because [^\x00-\x7F] matches emojis!
    # So we don't end up with "🤖🤖 AUTO". Wait! `[^\x00-\x7F]* ` will match "🤖 AUTO" and replace it with "🤖 AUTO". That's perfect.

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Fixed emojis in {filepath}")

for f in files:
    fix_file(f)
