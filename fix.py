import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    "let assetType = String(t.asset || '').toUpperCase();",
    "let assetType = String(t.asset || '').toUpperCase();\n                                          if (__isSportTrade(t)) assetType = 'SPORTS';"
)

c = c.replace(
    "else if (assetType === 'DOGE') { assetBadgeClass = 'bg-orange-500/20 text-orange-300 border-orange-500/40'; assetIcon = 'Y?  '; }",
    "else if (assetType === 'DOGE') { assetBadgeClass = 'bg-orange-500/20 text-orange-300 border-orange-500/40'; assetIcon = 'Y?  '; }\n                                              else if (assetType === 'SPORTS') { assetBadgeClass = 'bg-blue-500/20 text-blue-300 border-blue-500/40'; assetIcon = 'Y?^ '; }"
)

row1_old = '''                                      <div class="flex justify-between items-center px-3 pt-2.5 pb-1.5">
                                          <div class="flex items-center gap-2">
                                              <span class="text-[13px] font-black tracking-wider "></span>
                                              
                                              <span class="text-[11px] font-bold text-gray-400">Strike <span class="text-white"></span></span>
                                              
                                          </div>'''

row1_new = '''                                      <div class="flex justify-between items-center px-3 pt-2.5 pb-1.5">
                                          <div class="flex items-center gap-2">
                                              <span class="text-[13px] font-black tracking-wider "></span>
                                              
                                              <span class="text-[11px] font-bold text-gray-400"> <span class="text-white"></span></span>
                                              
                                          </div>'''

c = c.replace(row1_old, row1_new)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(c)
print('Fixed HTML!')
