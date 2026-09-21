import sys
with open('static/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start = text.find('// 1. MLB Hits + Runs + RBIs')
if start != -1:
    end = start + 500
    print(text[start:end].encode('ascii', 'ignore').decode('ascii'))
