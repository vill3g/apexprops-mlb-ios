import http.server, socketserver, threading, time, subprocess, os, shutil
from PIL import Image

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    base_html = f.read()

# Disable auth redirect and splash
base_html = base_html.replace('<div id="splash-screen"', '<div id="splash-screen" style="display:none !important;"')
base_html = base_html.replace("window.location.href = '/login.html';", "// disabled")
base_html = base_html.replace("window.location.href = '/login.html'", "// disabled")
base_html = base_html.replace('padding-top: calc(env(safe-area-inset-top, 0px) + 0.5rem);', 'padding-top: calc(54px + 0.5rem);')
base_html = base_html.replace('padding-top: calc(3.5rem + env(safe-area-inset-top, 0px));', 'padding-top: calc(3.5rem + 54px);')

# Also fill in BAL and PNL to match user screenshot ($695.59 and +$200.97)
base_html = base_html.replace('id="nav-balance" class="text-xs font-black text-white tabular-nums">$--.--<', 'id="nav-balance" class="text-xs font-black text-white tabular-nums">$695.59<')
base_html = base_html.replace('id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">$--.--<', 'id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">+$200.97<')
base_html = base_html.replace('AUTO OFF', 'AUTO ON')

# Variation 1: Inside header, bottom-2, text-2xl
v1 = base_html.replace(
    '<div id="nav-live-pnl-container" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden flex-col items-center justify-center">\n        <div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest leading-none mb-0.5">Live Trade PnL</div>\n        <div id="nav-live-pnl-val" class="text-3xl font-black tabular-nums leading-none tracking-tight">+$0.00</div>\n    </div>',
    '<div id="nav-live-pnl-container" class="absolute left-1/2 bottom-2 -translate-x-1/2 flex flex-col items-center justify-center pointer-events-none">\n        <div class="text-[8px] text-gray-400 font-bold uppercase tracking-wider leading-none mb-0.5">Open Trade PnL</div>\n        <div id="nav-live-pnl-val" class="text-xl font-black tabular-nums leading-none tracking-tight text-red-400">-$0.20</div>\n    </div>'
)

# Variation 2: Inside header, vertically centered in content row (between avatar top/bottom)
# Content row starts at calc(54px + 0.5rem) and ends at pb-2 (8px from bottom).
# Total content row height is ~44px. Centered in that row:
v2 = base_html.replace(
    '<div id="nav-live-pnl-container" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden flex-col items-center justify-center">\n        <div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest leading-none mb-0.5">Live Trade PnL</div>\n        <div id="nav-live-pnl-val" class="text-3xl font-black tabular-nums leading-none tracking-tight">+$0.00</div>\n    </div>',
    '<div id="nav-live-pnl-container" class="absolute left-1/2 bottom-2.5 -translate-x-1/2 flex flex-col items-center justify-center pointer-events-none">\n        <div class="text-[8px] text-gray-400 font-bold uppercase tracking-wider leading-none mb-0.5">Live Trade PnL</div>\n        <div id="nav-live-pnl-val" class="text-2xl font-black tabular-nums leading-none tracking-tight text-red-400">-$0.20</div>\n    </div>'
)

