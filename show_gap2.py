with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

part1 = '        <div id="topBarLivePnlContainer" class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight">'
part2 = '          <span class="text-[7px] sm:text-[8px] font-mono font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">Open P/L</span>'
part3 = '          <span id="topBarLivePnlText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-slate-300">.00</span>'
part4 = '        </div>'

target = f"{part1}\n{part2}\n{part3}\n{part4}"

start = text.find(part1)
actual = text[start:start+len(target)]

print(repr(target))
print(repr(actual))
print(target == actual)
