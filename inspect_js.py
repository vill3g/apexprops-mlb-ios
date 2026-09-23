import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Find the main JS block (block 4)
all_scripts = [(m.start(), m.end()) for m in re.finditer(r'<script(?:[^>]*)>.*?</script>', c, re.DOTALL)]
start4, end4 = all_scripts[3]
main_js = c[start4:end4]

# Print the first 3000 characters 
print(main_js[len("<script>"):len("<script>")+3000])
