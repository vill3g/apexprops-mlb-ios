import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the HTML for sports events
old_event_html = '''
                  container.innerHTML = '';
                  data.events.forEach(evt => {
                      const el = document.createElement('div');
                      el.className = 'bg-black/40 border border-white/5 rounded-xl p-4 flex flex-col gap-2 hover:border-cyan-500/30 transition-colors';
                      el.innerHTML = 
                          <div class="flex justify-between items-center">
                              <span class="text-xs font-black text-gray-400 bg-gray-800 px-2 py-0.5 rounded"></span>
                              <span class="text-xs font-mono text-cyan-400">AI Edge: %</span>
                          </div>
                          <div class="text-sm font-bold text-white mt-1"></div>
                          <div class="text-xs text-gray-400">Prediction: <span class="text-emerald-400 font-bold"></span></div>
                          <div class="flex justify-between items-center mt-2 pt-2 border-t border-white/5">
                              <div class="flex flex-col">
                                  <span class="text-[9px] text-gray-500 uppercase">Confidence</span>
                                  <span class="text-xs font-mono font-bold text-white">%</span>
                              </div>
                              <div class="flex flex-col text-right">
                                  <span class="text-[9px] text-gray-500 uppercase">Implied Odds</span>
                                  <span class="text-xs font-mono font-bold text-gray-300">%</span>
                              </div>
                          </div>
                      ;
                      container.appendChild(el);
                  });
'''

new_event_html = '''
                  container.innerHTML = '';
                  data.events.forEach(evt => {
                      const el = document.createElement('div');
                      el.className = 'bg-black/40 border border-white/5 rounded-lg p-3 flex flex-col gap-1 hover:border-cyan-500/30 transition-colors';
                      let opponentText = evt.opponent ? evt.opponent : 'Unknown Matchup';
                      let edgeVal = parseFloat(evt.edge_pct) || 0;
                      let confVal = parseFloat(evt.confidence_pct) || 0;
                      
                      el.innerHTML = 
                          <div class="flex justify-between items-center mb-1">
                              <span class="text-[10px] font-black text-gray-400 bg-gray-800 px-1.5 py-0.5 rounded"> | </span>
                              <span class="text-[10px] font-mono ">Edge: %</span>
                          </div>
                          <div class="flex justify-between items-end">
                              <div class="flex flex-col">
                                  <div class="text-xs text-gray-400 truncate max-w-[140px]">vs </div>
                                  <div class="text-sm font-bold text-emerald-400 truncate max-w-[140px]"></div>
                              </div>
                              <div class="flex flex-col text-right">
                                  <span class="text-[9px] text-gray-500 uppercase">Conf</span>
                                  <span class="text-xs font-mono font-bold text-white">%</span>
                              </div>
                          </div>
                      ;
                      container.appendChild(el);
                  });
'''

html = html.replace(old_event_html.strip(), new_event_html.strip())

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
