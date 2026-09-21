with open('temp_index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('sleek-glass-header')
if start != -1:
    print(text[start-200:start+1500])
