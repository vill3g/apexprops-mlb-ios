import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

header_pattern = r'(<header id=\"main-header\"[^>]*>)([\s\S]*?)(</header>)'
match = re.search(header_pattern, html)
if not match:
    print('Header not found')
    exit(1)

inner_html = match.group(2)

new_header_tag = '<header id=\"main-header\" class=\"fixed top-0 left-0 right-0 z-50 bg-black border-b border-white/10\" style=\"padding-top: calc(env(safe-area-inset-top, 0px));\">\n      <div class=\"px-3 py-2 flex justify-between items-end relative w-full\">'

# Let's fix the inner html wrappers
# We need to add z-10 to the left and right containers so they sit above the absolute center container if screens get small.
# Left container: <div class="flex items-center gap-2.5">
inner_html = inner_html.replace('<div class=\"flex items-center gap-2.5\">', '<div class=\"flex items-center gap-2.5 z-10\">')

# Right container: <div class="flex items-center gap-2">
inner_html = inner_html.replace('<div class=\"flex items-center gap-2\">', '<div class=\"flex items-center gap-2 z-10\">')

# Center container:
old_center = '''<div id=\"nav-live-pnl-container\" class=\"hidden flex-col items-center justify-center mx-auto transition-all duration-300\">'''
new_center = '''<div id=\"nav-live-pnl-container\" class=\"hidden absolute left-1/2 -translate-x-1/2 bottom-0 pb-1.5 z-0 flex-col items-center justify-end transition-all duration-300\">'''
inner_html = inner_html.replace(old_center, new_center)

new_header = new_header_tag + inner_html + '      </div>\n    </header>'

html = html[:match.start()] + new_header + html[match.end():]

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Updated header')