# Variation 3: Docked as a sleek strip on the base of nav bar (attached to bottom of header)
v3_orig_header = '<header id="main-header" class="fixed top-0 left-0 right-0 z-50 bg-black border-b border-white/10 px-3 pb-2 flex justify-between items-center" style="padding-top: calc(54px + 0.5rem);">'
v3_new = '''<header id="main-header" class="fixed top-0 left-0 right-0 z-50 bg-black border-b border-white/10 flex flex-col" style="padding-top: calc(54px + 0.5rem);">
    <div class="w-full px-3 pb-2 flex justify-between items-center relative">
    <!-- Left: Profile, Bal, PnL -->
    <div class="flex items-center gap-2.5">
        <div class="w-10 h-10 rounded-md overflow-hidden border border-kalshi-border shadow-md shrink-0 cursor-pointer" onclick="toggleProfileDropdown()">
            <img id="nav-avatar" src="/static/ai_avatar.gif" class="w-full h-full object-cover" alt="Profile">
        </div>
        <div class="flex flex-col justify-center">
            <div class="flex items-baseline gap-1.5">
                <span class="text-[9px] text-gray-500 font-bold uppercase tracking-widest">BAL</span>
                <span id="nav-balance" class="text-xs font-black text-white tabular-nums">$695.59</span>
            </div>
            <div class="flex items-baseline gap-1.5">
                <span class="text-[9px] text-gray-500 font-bold uppercase tracking-widest">PNL</span>
                <span id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">+$200.97</span>
            </div>
        </div>
    </div>

    <!-- Right: Controls -->
    <div class="flex items-center gap-2">
        <div class="flex flex-col items-center gap-1.5">
            <span id="exec-mode-badge" class="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 leading-none shadow-sm">PAPER</span>
            <span id="nav-auto-badge" class="px-1.5 py-0.5 rounded text-[7px] font-bold uppercase tracking-widest bg-gray-800 text-emerald-400 border border-emerald-500/30 leading-none shadow-sm">AUTO ON</span>
        </div>
        <button id="updates-bell-btn" class="w-8 h-8 flex items-center justify-center bg-gray-800 text-gray-300 rounded-lg shadow-sm">
            <svg class="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
        </button>
        <button class="w-8 h-8 flex items-center justify-center bg-gray-800 text-gray-300 rounded-lg shadow-sm">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg>
        </button>
    </div>
    </div>
    <!-- Docked to Base of Nav Bar -->
    <div id="nav-live-pnl-container" class="w-full bg-[#0a0d16] border-t border-white/5 px-3 py-1 flex items-center justify-between">
        <div class="flex items-center gap-1.5">
            <span class="inline-block w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping"></span>
            <span class="text-[9px] font-bold text-gray-400 uppercase tracking-widest">OPEN TRADE P&L</span>
        </div>
        <div id="nav-live-pnl-val" class="text-sm font-black tabular-nums text-red-400 leading-none">-$0.20</div>
    </div>
</header>'''

# For v3, replace entire old header
header_start = base_html.find('<header id="main-header"')
header_end = base_html.find('</header>') + len('</header>')
v3 = base_html[:header_start] + v3_new + base_html[header_end:]

# Variation 4: Attached floating pill docked right at the bottom border of header
v4 = base_html.replace(
    '<div id="nav-live-pnl-container" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden flex-col items-center justify-center">\n        <div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest leading-none mb-0.5">Live Trade PnL</div>\n        <div id="nav-live-pnl-val" class="text-3xl font-black tabular-nums leading-none tracking-tight">+$0.00</div>\n    </div>',
    '''<div id="nav-live-pnl-container" class="absolute left-1/2 -bottom-3 -translate-x-1/2 z-10 flex items-center gap-2 px-3 py-0.5 rounded-full bg-[#0d1322] border border-cyan-500/40 shadow-[0_4px_12px_rgba(0,0,0,0.8)] pointer-events-none">
        <span class="flex h-1.5 w-1.5 relative">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-500"></span>
        </span>
        <span class="text-[8px] text-gray-400 font-black uppercase tracking-wider">OPEN P&L</span>
        <span id="nav-live-pnl-val" class="text-xs font-black tabular-nums text-red-400 leading-none">-$0.20</span>
    </div>'''
)

variations = [('v1_bottom2_xl', v1), ('v2_bottom25_2xl', v2), ('v3_docked_strip', v3), ('v4_docked_pill', v4)]

for name, html in variations:
    with open(f'test_{name}.html', 'w', encoding='utf-8') as f:
        f.write(html)

PORT = 8766
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass

class QuietServer(socketserver.TCPServer):
    allow_reuse_address = True

server = QuietServer(('127.0.0.1', PORT), QuietHandler)
t = threading.Thread(target=server.serve_forever)
t.daemon = True
t.start()
time.sleep(0.5)

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
for name, _ in variations:
    temp_png = os.path.join(os.environ['TEMP'], f'test_{name}.png')
    subprocess.run([chrome, '--headless=new', f'--screenshot={temp_png}', '--window-size=390,844', f'http://127.0.0.1:{PORT}/test_{name}.html'], capture_output=True)
    if os.path.exists(temp_png):
        im = Image.open(temp_png)
        crop = im.crop((0, 0, im.width, 220))
        crop.save(f'crop_{name}.png')
        print(f'Generated crop_{name}.png')

server.shutdown()
