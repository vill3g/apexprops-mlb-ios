with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = r'''
        <!-- Live Open Trades P/L Display - Extended vertically to fill height -->
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
        </div>
'''

import re
text = re.sub(r'        <!-- Live Open Trades P/L Display - Extended vertically to fill height -->.*?<span id="topBarLivePnlText".*?</div>', replacement, text, flags=re.DOTALL)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Injected Account Balance and Spinning Bitcoin!")
