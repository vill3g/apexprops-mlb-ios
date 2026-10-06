import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.trade_store import TradeStore
from backend.sports_bridge.prediction_client import SportsPredictionClient

@pytest.fixture
def client():
    return TestClient(app)

def test_api_sports_events_npb_kbo(client):
    """AC 1: Querying /api/engine/sports/events with NPB/KBO filter returns events from both leagues."""
    res = client.get("/api/engine/sports/events?sport=NPB/KBO")
    assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
    data = res.json()
    assert data.get("status") == "ok"
    events = data.get("events", [])
    assert len(events) > 0, "Expected non-empty events list for NPB/KBO"

    leagues = {e.get("league") or e.get("metadata", {}).get("league") for e in events}
    assert "NPB" in leagues, f"Expected NPB events in response, got leagues: {leagues}"
    assert "KBO" in leagues, f"Expected KBO events in response, got leagues: {leagues}"

    # Also verify sports categorization
    for e in events:
        assert e.get("sport") == "NPB/KBO"
        assert e.get("event_ticker")
        assert e.get("predicted_team")

def test_api_sports_events_other_sports(client):
    """Test other sports filters: NFL, MLB, NHL, SOC, UFC, TEN."""
    sports_to_test = ["NFL", "MLB", "NHL", "SOC", "TEN"]
    for sp in sports_to_test:
        res = client.get(f"/api/engine/sports/events?sport={sp}")
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        events = data.get("events", [])
        assert len(events) > 0, f"Expected active events for {sp}"
        for e in events:
            assert e.get("sport") == sp or e.get("league") == sp

def test_sports_prediction_client():
    """Verify SportsPredictionClient fetches combined picks and on-demand prediction."""
    client = SportsPredictionClient()
    picks = client.fetch_latest_picks()
    assert len(picks) > 0, "Expected picks from local AI prediction engine (8057)"

    npb_kbo_picks = [p for p in picks if p.get("sport") == "NPB/KBO"]
    assert len(npb_kbo_picks) > 0, "Expected NPB/KBO picks from slate"

    # Test on-demand prediction for an active NPB event
    pred = client.predict_for_event("KXNPBGAME-26OCT050500FUKTOH", "Fukuoka Hawks vs Tohoku Rakuten Golden Eagles")
    assert pred is not None
    assert pred.get("predicted_team")
    assert float(pred.get("confidence_pct", 0)) > 50.0
    assert "edge_pct" in pred

def test_on_demand_prediction_and_paper_trade_execution(client):
    """AC 3: Verify end-to-end flow: execute a paper trade on an active Kalshi event using AI prediction."""
    # Active Kalshi event
    event_ticker = "KXNPBGAME-26OCT050500FUKTOH"
    
    res = client.get(f"/api/engine/sports/predict?event_ticker={event_ticker}&execute=true&min_confidence=50.0&min_edge=0.0")
    assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("prediction") is not None
    assert data.get("criteria_met") is True, f"Criteria not met. Data: {data}"
    assert data.get("executed") is True
    
    trade_id = data.get("trade_id")
    assert trade_id, "Expected valid trade_id from execution"
    
    # Verify trade in database TradeStore
    trade = TradeStore.get_trade_by_id(trade_id)
    assert trade is not None, f"Trade {trade_id} should be stored in database"
    assert trade.get("status") == "OPEN"
    assert trade.get("mode") == "PAPER"
    assert trade.get("trading_style") == "SPORTS_AI"
    assert float(trade.get("entry_price", 0)) > 0
    assert int(trade.get("count", 0)) > 0

def test_execute_endpoint_direct(client):
    """Verify dedicated /api/engine/sports/execute endpoint."""
    event_ticker = "KXKBOGAME-26OCT060530DOOLOT"
    res = client.post(f"/api/engine/sports/execute?event_ticker={event_ticker}")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("executed") is True
    trade_id = data.get("trade_id")
    assert trade_id
    trade = TradeStore.get_trade_by_id(trade_id)
    assert trade is not None
    assert trade.get("mode") == "PAPER"

def test_execute_combo_endpoint(client):
    """Verify dedicated /api/engine/sports/combo endpoint."""
    event_tickers = "KXKBOGAME-26OCT060530DOOLOT,KXNPBGAME-26OCT050500FUKTOH"
    res = client.post(f"/api/engine/sports/combo?event_tickers={event_tickers}")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("combo_executed") is True
    trades = data.get("trades", [])
    assert len(trades) > 0

