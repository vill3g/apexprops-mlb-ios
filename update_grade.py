import re
js_path = "static/js/dashboard.js"
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

# 1. Update gradeBubble text to have "GRADE " prefix
pattern1 = r"(gradeBubble\.innerText = gradeStr;)"
replace1 = r"gradeBubble.innerText = gradeStr === 'PASS' ? 'PASS' : 'GRADE ' + gradeStr;"
js = re.sub(pattern1, replace1, js)

# 2. Remove bubbleEl (ml-status-bubble) code logic
# We can just null it out or remove it entirely from HTML. If we remove from HTML, bubbleEl will be null.
# So we don't strictly *need* to remove the JS, but let's just leave it (it checks `if (bubbleEl)`).

with open(js_path, "w", encoding="utf-8") as f:
    f.write(js)
print("Updated dashboard.js for GRADE prefix")
