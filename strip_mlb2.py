import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove closeModal which references deepDiveModal
text = re.sub(r'function closeModal\(\) \{.*?\n      \}', '', text, flags=re.DOTALL)
# Remove allPitcherProps etc.
text = re.sub(r'let allPitcherProps = \[\];\n      let top5Pitchers = \[\];\n      let currentModalPlayer = null;', '', text)
text = re.sub(r'function getAnyProp\(id\) \{.*?\n      \}', '', text, flags=re.DOTALL)
text = re.sub(r'function toggleSlip\(id\) \{.*?\n      \}', '', text, flags=re.DOTALL)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("More MLB code stripped")
