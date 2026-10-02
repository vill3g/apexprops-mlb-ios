
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

inject_html = """
            <!-- GROUP: Push Notifications -->
            <div>
                <div class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-1 mb-2 flex items-center justify-between">
                    <span class="flex items-center gap-1.5">?? Push Notifications</span>
                </div>
                <div class="bg-[#131b2c] border border-white/[0.08] rounded-2xl shadow-sm overflow-hidden divide-y divide-white/[0.05]">
                    
                    <!-- Row: iOS Overlay Toggle -->
                    <div class="p-3.5 flex items-center justify-between gap-3 hover:bg-white/[0.02] transition-colors">
                        <div class="flex items-start gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0 text-sm font-bold mt-0.5">
                                ??
                            </div>
                            <div class="flex flex-col">
                                <span class="text-xs font-semibold text-white tracking-tight">iOS-Style Overlays</span>
                                <span class="text-[10px] text-gray-400 leading-snug mt-0.5">Show animated pill notifications at the top of the screen when a trade wins or settles.</span>
                            </div>
                        </div>
                        <label class="relative inline-flex items-center cursor-pointer shrink-0">
                            <input type="checkbox" id="ios-notify-toggle" class="sr-only peer" checked onchange="window.enableIosNotifications = this.checked;">
                            <div class="w-11 h-6 bg-gray-700/80 rounded-full peer peer-checked:after:translate-x-5 peer-checked:after:border-white after:content-[\x27\x27] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all after:shadow-sm peer-checked:bg-[#34c759]"></div>
                        </label>
                    </div>

                </div>
            </div>

            <!-- GROUP: AI Strategy & Signal Controls -->
"""

content = content.replace("<!-- GROUP: AI Strategy & Signal Controls -->", inject_html)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

