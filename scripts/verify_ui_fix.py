import http.server
import socketserver
import threading
import time
import subprocess
import os
import shutil
import glob
from PIL import Image

def run_verification():
    # Read actual static/saas_dashboard.html
    with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Assertions on modified codebase
    assert 'id="nav-live-pnl-container" class="absolute left-1/2 bottom-2 -translate-x-1/2 hidden flex-col items-center justify-center pointer-events-none z-10"' in html, 'bottom-2 not found on nav-live-pnl-container'
    assert 'id="nav-live-pnl-container" class="absolute left-1/2 top-1/2' not in html, 'old positioning still found on nav-live-pnl-container'
    assert 'Open Trade PnL' in html, 'Open Trade PnL label not found'
    assert 'text-lg sm:text-xl font-black tabular-nums' in html, 'balanced typography not found in html/js'
    assert "const isPos = lPnl > -0.005;" in html, 'negative zero guard not found in JS'
    assert "livePnlVal.textContent = (isPos ? '+$' : '-$') + Math.abs(lPnl).toFixed(2);" in html, 'proper +/- sign formatting not found in JS'
    assert 'backdrop- ' not in html, 'broken backdrop- class found in html'
    assert 'id="profileDropdown"' in html and 'top: calc(env(safe-area-inset-top, 0px) + 3.75rem);' in html, 'profileDropdown safe area style missing'

    print('[PASS] All code assertions verified successfully in static/saas_dashboard.html!')

    # 2. Render final verification screenshot
    render_html = html.replace('<div id="splash-screen"', '<div id="splash-screen" style="display:none !important;"')
    render_html = render_html.replace("window.location.href = '/login.html';", "// disabled")
    render_html = render_html.replace("window.location.href = '/login.html'", "// disabled")
    render_html = render_html.replace('padding-top: calc(env(safe-area-inset-top, 0px) + 0.5rem);', 'padding-top: calc(54px + 0.5rem);')
    render_html = render_html.replace('padding-top: calc(3.5rem + env(safe-area-inset-top, 0px));', 'padding-top: calc(3.5rem + 54px);')
    render_html = render_html.replace('hidden flex-col items-center justify-center', 'flex flex-col items-center justify-center')
    render_html = render_html.replace('id="nav-balance" class="text-xs font-black text-white tabular-nums">$--.--<', 'id="nav-balance" class="text-xs font-black text-white tabular-nums">$695.59<')
    render_html = render_html.replace('id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">$--.--<', 'id="nav-pnl" class="text-[11px] font-bold tabular-nums text-emerald-400">+$200.97<')
    render_html = render_html.replace('text-emerald-400">+$0.00<', 'text-rose-400">-$0.20<')

    with open('final_verify.html', 'w', encoding='utf-8') as f:
        f.write(render_html)

    PORT = 8780
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass

    class QuietServer(socketserver.TCPServer):
        allow_reuse_address = True

    server = QuietServer(('127.0.0.1', PORT), QuietHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.5)

    temp_png = os.path.join(os.environ['TEMP'], 'final_verify.png')
    chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    subprocess.run([chrome, '--headless=new', f'--screenshot={temp_png}', '--window-size=390,844', f'http://127.0.0.1:{PORT}/final_verify.html'], capture_output=True)

    if os.path.exists(temp_png):
        shutil.copy(temp_png, 'final_verification_full.png')
        im = Image.open('final_verification_full.png')
        crop = im.crop((0, 0, im.width, 150))
        crop.save('final_verification_crop.png')
        print('[PASS] Screenshots generated: final_verification_crop.png and final_verification_full.png')

    server.shutdown()

    # Cleanup temp scratch files
    for pat in ['test_*.html', 'test_*.png', 'crop_*.png', 'final_verify.html']:
        for file in glob.glob(pat):
            try:
                os.remove(file)
            except Exception:
                pass
    print('[PASS] Temporary test files cleaned up.')

if __name__ == '__main__':
    run_verification()
