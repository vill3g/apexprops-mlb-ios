with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('if (tab === \'plan\')')
if start != -1:
    end = start + 500
    print(text[start-500:end].encode('ascii', 'ignore').decode('ascii'))
