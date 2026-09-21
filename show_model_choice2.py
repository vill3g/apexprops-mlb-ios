with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('settingModelChoice')
print(text[start-150:start+50])
