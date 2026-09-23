import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

old_html = """<div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Percent of balance per trade</div>
                </div>
                <input type="number" id="trade-size-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>"""
            
# Or if it doesn't have the border-b class:
old_html2 = """<div class="flex justify-between items-center">
                <div>
                    <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size (%)</label>
                    <div class="text-[9px] text-gray-500 uppercase">Percent of balance per trade</div>
                </div>
                <input type="number" id="trade-size-pct" class="w-16 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="100">
            </div>"""

new_html = """<div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                  <div>
                      <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">AI Copy Size ($)</label>
                      <div class="text-[9px] text-gray-500 uppercase">Dollar amount per trade</div>
                  </div>
                  <input type="number" id="trade-size-dollars" class="w-20 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-xs text-white font-bold text-center focus:outline-none" min="1" max="10000">
              </div>
              <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                  <div>
                      <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">Trading Style</label>
                      <div class="text-[9px] text-gray-500 uppercase">AI execution strategy</div>
                  </div>
                  <select id="trading-style" class="w-28 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-[10px] text-white font-bold focus:outline-none">
                      <option value="AUTO">Auto</option>
                      <option value="SNIPER">Sniper</option>
                      <option value="MOMENTUM_SURFER">Momentum</option>
                      <option value="CHOP">Chop</option>
                  </select>
              </div>
              <div class="flex justify-between items-center border-b border-kalshi-border pb-3">
                  <div>
                      <label class="text-xs font-bold text-gray-300 uppercase tracking-widest">Signal Source</label>
                      <div class="text-[9px] text-gray-500 uppercase">Primary prediction engine</div>
                  </div>
                  <select id="signal-source" class="w-28 bg-[#131b2c] border border-kalshi-border rounded py-1 px-2 text-[10px] text-white font-bold focus:outline-none">
                      <option value="ML_ENSEMBLE">GodTier ML</option>
                      <option value="TECHNICAL_ONLY">Technical Only</option>
                  </select>
              </div>"""

# I will use a regex to replace it because whitespace might be messing it up.
c = re.sub(
    r'<div class="flex justify-between items-center.*?AI Copy Size \(%\).*?</label>.*?</div>\s*<input type="number" id="trade-size-pct".*?>\s*</div>',
    new_html,
    c, flags=re.DOTALL
)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
