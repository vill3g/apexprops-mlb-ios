with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('const balEl = document.getElementById("kalshiLiveBalance");')
if start != -1:
    print(text[start:start+1000])
