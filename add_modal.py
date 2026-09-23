# -*- coding: utf-8 -*-
import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add onclick to Trading Style label
old_label = '''<label class="text-[11px] font-bold text-gray-200 uppercase tracking-widest">Trading Style</label>'''
new_label = '''<label onclick="document.getElementById('styleModal').classList.remove('hidden')" class="text-[11px] font-bold text-kalshi-blue uppercase tracking-widest flex items-center gap-1 cursor-pointer hover:text-white transition-colors">Trading Style <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg></label>'''

if old_label in html:
    html = html.replace(old_label, new_label)
else:
    # Try more generic regex
    html = re.sub(
        r'<label class="text-\[11px\] font-bold text-gray-200 uppercase tracking-widest">Trading Style</label>',
        new_label,
        html
    )

# 2. Add the Modal HTML at the end of body
modal_html = '''
    <!-- Trading Style Explainer Modal -->
    <div id="styleModal" class="hidden fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
        <div class="bg-gradient-to-b from-[#1a233a] to-[#131b2c] border border-kalshi-border rounded-2xl p-5 shadow-2xl max-w-sm w-full relative">
            <button onclick="document.getElementById('styleModal').classList.add('hidden')" class="absolute top-4 right-4 text-gray-500 hover:text-white">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
            <h3 class="text-xs font-black text-white uppercase tracking-widest mb-4 border-b border-white/10 pb-2">Trading Styles</h3>
            
            <div class="space-y-4 text-xs">
                <div>
                    <div class="font-bold text-kalshi-blue uppercase mb-1">?? AUTO</div>
                    <div class="text-gray-400">Dynamically switches between strategies based on real-time market conditions. Best for hands-off trading.</div>
                </div>
                <div>
                    <div class="font-bold text-emerald-400 uppercase mb-1">?? SNIPER</div>
                    <div class="text-gray-400">Waits for high-conviction, high-probability setups. Trades less frequently but aims for a higher win rate.</div>
                </div>
                <div>
                    <div class="font-bold text-fuchsia-400 uppercase mb-1">?? MOMENTUM SURFER</div>
                    <div class="text-gray-400">Jumps on strong directional trends. Executes rapidly during high volatility.</div>
                </div>
                <div>
                    <div class="font-bold text-amber-500 uppercase mb-1">?? AMBUSH</div>
                    <div class="text-gray-400">Plays fading setups and reversals. Triggers when price action hits extreme exhaustion levels.</div>
                </div>
                <div>
                    <div class="font-bold text-purple-400 uppercase mb-1">?? CHOP</div>
                    <div class="text-gray-400">Optimized for low-volatility, sideways markets. Executes mean-reversion trades within tight ranges.</div>
                </div>
            </div>
            
            <button onclick="document.getElementById('styleModal').classList.add('hidden')" class="w-full mt-6 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[10px] font-bold text-white uppercase tracking-wider transition-colors">Got it</button>
        </div>
    </div>
</body>
'''

if 'id="styleModal"' not in html:
    html = html.replace('</body>', modal_html)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)
