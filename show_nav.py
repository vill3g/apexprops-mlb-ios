with open('temp_index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('<header id="iphone17NavBar"')
if start != -1:
    print(text[start:start+1500])
