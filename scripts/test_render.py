import http.server, socketserver, threading, time, subprocess, os, shutil
from PIL import Image

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Make live pnl visible and set to -$0.20
target_div = '<div id="nav-live-pnl-container" class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden flex-col items-center justify-center">'
replacement_div = '<div id="nav-live-pnl-container" class="absolute left-1/2 bottom-2 -translate-x-1/2 flex flex-col items-center justify-center">'
test_content = content.replace(target_div, replacement_div)

target_val = '<div id="nav-live-pnl-val" class="text-3xl font-black tabular-nums leading-none tracking-tight">+$0.00</div>'
replacement_val = '<div id="nav-live-pnl-val" class="text-3xl font-black tabular-nums leading-none tracking-tight text-red-400">-$0.20</div>'
test_content = test_content.replace(target_val, replacement_val)

# Remove splash screen
test_content = test_content.replace('<div id="splash-screen"', '<div id="splash-screen" style="display:none !important;"')

# Disable auth redirect
test_content = test_content.replace("window.location.href = '/login.html';", "// disabled redirect")
test_content = test_content.replace("window.location.href = '/login.html'", "// disabled redirect")

# Also let's simulate safe-area-inset-top: 54px by styling
test_content = test_content.replace('padding-top: calc(env(safe-area-inset-top, 0px) + 0.5rem);', 'padding-top: calc(54px + 0.5rem);')
test_content = test_content.replace('padding-top: calc(3.5rem + env(safe-area-inset-top, 0px));', 'padding-top: calc(3.5rem + 54px);')

with open('test_current.html', 'w', encoding='utf-8') as f:
    f.write(test_content)

PORT = 8765
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

class QuietServer(socketserver.TCPServer):
    allow_reuse_address = True

server = QuietServer(('127.0.0.1', PORT), QuietHandler)
t = threading.Thread(target=server.serve_forever)
t.daemon = True
t.start()

time.sleep(0.5)

temp_png = os.path.join(os.environ['TEMP'], 'test_view.png')
chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
res = subprocess.run([chrome, '--headless=new', f'--screenshot={temp_png}', '--window-size=390,844', f'http://127.0.0.1:{PORT}/test_current.html'], capture_output=True, text=True)

if os.path.exists(temp_png):
    shutil.copy(temp_png, 'test_current_view.png')
    im = Image.open('test_current_view.png')
    crop = im.crop((0, 0, im.width, 250))
    crop.save('test_current_crop.png')
    print('SUCCESS! test_current_crop.png generated!')

server.shutdown()
