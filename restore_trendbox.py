import re

# Read original
with open('orig_app.js', 'r', encoding='utf-8') as f:
    orig = f.read()

# Extract function
match = re.search(r'(    function renderBtcTrendBox\(last5, streak\) \{.*?\n    \})', orig, re.DOTALL)
if not match:
    print("Could not find function in orig_app.js")
    exit(1)
func_code = match.group(1)

# Read current
with open('static/js/app.js', 'r', encoding='utf-8') as f:
    app = f.read()

# Replace empty stub with real function
if "function renderBtcTrendBox(){}" in app:
    app = app.replace("function renderBtcTrendBox(){}", func_code)
    with open('static/js/app.js', 'w', encoding='utf-8') as f:
        f.write(app)
    print("Restored renderBtcTrendBox")
else:
    print("Could not find empty stub in app.js")
