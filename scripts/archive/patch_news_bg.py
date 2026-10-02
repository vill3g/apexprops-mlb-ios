import re

with open('backend/btc/news_fetcher.py', 'r', encoding='utf-8') as f:
    code = f.read()

bg_code = """
import threading
import time

_bg_thread_started = False

def _background_news_updater():
    while True:
        try:
            # Force a fresh fetch by temporarily overriding TTL logic
            global _NEWS_CACHE_TIME
            _NEWS_CACHE_TIME = 0.0
            fetch_crypto_news()
        except Exception as e:
            pass
        time.sleep(115) # Refresh every ~2 minutes

def start_news_background_task():
    global _bg_thread_started
    if not _bg_thread_started:
        t = threading.Thread(target=_background_news_updater, daemon=True)
        t.start()
        _bg_thread_started = True

start_news_background_task()
"""

if "start_news_background_task()" not in code:
    code = code + bg_code
    with open('backend/btc/news_fetcher.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Added background news updater")
else:
    print("Already added")
