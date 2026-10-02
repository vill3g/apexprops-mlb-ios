fpath = 'static/js/app.js'
with open(fpath, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    'minimumFractionDigits: 2, maximumFractionDigits: 2',
    "minimumFractionDigits: window.currentAsset === 'BTC' ? 0 : 2, maximumFractionDigits: window.currentAsset === 'BTC' ? 0 : 2"
)

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(text)