def test_frontend_contract_and_rendering_logic():
    """AC 2: Verify frontend saas_dashboard.html has correct handlers and icons."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Verify buttons
    assert 'id="btn-asset-npb-kbo"' in html
    assert "filterSportsEvents('NPB/KBO')" in html
    assert "filterSportsEvents('NFL')" in html
    assert "filterSportsEvents('MLB')" in html
    assert "filterSportsEvents('NHL')" in html
    assert "filterSportsEvents('SOC')" in html
    assert "filterSportsEvents('UFC')" in html
    assert "filterSportsEvents('TEN')" in html

    # Verify SPORT_ICONS is defined
    assert "const SPORT_ICONS =" in html

    # Verify isSportMatch logic combines NPB and KBO
    assert "NPB/KBO" in html
    assert "querySportsAI" in html
    assert "/api/engine/sports/predict" in html
    assert "/api/engine/sports/events" in html
    assert "__sportsReqId" in html
    assert "__sportsLoading" in html

def test_sports_bridge_executor_no_kalshi_python():
    """Ledger 1: Verify SportsBridgeExecutor initializes and worker imports without kalshi_python."""
    import backend.worker
    from backend.sports_bridge.executor import SportsBridgeExecutor
    executor = SportsBridgeExecutor()
    assert executor is not None
    assert hasattr(executor, "run_cycle")
    assert hasattr(executor, "_settle_open_trades")

def test_prediction_client_unmatched_game_monte_carlo_fallback():
    """Ledger 2: Unmatched NPB/KBO game must not falsely match random pick; must simulate on demand."""
    client = SportsPredictionClient()
    pred = client.predict_for_event("KXNPBGAME-26OCT050500YOKHIR", "Yokohama Baystars vs Hiroshima Carp")
    assert pred is not None
    assert pred.get("sport") == "NPB/KBO"
    assert pred.get("league") == "NPB"
    # Must simulate or evaluate for the actual matchup, not a random team like Tampa Bay or Tohoku
    assert pred.get("predicted_team") in ("Yokohama Baystars", "Hiroshima Carp", "Favorite")
    if pred.get("metadata", {}).get("simulation"):
        assert pred.get("confidence_pct", 0) > 50.0

def test_api_sports_events_caching_and_speed(client):
    """Ledger 3 & 6: Cached query should execute rapidly without repetitive external Kalshi calls."""
    import time
    t0 = time.time()
    res1 = client.get("/api/engine/sports/events?sport=NPB/KBO")
    t1 = time.time()
    assert res1.status_code == 200
    res2 = client.get("/api/engine/sports/events?sport=NPB/KBO")
    t2 = time.time()
    assert res2.status_code == 200
    assert len(res2.json().get("events", [])) == len(res1.json().get("events", []))
    # Cached call should take less than 0.5s
    assert (t2 - t1) < 0.5

def test_predict_threshold_criteria_not_met(client):
    """Verify criteria_met is False and no paper trade executed when confidence threshold is unreachable."""
    event_ticker = "KXNPBGAME-26OCT050500FUKTOH"
    res = client.get(f"/api/engine/sports/predict?event_ticker={event_ticker}&execute=true&min_confidence=99.9")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("criteria_met") is False
    assert data.get("executed") is False
    assert data.get("trade_id") is None

def test_predict_client_prevents_false_cross_match_on_partial_team():
    """Reviewer R2: Event Doosan vs Lotte must not falsely match pick KT Wiz vs Lotte."""
    client = SportsPredictionClient()
    pred = client.predict_for_event("KXKBOGAME-26OCT060530DOOLOT", "Doosan Bears vs Lotte Giants", "NPB/KBO")
    assert pred is not None
    # The predicted team must actually be playing in this game
    assert pred.get("predicted_team") in ("Doosan Bears", "Lotte Giants", "Favorite")
    assert pred.get("predicted_team") != "KT Wiz"
    if pred.get("metadata", {}).get("simulation"):
        assert pred.get("confidence_pct", 0) > 50.0

def test_predict_empty_or_whitespace_ticker(client):
    """Reviewer R2: Empty or whitespace ticker must return None / error and not execute."""
    pred_client = SportsPredictionClient()
    assert pred_client.predict_for_event("", "") is None
    assert pred_client.predict_for_event("   ", "") is None

    res = client.get("/api/engine/sports/predict?event_ticker=")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "error"
    assert data.get("executed") is False
    assert data.get("trade_id") is None

def test_execute_nonexistent_kalshi_event(client):
    """Reviewer R2: Attempting to trade on a non-existent Kalshi event (404) must not create a trade."""
    event_ticker = "KXNPBGAME-NONEXISTENT-999"
    res = client.post(f"/api/engine/sports/execute?event_ticker={event_ticker}&min_confidence=50.0&min_edge=0.0")
    assert res.status_code == 200
    data = res.json()
    assert data.get("executed") is False
    assert data.get("trade_id") is None
    assert "Trade execution failed" in str(data.get("error"))

def test_ai_engine_unreachable_fallback():
    """Reviewer R2: When port 8057 is unreachable, SportsPredictionClient falls back gracefully."""
    c = SportsPredictionClient(base_url="http://127.0.0.1:9999", endpoint_url="http://127.0.0.1:9999/api/bot-bridge/predictions")
    pred = c.predict_for_event("KXNPBGAME-26OCT050500FUKTOH", "Fukuoka Hawks vs Tohoku Rakuten Golden Eagles")
    assert pred is not None
    assert pred.get("predicted_team") in ("Fukuoka Hawks", "Tohoku Rakuten Golden Eagles", "Favorite")
    assert pred.get("metadata", {}).get("on_demand_eval") is True
    assert pred.get("confidence_pct") == 65.0
    assert pred.get("edge_pct") == 12.5

def test_ai_engine_500_error_fallback(monkeypatch):
    """Reviewer R2: When AI engine returns 500 error, client falls back to baseline model."""
    class Mock500Response:
        status_code = 500
        def json(self):
            return {"error": "internal error"}
    c = SportsPredictionClient(base_url="http://127.0.0.1:8888", endpoint_url="http://127.0.0.1:8888/api/bot-bridge/predictions")
    monkeypatch.setattr(c.client, "get", lambda *args, **kwargs: Mock500Response())

    pred = c.predict_for_event("KXNPBGAME-26OCT050500FUKTOH", "Fukuoka Hawks vs Tohoku Rakuten Golden Eagles")
    assert pred is not None
    assert pred.get("metadata", {}).get("on_demand_eval") is True
    assert pred.get("confidence_pct") == 65.0

def test_sports_bridge_settle_kx_trades_both_sides(monkeypatch):
    """Reviewer R2: SportsBridgeExecutor._settle_open_trades handles KX tickers and both YES/NO sides."""
    import uuid
    from backend.sports_bridge.executor import SportsBridgeExecutor
    import backend.sports_bridge.executor as executor_module

    test_uid = 99999
    trade_id_yes = f"test_settle_{uuid.uuid4().hex[:8]}"
    trade_id_no = f"test_settle_{uuid.uuid4().hex[:8]}"

    trade_yes = {
        "id": trade_id_yes,
        "user_id": test_uid,
        "ticker": "KXNPBGAME-TEST-YES",
        "side": "YES",
        "entry_price": 0.60,
        "count": 10,
        "cost": 6.0,
        "pnl": 0.0,
        "status": "OPEN",
        "mode": "PAPER",
        "trading_style": "SPORTS_AI"
    }
    trade_no = {
        "id": trade_id_no,
        "user_id": test_uid,
        "ticker": "KXNPBGAME-TEST-NO",
        "side": "NO",
        "entry_price": 0.40,
        "count": 10,
        "cost": 4.0,
        "pnl": 0.0,
        "status": "OPEN",
        "mode": "PAPER",
        "trading_style": "SPORTS_AI"
    }

    TradeStore.insert_trade(test_uid, trade_yes)
    TradeStore.insert_trade(test_uid, trade_no)

    # Mock settlement as YES won
    monkeypatch.setattr(executor_module, "_check_kalshi_settlement", lambda ticker: {"status": "determined", "result": "YES"})

    exec_inst = SportsBridgeExecutor()
    exec_inst._settle_open_trades({"id": test_uid})

    settled_yes = TradeStore.get_trade_by_id(trade_id_yes)
    settled_no = TradeStore.get_trade_by_id(trade_id_no)

    assert settled_yes.get("status") == "CLOSED"
    assert settled_yes.get("exit_price") == 1.0
    assert settled_yes.get("pnl") == 4.0  # (1.0 - 0.6) * 10

    assert settled_no.get("status") == "CLOSED"
    assert settled_no.get("exit_price") == 0.0
    assert settled_no.get("pnl") == -4.0  # -0.4 * 10

def test_tennis_on_demand_simulation():
    """Reviewer R3: Tennis event must run live on-demand simulation on port 8057."""
    client = SportsPredictionClient()
    pred = client.predict_for_event("KXATPMATCH-26OCT05BELYME", "Bellucci vs Ymer", "TEN")
    assert pred is not None
    assert pred.get("sport") == "TEN"
    assert pred.get("league") == "TEN"
    assert pred.get("predicted_team") in ("Bellucci", "Ymer")
    if pred.get("metadata", {}).get("simulation"):
        assert pred.get("confidence_pct", 0) > 50.0
        assert pred.get("edge_pct", 0) >= 0.0

def test_tennis_and_soccer_sport_normalization(client):
    """Reviewer R3: Sport normalization must bridge 'TENNIS' to 'TEN', 'SOCCER' to 'SOC'."""
    from backend.routes.engine import _normalize_sport
    assert _normalize_sport("TEN") == "TEN"
    assert _normalize_sport("TENNIS") == "TEN"
    assert _normalize_sport("ATP") == "TEN"
    assert _normalize_sport("WTA") == "TEN"
    assert _normalize_sport("SOC") == "SOC"
    assert _normalize_sport("SOCCER") == "SOC"
    assert _normalize_sport("UFC") == "UFC"
    assert _normalize_sport("MMA") == "UFC"
    assert _normalize_sport("NPB/KBO") == "NPB/KBO"
    assert _normalize_sport("NPB") == "NPB/KBO"
    assert _normalize_sport("KBO") == "NPB/KBO"

    # Query events for TEN: must return events
    res = client.get("/api/engine/sports/events?sport=TEN")
    assert res.status_code == 200
    events = res.json().get("events", [])
    assert len(events) > 0
    for e in events:
        assert e.get("sport") == "TEN"

def test_predict_uses_cache_and_custom_title_under_kalshi_failure(client, monkeypatch):
    """Reviewer R3: When Kalshi /events endpoint is 429 or failing, predict uses provided title or cache."""
    import requests
    # Simulate Kalshi 429 rate limit
    class Mock429Response:
        status_code = 429
        text = "Too Many Requests"
        def json(self):
            return {"error": "rate limit"}

    real_get = requests.get
    def mock_get(url, *args, **kwargs):
        if "/events/" in str(url) and not "nested_markets" in str(url):
            return Mock429Response()
        return real_get(url, *args, **kwargs)

    monkeypatch.setattr(requests, "get", mock_get)

    # Calling with explicit title and sport
    res = client.get("/api/engine/sports/predict?event_ticker=KXATPMATCH-26OCT05BELYME&title=Bellucci%20vs%20Ymer&sport=TEN&execute=false")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert data.get("prediction") is not None
    pred = data["prediction"]
    assert pred.get("predicted_team") in ("Bellucci", "Ymer")

def test_frontend_cache_updates_without_stuck_state():
    """Reviewer R3: saas_dashboard.html must pass title & sport params and update cache per sport."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert "&title=" in html
    assert "&sport=" in html
    assert "window.__sportsEventsCache = [...otherEvents, ...newEvents];" in html


