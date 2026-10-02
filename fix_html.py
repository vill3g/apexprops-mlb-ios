import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    code = f.read()

prediction_block = '''                <div class="p-2 rounded-xl bg-black/30 border border-white/5">
                    <div class="font-bold text-purple-400 uppercase mb-1 flex items-center gap-1.5">
                        <span>??</span> PREDICTION
                    </div>
                    <div class="text-gray-300 text-[11px] leading-relaxed">Trades exactly at the contract open. Forces a trade based on the highest probability direction without being blocked by negative EV or chop filters.</div>
                </div>
'''

new_code = code.replace('                <div class="p-2 rounded-xl bg-black/30 border border-white/5">\n                    <div class="font-bold text-fuchsia-400 uppercase mb-1 flex items-center gap-1.5">',
prediction_block + '                <div class="p-2 rounded-xl bg-black/30 border border-white/5">\n                    <div class="font-bold text-fuchsia-400 uppercase mb-1 flex items-center gap-1.5">')

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(new_code)
