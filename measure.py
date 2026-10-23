import sys
import time
sys.path.insert(0, 'C:/Users/Vill3/Desktop/kalshi-ai-trader')
from backend.sports_bridge.prediction_client import SportsPredictionClient

client = SportsPredictionClient()

# Mock get
def _mock_get(url, *args, **kwargs):
    class MockResp:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code
        def json(self): return self._json
        
    if "narrative" in url:
        time.sleep(2.0)
        return MockResp({"narrative": "Done"})
    if "explain" in url:
        time.sleep(0.5)
        return MockResp({"market": "moneyline", "line": ""})
    return MockResp({})

client.client.get = _mock_get

best_match = {"sport": "MLB", "market_type": "MONEYLINE", "metadata": {"game_id": "game-123"}, "predicted_team": "Team A"}
client.fetch_latest_picks = lambda *a, **k: [best_match]
client._match_kalshi_event_to_predictions = lambda t, ti, p: best_match

start = time.time()
client.predict_for_event("KXMLB-123", "Team A vs Team B", "MLB")
elapsed_no_cache = time.time() - start

# Run again, this time explain will hit the cache, and narrative will spawn a thread again
start = time.time()
client.predict_for_event("KXMLB-123", "Team A vs Team B", "MLB")
elapsed_cache = time.time() - start

print(f"Elapsed (no cache): {elapsed_no_cache:.4f}s")
print(f"Elapsed (cache): {elapsed_cache:.4f}s")
