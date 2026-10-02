path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\analyzer.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('except Exception as e:\n        logger.error(f\"[Analyzer] Failed to load or predict with ML Engine: {e}\")', 'except (json.JSONDecodeError, FileNotFoundError, OSError, ValueError, TypeError) as e:\n        logger.error(f\"[Analyzer] Failed to load or predict with ML Engine: {e}\")')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
