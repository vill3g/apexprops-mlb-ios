import re

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the old Signals HTML
old_html = r'''        <!-- 4. Live Signals Streamer -->
        <div id="topBarSignalsCard" class="sleek-glass-card hidden sm:flex flex-col justify-center flex-1 min-w-\[140px\] max-w-\[280px\] px-2 py-1.5 ml-1">
          <div class="flex items-center gap-1.5 w-full">
            <div class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse shadow-\[0_0_5px_rgba\(251,191,36,0.8\)\]"></div>
            <span class="text-\[8px\] sm:text-\[9px\] font-mono font-black uppercase text-amber-400 tracking-\[0.05em\]">LIVE SIGNALS</span>
          </div>
          <div class="mt-1 w-full overflow-hidden relative h-\[14px\] sm:h-\[18px\]">
            <div id="topBarSignalsText" class="absolute w-full whitespace-nowrap overflow-hidden text-ellipsis text-\[9px\] sm:text-\[10px\] lg:text-xs font-mono text-slate-300">
              Scanning market...
            </div>
          </div>
        </div>'''

new_html = '''        <!-- 4. Live Signals Streamer -->
        <div id="topBarSignalsCard" class="sleek-glass-card hidden sm:flex flex-col flex-1 min-w-[200px] max-w-[340px] px-2 py-1 ml-1 overflow-hidden h-[44px]">
          <div class="flex items-center gap-1.5 w-full mb-0.5 shrink-0">
            <div class="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse shadow-[0_0_5px_rgba(251,191,36,0.8)]"></div>
            <span class="text-[7px] sm:text-[8px] font-mono font-black uppercase text-amber-400 tracking-[0.05em]">LIVE SIGNALS</span>
          </div>
          <div class="w-full flex-1 overflow-hidden relative" style="mask-image: linear-gradient(to bottom, black 60%, transparent 100%); -webkit-mask-image: linear-gradient(to bottom, black 60%, transparent 100%);">
            <div id="topBarSignalsContainer" class="absolute w-full flex flex-col transition-transform duration-700 ease-in-out text-[8.5px] sm:text-[9px] font-mono text-slate-300 leading-tight">
              <!-- JS fills this -->
            </div>
          </div>
        </div>'''

html = re.sub(old_html, new_html, html, flags=re.MULTILINE)

# Replace the old JS cycler
old_js = r'''    // --- Live Signals Cycler ---[\s\S]*?    // ---------------------------'''

new_js = '''    // --- Live Signals Scroller ---
    let signalIndex = 0;
    let signalInterval = null;
    let currentSignalLines = [];
    
    function startSignalCycler() {
      if (signalInterval) clearInterval(signalInterval);
      
      const container = document.getElementById('topBarSignalsContainer');
      if (!container) return;
      
      signalInterval = setInterval(() => {
        let factors = [];
        if (window.lockedContractForecast && window.lockedContractForecast.decision_factors) {
           factors = window.lockedContractForecast.decision_factors;
        } else if (window.cachedNextContractForecast && window.cachedNextContractForecast.catalysts) {
           factors = window.cachedNextContractForecast.catalysts;
        }
        
        if (!factors || factors.length === 0) {
           factors = ['Awaiting next prediction interval...', 'Monitoring real-time orderbook flow...'];
        }
        
        const nextText = factors[signalIndex % factors.length];
        signalIndex++;
        
        // Add new line
        const line = document.createElement('div');
        line.className = 'whitespace-nowrap overflow-hidden text-ellipsis';
        line.innerHTML = <span class="text-cyan-500 mr-1">></span>;
        container.appendChild(line);
        currentSignalLines.push(line);
        
        // Max 3 lines visible, scroll up
        if (currentSignalLines.length > 3) {
            const rowHeight = line.offsetHeight || 12;
            const scrollAmount = (currentSignalLines.length - 3) * rowHeight;
            container.style.transform = 	ranslateY(-px);
            
            // Clean up old invisible lines after animation
            setTimeout(() => {
                while(currentSignalLines.length > 3) {
                    const oldLine = currentSignalLines.shift();
                    oldLine.remove();
                }
                // Reset transform instantly after DOM removal so it doesn't jump
                container.style.transition = 'none';
                container.style.transform = 	ranslateY(0);
                // Force reflow
                void container.offsetHeight;
                container.style.transition = 'transform 700ms ease-in-out';
            }, 700);
        }
      }, 2500); // push new line every 2.5s
    }
    
    setTimeout(startSignalCycler, 2000);
    // ---------------------------'''

html = re.sub(old_js, new_js, html, flags=re.MULTILINE)

with open('static/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("UI Patched successfully with scrolling signals!")