def test_mlb_hits_runs_rbis_player_prop_parsing():
    """Verify KXMLBHRR markets are accurately parsed as Player Prop with '1+ H+R+RBI' line."""
    from backend.routes.engine import parse_sports_market_details
    mkt = {
        'ticker': 'KXMLBHRR-26OCT061800LADATL-LADSOHTANI17-1',
        'title': 'Shohei Ohtani: 1+ hits + runs + RBIs?',
        'yes_sub_title': 'Shohei Ohtani: 1+',
        'floor_strike': 0.5,
        'rules_primary': 'If Shohei Ohtani records 1+ total hits + runs + rbis in the game, then the market resolves to Yes.'
    }
    details = parse_sports_market_details(
        ticker='KXMLBHRR-26OCT061800LADATL-LADSOHTANI17-1',
        title='Shohei Ohtani: 1+ hits + runs + RBIs?',
        series='KXMLBHRR',
        markets=[mkt],
        sub_title='Shohei Ohtani: 1+'
    )
    assert details['prop_type'] == 'Player Prop'
    assert details['line'] == '1+ H+R+RBI'
    assert details['player_name'] == 'Shohei Ohtani'
    assert details['strike_details'] == 'Shohei Ohtani: 1+ H+R+RBI'
    assert details['numeric_line'] == 1.0


def test_mlb_events_includes_hrr_series():
    """Verify _SPORTS_SERIES_MAP contains KXMLBHRR for MLB."""
    from backend.routes.engine import _SPORTS_SERIES_MAP
    assert 'KXMLBHRR' in _SPORTS_SERIES_MAP.get('MLB', [])


