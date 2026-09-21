with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

part1 = '        <div id="topBarLivePnlContainer" class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight">'
part2 = '          <span class="text-[7px] sm:text-[8px] font-mono font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">Open P/L</span>'
part3 = '          <span id="topBarLivePnlText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-slate-300">.00</span>'
part4 = '        </div>'

target = f"{part1}\n{part2}\n{part3}\n{part4}"

replacement = target + '''\n
        <!-- Account Balance & Spinning Bitcoin -->
        <div class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight" title="Account Balance">
          <div class="flex items-center gap-1.5">
             <span class="inline-block animate-spin text-amber-400 text-xs sm:text-sm font-black">&#x20BF;</span>
             <span class="text-[7px] sm:text-[8px] font-mono font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">Balance</span>
          </div>
          <span id="topBarAccountBalanceText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-emerald-400">$--.--</span>
        </div>'''

text = text.replace(target, replacement)

js_target = '''        const tradeLogBalEl = document.getElementById("tradeLogPaperBalance");
        if (data.balance_dollars !== undefined) {
          const formatted = $;
          if (balEl) balEl.innerText = formatted;
          if (settingsBalEl) settingsBalEl.innerText = formatted;
          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;
        }'''

js_replacement = '''        const tradeLogBalEl = document.getElementById("tradeLogPaperBalance");
        const topBarBalEl = document.getElementById("topBarAccountBalanceText");
        if (data.balance_dollars !== undefined) {
          const formatted = "$" + parseFloat(data.balance_dollars).toFixed(2);
          if (balEl) balEl.innerText = formatted;
          if (settingsBalEl) settingsBalEl.innerText = formatted;
          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;
          if (topBarBalEl) topBarBalEl.innerText = formatted;
        }'''

text = text.replace(js_target, js_replacement)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
