import re

js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

# Remove the line: if (sVal === 'ML_ENSEMBLE' || sVal === 'AI_ONLY') sVal = 'RL_DQN';
pattern = r"\s*if \(sVal === 'ML_ENSEMBLE' \|\| sVal === 'AI_ONLY'\) sVal = 'RL_DQN';"
js = re.sub(pattern, "", js)

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated dashboard.js to stop overriding ML_ENSEMBLE!")
