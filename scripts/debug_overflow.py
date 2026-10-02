import subprocess, os

js_code = """
const elements = document.querySelectorAll('*');
let widest = [];
elements.forEach(el => {
    const rect = el.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
        widest.push({tag: el.tagName, id: el.id, class: el.className, right: rect.right, width: rect.width});
    }
});
console.log('OVERFLOW_ELEMENTS:' + JSON.stringify(widest.slice(0, 10)));
"""

with open('test_v1_bottom2_xl.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('</body>', f'<script>{js_code}</script></body>')
with open('test_v1_debug.html', 'w', encoding='utf-8') as f:
    f.write(html)

chrome = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
res = subprocess.run([chrome, '--headless=new', '--enable-logging=stderr', '--v=1', '--window-size=390,844', 'http://127.0.0.1:8766/test_v1_debug.html'], capture_output=True, text=True)
for line in res.stderr.splitlines():
    if 'OVERFLOW_ELEMENTS' in line:
        print(line)
