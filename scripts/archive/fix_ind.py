import sys  
with open('backend/btc/indicators.py', 'r') as f: content = f.read()  
content = content.split('def compute_cvd_acceleration')[0]  
with open('backend/btc/indicators.py', 'w') as f: f.write(content)  
