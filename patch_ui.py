
import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove updates bell btn and move dots to settings btn
bell_btn_block = """        <button id="updates-bell-btn" onclick="openUpdateModal()" class="relative w-8 h-8 flex items-center justify-center bg-gray-800 text-gray-300 hover:text-white rounded-lg active:scale-95 transition-all shadow-sm cursor-pointer" title="What's New & Upgrades">
            <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
            <span id="updates-bell-dot" class="hidden absolute top-1 right-1 w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></span>
            <span id="updates-bell-dot-pulse" class="hidden absolute top-1 right-1 w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
        </button>"""
content = content.replace(bell_btn_block, "")

settings_btn = """        <button onclick="openSettings()" class="w-8 h-8 flex items-center justify-center bg-gray-800 text-gray-300 hover:text-white rounded-lg active:scale-95 transition-all shadow-sm cursor-pointer" title="Settings">"""
settings_btn_new = """        <button onclick="openSettings()" id="settings-nav-btn" class="relative w-8 h-8 flex items-center justify-center bg-gray-800 text-gray-300 hover:text-white rounded-lg active:scale-95 transition-all shadow-sm cursor-pointer" title="Settings">
            <span id="updates-bell-dot" class="hidden absolute top-0 right-0 w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)] z-10"></span>
            <span id="updates-bell-dot-pulse" class="hidden absolute top-0 right-0 w-2 h-2 rounded-full bg-cyan-400 animate-ping z-10"></span>"""
content = content.replace(settings_btn, settings_btn_new)

# 2. Add the View Updates & Upgrades button inside settings drawer
acc_sec = """            <!-- GROUP: Account & Security -->"""
updates_btn_block = """            <!-- GROUP: Updates -->
            <div>
                <button onclick="openUpdateModal(); closeSettings();" class="w-full p-3.5 bg-cyan-900/30 hover:bg-cyan-900/50 text-cyan-300 border border-cyan-500/30 rounded-2xl text-xs font-bold tracking-wide transition-colors flex items-center justify-center gap-2 shadow-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                    View Updates & Upgrades
                </button>
            </div>
            
            <!-- GROUP: Account & Security -->"""
content = content.replace(acc_sec, updates_btn_block)

# 3. Fix Push Notifications UI
push_old = """            <!-- GROUP: Push Notifications -->
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
                        </div>"""
push_new = """            <!-- GROUP: Push Notifications -->
            <div>
                <div class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider px-1 mb-2 flex items-center justify-between">
                    <span class="flex items-center gap-1.5">
                        <svg class="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                        Push Notifications
                    </span>
                </div>
                <div class="bg-[#131b2c] border border-white/[0.08] rounded-2xl shadow-sm overflow-hidden divide-y divide-white/[0.05]">
                    
                    <!-- Row: iOS Overlay Toggle -->
                    <div class="p-3.5 flex items-center justify-between gap-3 hover:bg-white/[0.02] transition-colors">
                        <div class="flex items-start gap-2.5 min-w-0">
                            <div class="w-7 h-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                            </div>
                            <div class="flex flex-col">
                                <span class="text-xs font-semibold text-white tracking-tight">Native Push Alerts</span>
                                <span class="text-[10px] text-gray-400 leading-snug mt-0.5">Receive lockscreen alerts when a trade wins or settles.</span>
                            </div>
                        </div>"""
content = content.replace(push_old, push_new)

# 4. JS Fix
content = content.replace("const bellBtn = document.getElementById('updates-bell-btn');", "const bellBtn = document.getElementById('settings-nav-btn');")

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

