import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('async function checkTradingTip(force = false) {', 'window.checkTradingTip = async function(force = false) {')

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced!")
