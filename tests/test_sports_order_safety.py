"""Regression tests for the sports auto-trader order-safety fix (SPORTS_ORDER_SAFETY_FIX.md).

1. A LIVE sports order whose outcome is unknown ("ambiguous") must never be re-sent by a later
   cycle; a clean rejection may be retried.
2. Uncertain orders are reconciled against Kalshi positions and recorded if they filled.
3. Sizing keeps worst-case fill + Kalshi fee inside the wager, and never forces 1 contract.
4. Settlement / take-profit close a trade and credit paper winnings exactly once.
"""
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

import backend.database.models as models
import backend.sports_bridge.executor as sx
from backend.btc.fees import kalshi_order_fee
from backend.database import order_intents
from backend.database.trade_store import TradeStore

_ET = ZoneInfo("America/New_York")


def _user(mode="LIVE", **over):
    uid = models.create_user(f"sports_safety_{uuid.uuid4().hex[:6]}", "pw-hash")
    u = {"id": uid, "username": "sports_safety", "trading_mode": mode, "ai_enabled": 1,
         "trading_universe": "SPORTS", "min_sports_confidence": 50.0, "min_sports_edge": 0.0,
         "sports_trade_size_dollars": 10.0, "sports_max_wager": 10.0,
         "sports_max_daily_trades": 10, "sports_max_open_trades": 5, "sports_max_daily_risk": 100.0,
         "sports_active_leagues": "NFL", "sports_market_types": "GAME,SPREAD,TOTAL,PROP",
         "sports_min_price": 0.20, "sports_max_price": 0.80, "paper_balance": 500.0}
    u.update(over)
    return u


def _pick(ticker):
    import time
    now_s = time.time()
    return {"sport": "NFL", "predicted_team": "Team A", "confidence_pct": 80.0, "edge_pct": 6.0,
            "status": "scheduled", "start_epoch": now_s + 1800.0,
            "metadata": {"is_upcoming": True, "start_epoch": now_s + 1800.0}, "_ticker": ticker}


def _kt(order_results):
    kt = MagicMock()
    kt.is_authenticated.return_value = True
    kt.get_balance.return_value = {"success": True, "balance_dollars": 1000.0}
    kt.get_positions.return_value = {"success": True, "positions": []}
    kt.place_sports_order.side_effect = list(order_results)
    kt._extract_side_position.side_effect = lambda p, side: float((p or {}).get("position", 0) or 0)
    return kt


def _run(user, picks, kt):
    today = datetime.now(_ET).date()
    with patch("backend.btc.kalshi_trader.get_authenticated_trader_for_user", return_value=kt), \
         patch.object(sx, "_generate_kalshi_market",
                      side_effect=lambda pred, require_today=True, **kwargs: (pred["_ticker"], 0.50, "Team A to win", {})), \
         patch.object(sx, "extract_sports_event_date_and_time", return_value=(today, datetime.now(_ET).timestamp() + 1800.0)):
        sx.SportsBridgeExecutor.__new__(sx.SportsBridgeExecutor)._process_user(user, picks)


# ── 1. no repeated orders ────────────────────────────────────────────────────

def test_ambiguous_live_sports_order_is_never_resent():
    user = _user()
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-A"
    ambiguous = {"success": False, "ambiguous": True, "client_order_id": "cid-1", "error": "timed out"}
    kt = _kt([ambiguous, ambiguous])
    _run(user, [_pick(ticker)], kt)
    _run(user, [_pick(ticker)], kt)  # next 60s cycle
    assert kt.place_sports_order.call_count == 1


def test_clean_rejection_may_be_retried_next_cycle():
    user = _user()
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-B"
    rejected = {"success": False, "error": "Kalshi Order Unfilled"}
    kt = _kt([rejected, rejected])
    _run(user, [_pick(ticker)], kt)
    _run(user, [_pick(ticker)], kt)
    assert kt.place_sports_order.call_count == 2


def test_filled_market_is_not_bought_again_after_the_trade_closes():
    user = _user()
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-C"
    filled = {"success": True, "count": 5, "filled_price": 0.51, "client_order_id": f"cid-{uuid.uuid4().hex[:6]}"}
    kt = _kt([filled, filled])
    _run(user, [_pick(ticker)], kt)
    trade = TradeStore.get_trade_by_id(filled["client_order_id"])
    TradeStore.close_if_open(user["id"], trade, {"exit_price": 1.0, "pnl": 2.0, "exit_reason": "SETTLEMENT"})
    _run(user, [_pick(ticker)], kt)
    assert kt.place_sports_order.call_count == 1


