import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the JS logic
old_js = '''                // Fetch Countdown
                fetch('/api/engine/btc/countdown').then(r => r.json()).then(cData => {
                    if(cData.minutes_remaining !== undefined) {
                        const mins = Math.floor(cData.minutes_remaining);
                        const secs = Math.floor((cData.minutes_remaining - mins) * 60);
                        document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                    } else {
                        document.getElementById('kalshi-time').innerText = "--:--";
                    }
                }).catch(e=>{});'''

new_js = '''                // Fetch Countdown
                fetch('/api/engine/btc/countdown').then(r => r.json()).then(cData => {
                    if(cData.formatted) {
                        document.getElementById('kalshi-time').innerText = cData.formatted;
                    } else if(cData.minutes_remaining !== undefined) {
                        const mins = Math.floor(cData.minutes_remaining);
                        const secs = Math.floor((cData.minutes_remaining - mins) * 60);
                        document.getElementById('kalshi-time').innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
                    } else {
                        document.getElementById('kalshi-time').innerText = "--:--";
                    }
                }).catch(e=>{});'''

content = content.replace(old_js, new_js)

# 2. Make the text bigger
old_html = '''<span id="kalshi-time" class="text-[10px] font-black uppercase tabular-nums">--:--</span>'''
new_html = '''<span id="kalshi-time" class="text-sm font-black uppercase tabular-nums">--:--</span>'''

content = content.replace(old_html, new_html)

with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
