import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# I will extract the sports-event-list div
pattern = re.compile(r'(\s*<div id="sports-event-list".*?<!-- Events populated here -->\s*</div>\s*</div>)', re.DOTALL)
match = pattern.search(html)

if match:
    sports_list = match.group(1)
    html = html.replace(sports_list, '') # remove it from where it is
    
    # insert it right after <div id="lw-chart-container" class="absolute inset-0"></div>
    target = '<div id="lw-chart-container" class="absolute inset-0"></div>'
    html = html.replace(target, target + sports_list)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed layout structure')
