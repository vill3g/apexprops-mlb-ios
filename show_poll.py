with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('async function pollKalshiTradingStatus()')
if start != -1:
    print(text[start:start+1000])
