import re

filepath = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\static\saas_dashboard.html"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

one_click_html = """                    <!-- Row: 1-Click Trading -->
                    <div class="p-3.5 flex items-center justify-between gap-3 hover:bg-white/[0.02] transition-colors border-b border-white/5">
                        <div class="flex items-start gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 text-xs font-bold mt-0.5">
                                ⚡
                            </div>
                            <div class="flex flex-col">
                                <span class="text-xs font-semibold text-white tracking-tight">1-Click Trade Execution</span>
                                <span class="text-[10px] text-gray-400 leading-snug mt-0.5">Bypass manual confirmation popups when clicking Execute YES / NO manually.</span>
                            </div>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer shrink-0">
                            <input type="checkbox" id="one-click-toggle" class="sr-only peer" onchange="saveUserConfig()">
                            <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all after:shadow-sm peer-checked:bg-emerald-500"></div>
                        </label>
                    </div>

"""

pattern = r"(<!-- Row: Force Trade on PASS -->)"
if 'id="one-click-toggle"' not in content:
    content = re.sub(pattern, one_click_html + r"\1", content)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added one-click-toggle to HTML.")
else:
    print("Already exists.")
