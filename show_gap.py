with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

part1 = '        <div id="topBarLivePnlContainer" class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight">'

start = text.find(part1)
print(repr(text[start:start+400]))
