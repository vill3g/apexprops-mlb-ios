import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS
if 'body.universe-sports .finance-only-setting' not in content:
    content = content.replace('</style>\n</head>', '''    body.universe-sports .finance-only-setting { display: none !important; }
</style>
</head>''')

# 2. Add JS classList toggle
if "document.body.classList.toggle('universe-sports'" not in content:
    old_js = "window.selectUniverse = function(universe) {\n            window.currentUniverse = universe;"
    new_js = "window.selectUniverse = function(universe) {\n            window.currentUniverse = universe;\n            document.body.classList.toggle('universe-sports', universe === 'SPORTS');"
    content = content.replace(old_js, new_js)

# 3. Add class to groups
def inject_class(group_comment_substring):
    global content
    idx = content.find(group_comment_substring)
    if idx == -1:
        print(f"Group not found: {group_comment_substring}")
        return
    
    div_idx = content.find('<div>', idx)
    if div_idx != -1 and div_idx < idx + 200:
        content = content[:div_idx] + '<div class="finance-only-setting">' + content[div_idx+5:]
        print(f"Replaced <div> for {group_comment_substring}")
    else:
        print(f"Could not find <div> for {group_comment_substring}")

inject_class('<!-- GROUP: AI Strategy & Signal Controls -->')
inject_class('<!-- GROUP 3: UI & Chart Preferences -->')
inject_class('<!-- GROUP 4: Advanced Machine Learning')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
