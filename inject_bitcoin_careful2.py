with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

replacement_html = r'''        <!-- Live Open Trades P/L Display - Extended vertically to fill height -->
        <div id="topBarLivePnlContainer" class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight">
          <span class="text-[7px] sm:text-[8px] font-mono font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">Open P/L</span>
          <span id="topBarLivePnlText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-slate-300">.00</span>
        </div>

        <!-- Account Balance & Spinning Bitcoin -->
        <div class="sleek-glass-card flex flex-col items-end justify-center px-2.5 py-1 sm:px-3 sm:py-1.5 self-stretch shrink-0 min-w-[84px] leading-tight" title="Account Balance">
          <div class="flex items-center gap-1.5">
             <span class="inline-block animate-spin text-amber-400 text-xs sm:text-sm font-black">&#x20BF;</span>
             <span class="text-[7px] sm:text-[8px] font-mono font-bold uppercase tracking-wider text-slate-400 whitespace-nowrap">Balance</span>
          </div>
          <span id="topBarAccountBalanceText" class="text-xs sm:text-sm lg:text-base font-black font-mono whitespace-nowrap text-emerald-400">$--.--</span>
        </div>'''

import re
# We will use exactly 4 lines to ensure no greedy matching across the whole file
text = re.sub(r'        <!-- Live Open Trades P/L Display - Extended vertically to fill height -->\s*<div id="topBarLivePnlContainer"[^\n]*\s*<span[^\n]*Open P/L</span>\s*<span id="topBarLivePnlText"[^\n]*\\.00</span>\s*</div>', replacement_html, text)

replacement_js = r'''        const tradeLogBalEl = document.getElementById("tradeLogPaperBalance");
        const topBarBalEl = document.getElementById("topBarAccountBalanceText");
        if (data.balance_dollars !== undefined) {
          const formatted = "$" + parseFloat(data.balance_dollars).toFixed(2);
          if (balEl) balEl.innerText = formatted;
          if (settingsBalEl) settingsBalEl.innerText = formatted;
          if (tradeLogBalEl) tradeLogBalEl.innerText = formatted;
          if (topBarBalEl) topBarBalEl.innerText = formatted;
        }'''

text = re.sub(r'        const tradeLogBalEl = document\.getElementById\("tradeLogPaperBalance"\);\s*if \(data\.balance_dollars !== undefined\) \{\s*const formatted = \$\$\{parseFloat\(data\.balance_dollars\)\.toFixed\(2\)\};\s*if \(balEl\) balEl\.innerText = formatted;\s*if \(settingsBalEl\) settingsBalEl\.innerText = formatted;\s*if \(tradeLogBalEl\) tradeLogBalEl\.innerText = formatted;\s*\}', replacement_js, text)


with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
