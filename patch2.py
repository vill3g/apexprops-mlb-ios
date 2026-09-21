import os, re
an_path = 'backend/btc/analyzer.py'
with open(an_path, 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'grade = "GRADE B SETUP"(\s+badge = ".*?\((6[34])%\)")', r'grade = "GRADE B+ SETUP"\1', text)
text = re.sub(r'3-STAR B \((6[34])%\)', r'3-STAR B+ (\1%)', text)

with open(an_path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Regex patch applied.")
