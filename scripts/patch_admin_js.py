import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\js\admin_users.js"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

old_select = """              <div class="mb-3">
                <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Signal Source</label>
                <select id="edit_signal_source" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-bold text-white focus:border-cyan-500 focus:outline-none">
                  <option value="RL_DQN" ${u.signal_source === "RL_DQN" || u.signal_source === "AI_ONLY" ? "selected" : ""}>🧠 Primary AI Engine (100% AI)</option>
                  <option value="BLEND" ${u.signal_source === "BLEND" || !u.signal_source ? "selected" : ""}>⚖️ BLEND (AI Model + Chart Confluence)</option>
                  <option value="TECHNICAL_ONLY" ${u.signal_source === "TECHNICAL_ONLY" || u.signal_source === "CHART_ONLY" ? "selected" : ""}>📊 TECHNICAL_ONLY (100% Chart)</option>"""

new_select = """              <div class="mb-3">
                <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">Signal Source</label>
                <select id="edit_signal_source" class="w-full bg-slate-950 border border-slate-700 rounded-lg py-1.5 px-2 text-xs font-bold text-white focus:border-cyan-500 focus:outline-none">
                  <option value="AUTO" ${u.signal_source === "AUTO" ? "selected" : ""}>🤖 AUTO (Dynamic Regime Engine)</option>
                  <option value="RL_DQN" ${u.signal_source === "RL_DQN" || u.signal_source === "AI_ONLY" ? "selected" : ""}>🧠 Primary AI Engine (100% AI)</option>
                  <option value="BLEND" ${u.signal_source === "BLEND" || !u.signal_source ? "selected" : ""}>⚖️ BLEND (AI Model + Chart Confluence)</option>
                  <option value="TECHNICAL_ONLY" ${u.signal_source === "TECHNICAL_ONLY" || u.signal_source === "CHART_ONLY" ? "selected" : ""}>📊 TECHNICAL_ONLY (100% Chart)</option>"""

content = content.replace(old_select, new_select)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched admin_users.js successfully")
