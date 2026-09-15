import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add CSS
css_to_add = '''
    .signal-fade-in { animation: fadeIn 0.3s ease-in forwards; }
    .signal-fade-out { animation: fadeOut 0.3s ease-out forwards; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes fadeOut { from { opacity: 1; transform: translateY(0); } to { opacity: 0; transform: translateY(-3px); } }
</style>
'''
html = html.replace('</style>', css_to_add, 1)

# 2. Add HTML Panel
html_to_insert = '''
        <!-- 4. Live Signals Streamer -->
        <div id="topBarSignalsCard" class="sleek-glass-card hidden sm:flex flex-col justify-center flex-1 min-w-[140px] max-w-[280px] px-2 py-1.5 ml-1">
          <div class="flex items-center gap-1.5 w-full">
            <div class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse shadow-[0_0_5px_rgba(251,191,36,0.8)]"></div>
            <span class="text-[8px] sm:text-[9px] font-mono font-black uppercase text-amber-400 tracking-[0.05em]">LIVE SIGNALS</span>
          </div>
          <div class="mt-1 w-full overflow-hidden relative h-[14px] sm:h-[18px]">
            <div id="topBarSignalsText" class="absolute w-full whitespace-nowrap overflow-hidden text-ellipsis text-[9px] sm:text-[10px] lg:text-xs font-mono text-slate-300">
              Scanning market...
            </div>
          </div>
        </div>
      </div>
'''
html = html.replace('</div>\n\n      <!-- Action Controls & P/L -->', html_to_insert + '\n      <!-- Action Controls & P/L -->', 1)

# 3. Add JS Cycler
js_to_add = '''
    // --- Live Signals Cycler ---
    let currentSignalIndex = 0;
    let signalCyclerInterval = null;
    
    function startSignalCycler() {
      if (signalCyclerInterval) clearInterval(signalCyclerInterval);
      signalCyclerInterval = setInterval(() => {
        const textEl = document.getElementById('topBarSignalsText');
        if (!textEl) return;
        
        let factors = [];
        if (window.lockedContractForecast && window.lockedContractForecast.decision_factors) {
           factors = window.lockedContractForecast.decision_factors;
        } else if (window.cachedNextContractForecast && window.cachedNextContractForecast.catalysts) {
           factors = window.cachedNextContractForecast.catalysts;
        }
        
        if (!factors || factors.length === 0) {
           factors = ['Awaiting next prediction interval...', 'Monitoring real-time orderbook flow...'];
        }
        
        currentSignalIndex = (currentSignalIndex + 1) % factors.length;
        const nextText = factors[currentSignalIndex];
        
        textEl.classList.remove('signal-fade-in');
        textEl.classList.add('signal-fade-out');
        
        setTimeout(() => {
           textEl.innerText = nextText;
           textEl.classList.remove('signal-fade-out');
           textEl.classList.add('signal-fade-in');
        }, 300);
        
      }, 3500); // cycle every 3.5s
    }
    
    // Start it when UI loads
    setTimeout(startSignalCycler, 2000);
    // ---------------------------
    
    function initAccuracyTooltip() {
'''
html = html.replace('function initAccuracyTooltip() {', js_to_add, 1)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("UI Patched!")
