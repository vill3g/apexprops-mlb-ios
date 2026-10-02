import re

def patch_html_dropdown(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update the hidden <select> to include AUTO
    old_select = '<select id="signal-source" class="hidden" onchange="saveUserConfig()"><option value="BLEND">⚖️ BLEND</option><option value="AI_ONLY">🧠 AI ONLY</option><option value="CHART_ONLY">📊 CHART ONLY</option></select>'
    new_select = '<select id="signal-source" class="hidden" onchange="saveUserConfig()"><option value="AUTO">🤖 AUTO</option><option value="BLEND">⚖️ BLEND</option><option value="AI_ONLY">🧠 AI ONLY</option><option value="CHART_ONLY">📊 CHART ONLY</option></select>'
    
    # Also support if it was already patched or has different spacing
    pattern_select = re.compile(r'<select id="signal-source" class="hidden" onchange="saveUserConfig()">.*?</select>')
    content = pattern_select.sub(new_select, content)

    # 2. Add the UI dropdown option
    old_options = """                                    <div onclick="selectDropdownOption(this, 'BLEND', '⚖️ BLEND', event)" class="px-3 py-2 text-gray-300 hover:bg-white/10 hover:text-white cursor-pointer transition-colors">⚖️ BLEND (Optimal)</div>
                                    <div onclick="selectDropdownOption(this, 'AI_ONLY', '🧠 AI ONLY', event)" class="px-3 py-2 text-gray-300 hover:bg-white/10 hover:text-white cursor-pointer transition-colors">🧠 AI ONLY (Neural)</div>
                                    <div onclick="selectDropdownOption(this, 'CHART_ONLY', '📊 CHART ONLY', event)" class="px-3 py-2 text-gray-300 hover:bg-white/10 hover:text-white cursor-pointer transition-colors">📊 CHART ONLY (RSI/MACD)</div>"""
    
    new_options = """                                    <div onclick="selectDropdownOption(this, 'AUTO', '🤖 AUTO', event)" class="px-3 py-2 text-green-300 bg-green-900/20 hover:bg-green-900/40 hover:text-green-200 cursor-pointer transition-colors font-bold">🤖 AUTO (Dynamic Regime)</div>
                                    <div onclick="selectDropdownOption(this, 'BLEND', '⚖️ BLEND', event)" class="px-3 py-2 text-gray-300 hover:bg-white/10 hover:text-white cursor-pointer transition-colors">⚖️ BLEND (Fixed)</div>
                                    <div onclick="selectDropdownOption(this, 'AI_ONLY', '🧠 AI ONLY', event)" class="px-3 py-2 text-gray-300 hover:bg-white/10 hover:text-white cursor-pointer transition-colors">🧠 AI ONLY (Neural)</div>
                                    <div onclick="selectDropdownOption(this, 'CHART_ONLY', '📊 CHART ONLY', event)" class="px-3 py-2 text-gray-300 hover:bg-white/10 hover:text-white cursor-pointer transition-colors">📊 CHART ONLY (RSI/MACD)</div>"""

    # We need to replace it carefully
    if 'selectDropdownOption(this, \'BLEND\'' in content:
        content = re.sub(
            r"<div onclick=\"selectDropdownOption\(this, 'BLEND'.*?CHART ONLY \(RSI/MACD\)</div>",
            new_options,
            content,
            flags=re.DOTALL
        )
    
    # 3. Update JS fallback display texts
    content = content.replace(
        "signalSource === 'BLEND' ? '⚖️ BLEND'",
        "signalSource === 'AUTO' ? '🤖 AUTO' : signalSource === 'BLEND' ? '⚖️ BLEND'"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

patch_html_dropdown(r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html")
print("Patched dropdowns!")
