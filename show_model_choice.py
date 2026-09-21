with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('Model Choice')
print(text[start-150:start+50])
