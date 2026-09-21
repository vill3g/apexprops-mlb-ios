with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('id="topBarLivePnlContainer"')
if start != -1:
    print(repr(text[start-100:start+200]))
