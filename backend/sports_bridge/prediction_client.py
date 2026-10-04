import httpx
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class SportsPredictionClient:
    def __init__(self, endpoint_url="http://127.0.0.1:8057/api/bot-bridge/predictions"):
        self.endpoint_url = endpoint_url
        self.client = httpx.Client(timeout=10.0)

    def fetch_latest_picks(self) -> List[Dict]:
        try:
            response = self.client.get(self.endpoint_url)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                return data.get("predictions", [])
            return []
        except Exception as e:
            logger.error(f"Failed to fetch sports predictions: {e}")
            return []
