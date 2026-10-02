
import re
path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\btc\kalshi_trader.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure tenacity is imported
if 'from tenacity import' not in content:
    content = content.replace('import time', 'import time\nfrom tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type')
if 'import requests' not in content:
    content = 'import requests\n' + content

# Wrap get_market_result
content = content.replace('    def get_market_result(self, ticker: str) -> Dict[str, Any]:', '    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=1, max=5), retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError)))\n    def get_market_result(self, ticker: str) -> Dict[str, Any]:')

# Wrap get_market_quote
content = content.replace('    def get_market_quote(self, ticker: str) -> Dict[str, Any]:', '    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=1, max=5), retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout, requests.exceptions.ConnectionError)))\n    def get_market_quote(self, ticker: str) -> Dict[str, Any]:')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

