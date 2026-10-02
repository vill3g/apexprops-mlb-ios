with open('requirements.txt', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('yfinance==0.2.50', 'yfinance==1.7.0')

with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write(content)
