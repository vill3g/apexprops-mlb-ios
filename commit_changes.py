import os
from dulwich import porcelain
repo_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader'
porcelain.add(repo_path, '.')
porcelain.commit(repo_path, b'feat: UI Live Signals scroller, grace period fixes, Chart Override rules', author=b'AI <ai@example.com>')
print('Committed locally.')
