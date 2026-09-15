import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_html = r'''        <!-- 4. Live Signals Streamer -->
        <div id="topBarSignalsCard" class="sleek-glass-card hidden sm:flex flex-col flex-1 min-w-\[200px\] max-w-\[340px\] px-2 py-1.5 ml-1 overflow-hidden self-stretch">
          <div class="flex items-center gap-1.5 w-full mb-0.5 shrink-0">
            <div class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse shadow-\[0_0_5px_rgba\(251,191,36,0.8\)\]"></div>
            <span class="text-\[7px\] sm:text-\[8px\] font-mono font-black uppercase text-amber-400 tracking-\[0.05em\]">LIVE SIGNALS</span>
          </div>
          <div class="w-full flex-1 overflow-hidden relative" style="mask-image: linear-gradient\(to bottom, black 60%, transparent 100%\); -webkit-mask-image: linear-gradient\(to bottom, black 60%, transparent 100%\);">
            <div id="topBarSignalsContainer" class="absolute w-full flex flex-col transition-transform duration-700 ease-in-out text-\[8.5px\] sm:text-\[9px\] font-mono text-slate-300 leading-tight">
              <!-- JS fills this -->
            </div>
          </div>
        </div>'''

new_html = '''        <!-- 4. Live Signals Streamer -->
        <div id="topBarSignalsCard" class="sleek-glass-card hidden sm:flex flex-row items-center flex-1 min-w-[200px] max-w-[400px] px-2 py-1 ml-1 overflow-hidden self-stretch gap-2">
          <div class="w-2 h-2 bg-amber-400 rounded-full animate-pulse shadow-[0_0_6px_rgba(251,191,36,0.9)] shrink-0"></div>
          <div class="w-full flex-1 h-full overflow-hidden relative" style="mask-image: linear-gradient(to bottom, black 70%, transparent 100%); -webkit-mask-image: linear-gradient(to bottom, black 70%, transparent 100%);">
            <div id="topBarSignalsContainer" class="absolute w-full flex flex-col transition-transform duration-700 ease-in-out text-[10px] sm:text-[11px] lg:text-[12px] font-mono text-slate-200 leading-snug">
              <!-- JS fills this -->
            </div>
          </div>
        </div>'''

html = re.sub(old_html, new_html, html, flags=re.MULTILINE)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("UI Patched successfully with larger text!")
