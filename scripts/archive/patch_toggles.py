import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Patch one-click-toggle
old_one_click = '''<input type="checkbox" id="one-click-toggle" class="sr-only peer" onchange="document.getElementById('one-click-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('one-click-text').className = this.checked ? 'text-[9px] font-bold text-kalshi-blue uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';">'''
new_one_click = '''<input type="checkbox" id="one-click-toggle" class="sr-only peer" onchange="document.getElementById('one-click-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('one-click-text').className = this.checked ? 'text-[9px] font-bold text-kalshi-blue uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest'; saveUserConfig();">'''
content = content.replace(old_one_click, new_one_click)

# 2. Patch force-trade-toggle
old_force = '''<input type="checkbox" id="force-trade-toggle" class="sr-only peer" onchange="document.getElementById('force-trade-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('force-trade-text').className = this.checked ? 'text-[9px] font-bold text-purple-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest';">'''
new_force = '''<input type="checkbox" id="force-trade-toggle" class="sr-only peer" onchange="document.getElementById('force-trade-text').innerText = this.checked ? 'ON' : 'OFF'; document.getElementById('force-trade-text').className = this.checked ? 'text-[9px] font-bold text-purple-400 uppercase tracking-widest' : 'text-[9px] font-bold text-gray-500 uppercase tracking-widest'; saveUserConfig();">'''
content = content.replace(old_force, new_force)

# 3. Patch loadDashboard polling logic so it doesn't overwrite if user is focused on the toggle
old_load_one_click = '''                const oneClickEl = document.getElementById('one-click-toggle');
                if (oneClickEl && s.one_click_trade !== undefined) {
                    oneClickEl.checked = !!s.one_click_trade;'''
new_load_one_click = '''                const oneClickEl = document.getElementById('one-click-toggle');
                if (oneClickEl && s.one_click_trade !== undefined && document.activeElement.id !== 'one-click-toggle') {
                    oneClickEl.checked = !!s.one_click_trade;'''
content = content.replace(old_load_one_click, new_load_one_click)

old_load_force = '''                const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl && s.auto_force_trade !== undefined) {
                    forceEl.checked = !!s.auto_force_trade;'''
new_load_force = '''                const forceEl = document.getElementById('force-trade-toggle');
                if (forceEl && s.auto_force_trade !== undefined && document.activeElement.id !== 'force-trade-toggle') {
                    forceEl.checked = !!s.auto_force_trade;'''
content = content.replace(old_load_force, new_load_force)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