def test_ambiguous_order_counts_against_the_cycle_caps():
    user = _user(sports_max_open_trades=1)
    t1 = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-D"
    t2 = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-E"
    kt = _kt([{"success": False, "ambiguous": True, "error": "dropped"},
              {"success": True, "count": 5, "filled_price": 0.5, "client_order_id": "x"}])
    _run(user, [_pick(t1), _pick(t2)], kt)
    assert kt.place_sports_order.call_count == 1


# ── 2. reconciliation ────────────────────────────────────────────────────────

def test_uncertain_order_that_filled_is_recorded_once():
    user = _user()
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-F"
    key = order_intents.account_key_for_user(user["id"])
    it = sx._sports_intent_ticker(ticker)
    assert order_intents.claim(key, it, "yes")
    order_intents.mark(key, it, "ambiguous", "cid-recon-" + uuid.uuid4().hex[:6])
    kt = _kt([])
    kt.get_positions.return_value = {"success": True, "positions": [
        {"ticker": ticker, "position": 7, "market_exposure_dollars": "3.57"}]}
    with patch.object(order_intents, "time") as fake_time:  # make the claim look old enough
        import time as _t
        fake_time.time.return_value = _t.time() + 120
        executor = sx.SportsBridgeExecutor.__new__(sx.SportsBridgeExecutor)
        executor._reconcile_uncertain_sports_orders(user, kt)
        executor._reconcile_uncertain_sports_orders(user, kt)
    rows = [t for t in TradeStore.get_open_trades(user["id"]) if t.get("ticker") == ticker]
    assert len(rows) == 1
    assert rows[0]["count"] == 7 and rows[0]["entry_price"] == pytest.approx(0.51)
    assert order_intents.get(key, it)["state"] == "filled_reconciled"


# ── 3. sizing ────────────────────────────────────────────────────────────────

def test_sizing_keeps_worst_case_cost_plus_fee_inside_the_wager():
    n, worst = sx._size_sports_order(10.0, 0.60)
    assert n > 0
    assert n * 0.64 + kalshi_order_fee(0.64, n) <= 10.0
    assert worst <= 10.0


def test_wager_too_small_for_one_contract_is_skipped_not_forced():
    assert sx._size_sports_order(0.50, 0.70) == (0, 0.0)


def test_paper_sports_entry_deducts_the_fee():
    user = _user(mode="PAPER")
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-G"
    with patch.object(sx, "deduct_user_paper_balance", return_value=True) as deduct:
        _run(user, [_pick(ticker)], _kt([]))
    n, _ = sx._size_sports_order(10.0, 0.50)
    assert deduct.call_args.args[1] == pytest.approx(round(0.50 * n + kalshi_order_fee(0.50, n), 2))


# ── 4. settle once ───────────────────────────────────────────────────────────

def test_paper_win_is_credited_exactly_once():
    user = _user(mode="PAPER")
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-H"
    trade = {"id": f"t-{uuid.uuid4().hex[:8]}", "ticker": ticker, "side": "YES", "entry_price": 0.40,
             "count": 5, "status": "OPEN", "mode": "PAPER", "trading_style": "SPORTS_AI", "sport": "NFL"}
    TradeStore.insert_trade(user["id"], trade)
    settled = {"status": "settled", "result": "yes", "cur_price": 1.0}
    executor = sx.SportsBridgeExecutor.__new__(sx.SportsBridgeExecutor)
    with patch.object(sx, "_check_kalshi_settlement", return_value=settled), \
         patch.object(sx, "credit_user_paper_balance") as credit:
        executor._settle_open_trades(user)
        executor._settle_open_trades(user)
    credit.assert_called_once_with(user["id"], 5.0)
    stored = TradeStore.get_trade_by_id(trade["id"])
    assert stored["status"] == "CLOSED"
    assert stored["pnl"] == pytest.approx(round((1.0 - 0.40) * 5 - kalshi_order_fee(0.40, 5), 4))


