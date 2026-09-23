import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the old buttons from AI panel
old_ai_buttons = '''            <div class="pl-2 mb-2 flex gap-2">
                <button onclick="placeManualTrade('BUY')" class="flex-1 py-3 bg-green-500/20 border border-green-500/50 text-green-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 shadow-[0_0_15px_rgba(34,197,94,0.15)]">BUY YES</button>
                <button onclick="placeManualTrade('SELL')" class="flex-1 py-3 bg-red-500/20 border border-red-500/50 text-red-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 shadow-[0_0_15px_rgba(239,68,68,0.15)]">BUY NO</button>
            </div>
            <div class="pl-2">
                <button onclick="forceMLTrade()" class="w-full py-3.5 bg-purple-600/20 border border-purple-500/50 text-purple-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 active:bg-purple-600/40 shadow-[0_0_15px_rgba(168,85,247,0.15)]">Force AI Signal Now</button>
            </div>'''
            
# Also remove the `mb-4` from popup-summary if the buttons are gone so the padding looks right
old_summary = '''<div id="popup-summary" class="text-[10px] text-gray-400 leading-relaxed mb-4 text-center pl-2 italic">Awaiting AI signal computation...</div>'''
new_summary = '''<div id="popup-summary" class="text-[10px] text-gray-400 leading-relaxed text-center pl-2 italic">Awaiting AI signal computation...</div>'''

content = content.replace(old_summary, new_summary)
content = content.replace(old_ai_buttons, '')

# 2. Add Force AI button above Close All Trades
old_close = '''            <div class="px-4 pb-5">
                <button onclick="closeAllTrades()" class="w-full py-3 bg-red-600/20 border border-red-500/50 text-red-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 active:bg-red-600/40 shadow-[0_0_15px_rgba(239,68,68,0.15)]">CLOSE ALL TRADES</button>
            </div>'''

new_close = '''            <div class="px-4 pb-5 flex flex-col gap-3">
                <button onclick="forceMLTrade()" class="w-full py-3 border border-purple-500/50 text-purple-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 bg-purple-600/20 active:bg-purple-600/40 shadow-[0_0_15px_rgba(168,85,247,0.15)]">FORCE AI SIGNAL NOW</button>
                <button onclick="closeAllTrades()" class="w-full py-3 bg-red-600/20 border border-red-500/50 text-red-400 font-bold text-xs uppercase tracking-widest rounded-xl transition-all active:scale-95 active:bg-red-600/40 shadow-[0_0_15px_rgba(239,68,68,0.15)]">CLOSE ALL TRADES</button>
            </div>'''

content = content.replace(old_close, new_close)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
