with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('// 5. Deep Dive Modal Logic')
if start != -1:
    end = start + 3000
    print(text[start:end].encode('ascii', 'ignore').decode('ascii'))
