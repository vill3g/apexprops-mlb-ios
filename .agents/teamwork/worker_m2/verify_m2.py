import json
from html.parser import HTMLParser
from bs4 import BeautifulSoup

print("=== 1. HTML PARSER VERIFICATION ===")
class TagChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() not in self.void_tags:
            self.stack.append((tag.lower(), self.getpos()))

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self.void_tags:
            return
        if not self.stack:
            self.errors.append(f'Unexpected end tag </{t}> at {self.getpos()}')
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == t:
                for unclosed, pos in self.stack[i+1:]:
                    self.errors.append(f'Unclosed <{unclosed}> opened at {pos} before </{t}> at {self.getpos()}')
                self.stack = self.stack[:i]
                return
        self.errors.append(f'No matching start tag for </{t}> at {self.getpos()}')

checker = TagChecker()
with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    saas_html = f.read()
checker.feed(saas_html)
for unclosed, pos in checker.stack:
    checker.errors.append(f'Unclosed tag <{unclosed}> opened at {pos} reached EOF')

print(f'saas_dashboard.html structural errors: {len(checker.errors)}')
assert len(checker.errors) == 0, f'Expected 0 errors, got: {checker.errors}'

print("=== 2. SETTINGS DRAWER DOM STRUCTURE ===")
soup = BeautifulSoup(saas_html, 'html.parser')
drawer = soup.find('div', id='settingsDrawer')
assert drawer is not None, 'settingsDrawer not found'
direct_child_ids = [c.get('id') or c.name for c in drawer.find_all(recursive=False) if hasattr(c, 'name')]
print('settingsDrawer direct children:', direct_child_ids)
assert direct_child_ids == ['settingsBackdrop', 'settingsPanel'], f'Unexpected drawer children: {direct_child_ids}'

print("=== 3. SAFE AREA INSETS IN SAAS DASHBOARD ===")
assert 'safe-area-inset-bottom' in saas_html
assert 'pb-safe' in saas_html
main_tag = soup.find('main')
assert main_tag is not None
assert 'safe-area-inset-bottom' in main_tag.get('style', '') or 'pb-safe' in main_tag.get('class', [])
print('main container safe area:', main_tag.get('style'), main_tag.get('class'))

update_card = soup.find('div', id='updateAnnouncementCard')
assert update_card is not None
update_footer = update_card.find_all('div', recursive=False)[-1]
print('updateAnnouncementModal footer style:', update_footer.get('style'))
assert 'safe-area-inset-bottom' in update_footer.get('style', '')

tdm_modal = soup.find('div', id='tradeDetailsModal')
assert tdm_modal is not None
tdm_card = tdm_modal.find('div', recursive=False)
tdm_footer = tdm_card.find_all('div', recursive=False)[-1]
print('tradeDetailsModal footer style:', tdm_footer.get('style'))
assert 'safe-area-inset-bottom' in tdm_footer.get('style', '')

print("=== 4. BACKDROP BLUR TOKENS RESTORATION ===")
orphan_tokens = [' -sm ', ' -xl ', ' -2xl ', ' -md ']
for tok in orphan_tokens:
    assert tok not in saas_html, f'Found orphan token {tok}'
assert 'backdrop-blur-2xl' in saas_html
assert 'backdrop-blur-xl' in saas_html
assert 'backdrop-blur-sm' in saas_html
print('backdrop-blur tokens successfully restored.')

print("=== 5. RETIRE UPDATE ALERT MODAL & TV.JS ===")
assert 'updateAlertModal' not in saas_html
assert 'dismissUpdateAlert' not in saas_html
assert 's3.tradingview.com/tv.js' not in saas_html
print('updateAlertModal and tv.js successfully retired.')

print("=== 6. VOID META TAGS IN HEAD ===")
head_str = saas_html[:saas_html.find('</head>')]
assert '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">' in head_str
assert '<meta http-equiv="Pragma" content="no-cache">' in head_str
assert '<meta http-equiv="Expires" content="0">' in head_str
print('Void meta tags verified valid HTML5.')

print("=== 7. TRADES.HTML SAFE AREA & VIEWPORT ===")
with open('static/trades.html', 'r', encoding='utf-8') as f:
    trades_html = f.read()
assert 'viewport-fit=cover' in trades_html
assert 'safe-area-inset-top' in trades_html
assert 'safe-area-inset-bottom' in trades_html
t_checker = TagChecker()
t_checker.feed(trades_html)
assert len(t_checker.errors) == 0
print('trades.html safe area and syntax verified.')

print("=== 8. CAPACITOR CONFIG CONTENT INSET ===")
with open('capacitor.config.json', 'r', encoding='utf-8') as f:
    cap_cfg = json.load(f)
assert cap_cfg['ios']['contentInset'] == 'automatic'
print('capacitor.config.json contentInset verified:', cap_cfg['ios']['contentInset'])

print("=== 9. APP.CSS & DASHBOARD.CSS LOADED ===")
assert 'href="./css/app.css"' in saas_html
assert 'href="./css/dashboard.css"' in saas_html
with open('static/css/dashboard.css', 'r', encoding='utf-8') as f:
    dash_css = f.read()
assert '--sab' in dash_css
assert '.pb-safe' in dash_css

print('\nALL 9 CHECKS PASSED PERFECTLY!')
