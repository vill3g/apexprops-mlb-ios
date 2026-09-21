with open('main_index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('id="settingModelChoice"')
print(repr(text[start-200:start+200]))
