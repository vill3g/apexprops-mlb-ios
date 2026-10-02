import re
js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()
# Replace the rendering line to show the real string
pattern = r"\$\{\(u\.signal_source === 'ML_ENSEMBLE' \|\| u\.signal_source === 'RL_DQN' \|\| u\.signal_source === 'AI_ONLY'\) \? 'RL_DQN' : escapeHtml\(u\.signal_source \|\| 'BLEND'\)\}"
replace = r"${escapeHtml(u.signal_source || 'BLEND')}"
js = re.sub(pattern, replace, js)
with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
