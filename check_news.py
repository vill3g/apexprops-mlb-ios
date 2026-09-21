import sys
sys.path.append('.')
from backend.btc.news_fetcher import get_news_sentiment_summary
import json

print(json.dumps(get_news_sentiment_summary(), indent=2))
