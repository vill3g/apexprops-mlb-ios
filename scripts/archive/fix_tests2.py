import re

with open('tests/test_remediation.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('patch("backend.btc.auto_executor.auto_executor", mock_executor)', 'patch("backend.btc.scalp_engine.get_auto_executor", return_value=mock_executor)')

with open('tests/test_remediation.py', 'w', encoding='utf-8') as f:
    f.write(content)
