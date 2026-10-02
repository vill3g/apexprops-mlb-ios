import http.server, socketserver, threading, time, subprocess, os, shutil
from PIL import Image

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    base_html = f.read()

# Disable splash and auth
base_html = base_html.replace('<div id="splash-screen"', '<div id="splash-screen" style="display:none !important;"')
base_html = base_html.replace("window.location.href = '/login.html';", "// disabled")
base_html = base_html.replace("window.location.href = '/login.html'", "// disabled")

# Mock data matching user screenshot
base_html = base_html.replace('id="nav-balance" class="text-xs font-black text-white tabular-nums">$--.--<', 'id="nav-balance" class="text-xs font-black text-white tabular-nums">$695.59<')
base_html = base_html.replace('id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">$--.--<', 'id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">+$200.97<')
base_html = base_html.replace('AUTO OFF', 'AUTO ON')
base_html = base_html.replace('text-gray-400 border border-gray-700', 'text-emerald-400 border border-emerald-500/30')

# Simulate safe-area-inset-top: 54px
base_html = base_html.replace('padding-top: calc(env(safe-area-inset-top, 0px) + 0.5rem);', 'padding-top: calc(54px + 0.5rem);')
base_html = base_html.replace('padding-top: calc(3.5rem + env(safe-area-inset-top, 0px));', 'padding-top: calc(3.5rem + 54px);')

# New nav-live-pnl-container: bottom-2 left-1/2 -translate-x-1/2
target_div = '<div id="nav-live-pnl-container" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden flex-col items-center justify-center">'
new_div = '<div id="nav-live-pnl-container" class="absolute left-1/2 bottom-2 -translate-x-1/2 flex flex-col items-center justify-center pointer-events-none z-10">'
base_html = base_html.replace(target_div, new_div)

target_inner = '''<div class="text-[9px] text-gray-500 font-bold uppercase tracking-widest leading-none mb-0.5">Live Trade PnL</div>
        <div id="nav-live-pnl-val" class="text-3xl font-black tabular-nums leading-none tracking-tight">+$0.00</div>'''
new_inner = '''<div class="text-[8px] sm:text-[9px] text-gray-400 font-bold uppercase tracking-widest leading-none mb-0.5">Live Trade PnL</div>
        <div id="nav-live-pnl-val" class="text-xl sm:text-2xl font-black tabular-nums leading-none tracking-tight text-rose-400">-$0.20</div>'''
base_html = base_html.replace(target_inner, new_inner)

with open('test_final_preview.html', 'w', encoding='utf-8') as f:
    f.write(base_html)

PORT = 8769
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
for w, h, name in [(390, 844, 'iphone14_390'), (375, 667, 'iphoneSE_375'), (430, 932, 'iphoneProMax_430')]:
    temp_png = os.path.join(os.environ['TEMP'], f'preview_{name}.png')
    subprocess.run([chrome, '--headless=new', f'--screenshot={temp_png}', f'--window-size={w},{h}', f'http://127.0.0.1:{PORT}/test_final_preview.html'], capture_output=True)
    if os.path.exists(temp_png):
        im = Image.open(temp_png)
        crop = im.crop((0, 0, im.width, 200))
        crop.save(f'crop_{name}.png')
        print(f'Rendered crop_{name}.png ({w}x{h})')

server.shutdown()
