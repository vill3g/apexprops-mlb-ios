import re

with open('static/saas_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace finAssets classList toggling to explicitly use display: none logic
# Wait, I can just use .style.display
fix_js = '''
            if(universe === 'SPORTS') {
                finAssets.forEach(el => { el.style.display = 'none'; });
                if (moreAssetsWrapper) moreAssetsWrapper.style.display = 'none';
                sportsAssets.forEach(el => { el.style.display = 'inline-block'; el.classList.remove('hidden'); });
'''

html = html.replace('''            if(universe === 'SPORTS') {
                finAssets.forEach(el => el.classList.add('hidden'));
                if (moreAssetsWrapper) moreAssetsWrapper.classList.add('hidden');
                sportsAssets.forEach(el => el.classList.remove('hidden'));''', fix_js)

fix_js2 = '''
            } else {
                finAssets.forEach(el => { el.style.display = ''; el.classList.remove('hidden'); });
                if (moreAssetsWrapper) moreAssetsWrapper.style.display = '';
                sportsAssets.forEach(el => { el.style.display = 'none'; });
'''

html = html.replace('''            } else {
                finAssets.forEach(el => el.classList.remove('hidden'));
                if (moreAssetsWrapper) moreAssetsWrapper.classList.remove('hidden');
                sportsAssets.forEach(el => el.classList.add('hidden'));''', fix_js2)


with open('static/saas_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Fixed asset button hiding')
