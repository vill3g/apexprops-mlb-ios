import sys
with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('<header class="sticky top-0 z-40 sleek-glass-header')
end = text.find('</header>', start)
if start != -1 and end != -1:
    sys.stdout.buffer.write(text[start:end+9].encode('utf-8'))
