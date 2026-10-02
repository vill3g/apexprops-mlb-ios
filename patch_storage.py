import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("sessionStorage.getItem('tradingTipShown')", "localStorage.getItem('tradingTipShown')")
content = content.replace("sessionStorage.setItem('tradingTipShown', 'true')", "localStorage.setItem('tradingTipShown', 'true')")

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced sessionStorage with localStorage!")
