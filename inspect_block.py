import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

# Find what's in the tailwind config script block - it may have leaked JS into it
idx_start = c.find("<script>\n    tailwind.config")
idx_end = c.find("</script>", idx_start)
block = c[idx_start:idx_end+9]
print("Block length:", len(block))
print("Block content:")
print(block)