def test_live_take_profit_without_kalshi_session_leaves_trade_open():
    user = _user(mode="LIVE", sports_tp_enabled=1, sports_tp_pct=10.0)
    ticker = f"KXNFLGAME-{uuid.uuid4().hex[:6].upper()}-I"
    trade = {"id": f"t-{uuid.uuid4().hex[:8]}", "ticker": ticker, "side": "YES", "entry_price": 0.40,
             "count": 5, "status": "OPEN", "mode": "LIVE", "trading_style": "SPORTS_AI", "sport": "NFL"}
    TradeStore.insert_trade(user["id"], trade)
    executor = sx.SportsBridgeExecutor.__new__(sx.SportsBridgeExecutor)
    with patch.object(sx, "_check_kalshi_settlement", return_value={"status": "open", "cur_price": 0.60}), \
         patch("backend.btc.kalshi_trader.get_authenticated_trader_for_user", return_value=None):
        executor._settle_open_trades(user)
    assert TradeStore.get_trade_by_id(trade["id"])["status"] == "OPEN"
def test_line_mismatch_no_explain():
    # If the requested line is -1.5, but the explainer returns -2.5, the predict client must drop the explanation.
    from backend.sports_bridge.prediction_client import SportsPredictionClient
    
    # Mock httpx responses
    def _mock_get(url, *args, **kwargs):
        class MockResp:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code
            def json(self): return self._json
            
        if "/explain" in url and "narrative" not in url:
            # Explainer returns mismatched line
            return MockResp({"market": "spread", "line": "-2.5"})
        return MockResp({})
        
    client = SportsPredictionClient()
    client.client.get = _mock_get
    
    best_match = {"sport": "MLB", "market_type": "SPREAD", "line": "-1.5", "metadata": {"game_id": "game-123"}, "predicted_team": "Team A"}
    client.fetch_latest_picks = lambda *a, **k: [best_match]
    client._match_kalshi_event_to_predictions = lambda t, ti, p: best_match
    
    res = client.predict_for_event("KXMLB-123", "Team A vs Team B", "MLB")
    assert res is not None
    assert "explain" not in res.get("metadata", {})


def test_explain_cache_hit():
    from backend.sports_bridge.prediction_client import SportsPredictionClient, _EXPLAIN_CACHE, _EXPLAIN_CACHE_LOCK
    import time
    
    client = SportsPredictionClient()
    key = "mlb_game-123_moneyline__team a"
    with _EXPLAIN_CACHE_LOCK:
        _EXPLAIN_CACHE[key] = (time.time(), {"market": "moneyline", "line": "", "cached": True})
        
    called = [False]
    def _mock_get(url, *args, **kwargs):
        called[0] = True
        class MockResp:
            def __init__(self, json_data): self._json = json_data; self.status_code = 200
            def json(self): return self._json
        return MockResp({})
    client.client.get = _mock_get
    
    best_match = {"sport": "MLB", "market_type": "MONEYLINE", "metadata": {"game_id": "game-123"}, "predicted_team": "Team A"}
    client.fetch_latest_picks = lambda *a, **k: [best_match]
    client._match_kalshi_event_to_predictions = lambda t, ti, p: best_match
    
    res = client.predict_for_event("KXMLB-123", "Team A vs Team B", "MLB")
    
    assert res is not None
    assert "explain" in res["metadata"]
    assert res["metadata"]["explain"].get("cached") is True
    assert called[0] is False

def test_explain_narrative_never_blocks():
    from backend.sports_bridge.prediction_client import SportsPredictionClient
    import time
    
    client = SportsPredictionClient()
    def _mock_get(url, *args, **kwargs):
        class MockResp:
            def __init__(self, json_data, status_code=200):
                self._json = json_data
                self.status_code = status_code
            def json(self): return self._json
            
        if "narrative" in url:
            time.sleep(1.0)  # Simulate slow narrative API
            return MockResp({"narrative": "Done"})
        return MockResp({"market": "moneyline", "line": ""})
        
    client.client.get = _mock_get
    best_match = {"sport": "MLB", "market_type": "MONEYLINE", "metadata": {"game_id": "game-123"}, "predicted_team": "Team A"}
    client.fetch_latest_picks = lambda *a, **k: [best_match]
    client._match_kalshi_event_to_predictions = lambda t, ti, p: best_match
    
    start = time.time()
    res = client.predict_for_event("KXMLB-123", "Team A vs Team B", "MLB")
    elapsed = time.time() - start
    
    assert res is not None
    assert elapsed < 0.5  # Should return instantly without blocking on narrative
    assert "explain" in res["metadata"]
    assert "narrative" not in res["metadata"]["explain"]
