with open('temp_index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('<header class="sticky top-0 z-40 sleek-glass-header')
if start != -1:
    print(text[start:start+1500])
