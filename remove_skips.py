import os, glob

for p in glob.glob('tests/*.py'):
    with open(p, 'r') as f:
        content = f.read()
    
    if '@pytest.mark.skip(reason="Test logic obsoleted by fixes")' in content:
        content = content.replace('@pytest.mark.skip(reason="Test logic obsoleted by fixes")\n\n\n\n', '')
        content = content.replace('@pytest.mark.skip(reason="Test logic obsoleted by fixes")\n\n', '')
        content = content.replace('@pytest.mark.skip(reason="Test logic obsoleted by fixes")\n', '')
        with open(p, 'w') as f:
            f.write(content)
