import re

with open('tests/test_audit_findings.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("from backend.btc.auto_executor import auto_executor", "from backend.btc.auto_executor import get_auto_executor\nauto_executor = get_auto_executor('BTC')")

with open('tests/test_audit_findings.py', 'w', encoding='utf-8') as f:
    f.write(content)
    
with open('tests/test_remediation.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("from backend.btc.auto_executor import auto_executor", "from backend.btc.auto_executor import get_auto_executor\nauto_executor = get_auto_executor('BTC')")

with open('tests/test_remediation.py', 'w', encoding='utf-8') as f:
    f.write(content)
