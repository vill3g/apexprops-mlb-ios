
import re

with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the location right before GROUP: AI Strategy
target = "            <!-- GROUP: AI Strategy & Signal Controls -->"
updates_html = """            <!-- GROUP: App Updates -->
            <div>
                <button onclick="openUpdateModal(); closeSettings();" class="w-full p-3.5 bg-cyan-900/30 hover:bg-cyan-900/50 text-cyan-300 border border-cyan-500/30 rounded-2xl text-xs font-bold tracking-wide transition-colors flex items-center justify-center gap-2 shadow-sm relative">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path></svg>
                    View Updates & Upgrades
                    <span id="settings-updates-dot" class="hidden absolute right-4 w-2.5 h-2.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)] animate-pulse"></span>
                </button>
            </div>
            
            <!-- GROUP: AI Strategy & Signal Controls -->"""
content = content.replace(target, updates_html)

# Also fix the JS to update settings-updates-dot
# Look for bellBtn...
js_target = """                const bellBtn = document.getElementById('settings-nav-btn');
                const bellDot = document.getElementById('updates-bell-dot');
                const bellPulse = document.getElementById('updates-bell-dot-pulse');"""
js_new = """                const bellBtn = document.getElementById('settings-nav-btn');
                const bellDot = document.getElementById('updates-bell-dot');
                const bellPulse = document.getElementById('updates-bell-dot-pulse');
                const settingsBtnDot = document.getElementById('settings-updates-dot');"""
content = content.replace(js_target, js_new)

js_target_2 = """                    if (bellDot) bellDot.classList.remove('hidden');
                    if (bellPulse) bellPulse.classList.remove('hidden');"""
js_new_2 = """                    if (bellDot) bellDot.classList.remove('hidden');
                    if (bellPulse) bellPulse.classList.remove('hidden');
                    if (settingsBtnDot) settingsBtnDot.classList.remove('hidden');"""
content = content.replace(js_target_2, js_new_2)

js_target_3 = """            if (bellDot) bellDot.classList.add('hidden');
            if (bellPulse) bellPulse.classList.add('hidden');"""
js_new_3 = """            if (bellDot) bellDot.classList.add('hidden');
            if (bellPulse) bellPulse.classList.add('hidden');
            const settingsBtnDot = document.getElementById('settings-updates-dot');
            if (settingsBtnDot) settingsBtnDot.classList.add('hidden');"""
content = content.replace(js_target_3, js_new_3)


with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

