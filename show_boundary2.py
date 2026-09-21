with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('function switchAuxTab')
if start != -1:
    end = start + 500
    print(text[start-1000:end].encode('ascii', 'ignore').decode('ascii'))
