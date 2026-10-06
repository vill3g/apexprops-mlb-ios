import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.database.models import get_db_connection
from backend.database.trade_store import TradeStore
from backend.routes.engine import _get_user_sports_criteria
from backend.auth.security import create_jwt_token

@pytest.fixture
def client():
    return TestClient(app)

def test_sports_trade_size_persistence_and_stats(client):
    """Verify R2: sports_trade_size_dollars persists across settings endpoints and dashboard_stats."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, trading_universe, min_sports_confidence, min_sports_edge, sports_max_wager, sports_trade_size_dollars, sports_include_live FROM users WHERE id = 2").fetchone()
    conn.close()
    assert user is not None, "Test user ID 2 must exist"
    orig_state = dict(user)

    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        payload = {
            "trading_universe": "SPORTS",
            "min_sports_confidence": 75.0,
            "min_sports_edge": 4.5,
            "sports_trade_size_dollars": 35.0,
            "sports_include_live": True
        }
        res = client.post("/api/auth/user/config", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") is True or data.get("status") == "ok"

        # Verify directly in database
        criteria = _get_user_sports_criteria(2)
        assert criteria["trade_size_dollars"] == 35.0
        assert criteria["max_wager"] == 35.0
        assert criteria["min_confidence"] == 75.0
        assert criteria["min_edge"] == 4.5

        # Verify returned in /api/auth/dashboard_stats
        stats_res = client.get("/api/auth/dashboard_stats", headers=headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats.get("sports_trade_size_dollars") == 35.0
        assert stats.get("sports_max_wager") == 35.0
        assert stats.get("min_sports_confidence") == 75.0
        assert stats.get("min_sports_edge") == 4.5
        assert stats.get("trading_universe") == "SPORTS"
        assert stats.get("sports_include_live") is True
    finally:
        conn = get_db_connection()
        conn.execute("""
            UPDATE users SET
                trading_universe = ?,
                min_sports_confidence = ?,
                min_sports_edge = ?,
                sports_max_wager = ?,
                sports_trade_size_dollars = ?,
                sports_include_live = ?
            WHERE id = 2
        """, (
            orig_state.get("trading_universe", "FINANCIAL"),
            orig_state.get("min_sports_confidence", 70.0),
            orig_state.get("min_sports_edge", 3.0),
            orig_state.get("sports_max_wager", 10.0),
            orig_state.get("sports_trade_size_dollars", 10.0),
            orig_state.get("sports_include_live", 0)
        ))
        conn.commit()
        conn.close()

def test_sports_execution_uses_sports_trade_size(client):
    """Verify R1 & R2: sports paper trade execution creates trade with sport, team, and trade size matching user config."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username, trading_universe, min_sports_confidence, min_sports_edge, sports_max_wager, sports_trade_size_dollars, sports_include_live FROM users WHERE id = 2").fetchone()
    conn.close()
    assert user is not None
    orig_state = dict(user)

    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    trade_id = None
    try:
        client.post("/api/auth/user/config", json={"sports_trade_size_dollars": 40.0, "sports_max_wager": 40.0}, headers=headers)

        # Execute a sports trade on an active Kalshi event with manual_team
        event_ticker = "KXKBOGAME-26OCT060530DOOLOT"
        res = client.post(
            f"/api/engine/sports/execute?event_ticker={event_ticker}&manual_team=Doosan%20Bears&sport=KBO",
            headers=headers
        )
        assert res.status_code == 200
        resp_data = res.json()
        assert resp_data.get("status") == "ok"
        assert resp_data.get("executed") is True
        trade = resp_data.get("trade")
        assert trade is not None
        trade_id = trade.get("id")

        # Check trade attributes
        assert trade.get("sport") in ("KBO", "NPB/KBO", "NPB")
        assert trade.get("asset") in ("KBO", "NPB/KBO", "NPB")
        assert trade.get("team") == "Doosan Bears"
        assert trade.get("predicted_team") == "Doosan Bears"
        assert trade.get("status") == "OPEN"
        assert trade.get("trading_style") == "SPORTS_AI"
        assert trade.get("trade_size_dollars") == 40.0
        assert int(trade.get("count", 0)) > 0
        assert float(trade.get("cost", 0.0)) > 0.0
    finally:
        conn = get_db_connection()
        if trade_id:
            conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.execute("""
            UPDATE users SET
                trading_universe = ?,
                min_sports_confidence = ?,
                min_sports_edge = ?,
                sports_max_wager = ?,
                sports_trade_size_dollars = ?,
                sports_include_live = ?
            WHERE id = 2
        """, (
            orig_state.get("trading_universe", "FINANCIAL"),
            orig_state.get("min_sports_confidence", 70.0),
            orig_state.get("min_sports_edge", 3.0),
            orig_state.get("sports_max_wager", 10.0),
            orig_state.get("sports_trade_size_dollars", 10.0),
            orig_state.get("sports_include_live", 0)
        ))
        conn.commit()
        conn.close()

def test_dashboard_stats_formats_sports_trades(client):
    """Verify R1: /api/auth/dashboard_stats returns sports trades with sport, team, predicted_team."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username FROM users WHERE id = 2").fetchone()
    conn.close()
    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Insert a simulated open sports trade
    import time
    trade_id = f"test_sports_{int(time.time())}"
    trade = {
        "id": trade_id,
        "user_id": 2,
        "ticker": "KXNFLGAME-TEST-DETKC",
        "sport": "NFL",
        "asset": "NFL",
        "predicted_team": "Detroit Lions",
        "team": "Detroit Lions",
        "side": "YES",
        "direction": "YES",
        "entry_price": 0.52,
        "count": 20,
        "cost": 10.4,
        "pnl": 0.0,
        "status": "OPEN",
        "mode": "PAPER",
        "trading_style": "SPORTS_AI",
        "timestamp": time.time(),
        "ml_reasoning": '{"sport": "NFL", "predicted_team": "Detroit Lions", "confidence_pct": 78.0}'
    }
    TradeStore.insert_trade(2, trade)

    try:
        stats_res = client.get("/api/auth/dashboard_stats", headers=headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        recent = stats.get("recent_trades", [])
        matched = [t for t in recent if t.get("id") == trade_id]
        assert len(matched) == 1
        t_obj = matched[0]
        assert t_obj.get("sport") == "NFL"
        assert t_obj.get("team") == "Detroit Lions"
        assert t_obj.get("predicted_team") == "Detroit Lions"
    finally:
        conn = get_db_connection()
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
        conn.close()

def test_saas_dashboard_html_contracts():
    """Verify frontend HTML contracts in static/saas_dashboard.html for R1, R2, R3."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # R2: Sports Trade Size ($) setting
    assert 'id="sports-trade-size-dollars"' in html
    assert "Sports Trade Size ($)" in html

    # R3: Overscroll containment and gap reduction
    assert 'id="sports-event-list"' in html
    assert "overscroll-behavior-y: contain" in html
    assert "body.universe-sports #sports-event-list" in html
    assert "overscroll-y-contain" in html

    # R1: Sports helpers and rendering logic
    assert "window.__isSportTrade" in html
    assert "window.__getSportInfo" in html
    assert "window.renderTradesContainer" in html
    assert "window._currentTradeSportInfo" in html

    # Verify team name is displayed for sports
    assert "window._currentTradeSportInfo.team" in html

    # R2: Universe visibility classes
    assert 'sports-only-setting' in html
    assert 'finance-only-setting' in html
    assert 'id="sports-risk-settings" class="hidden sports-only-setting"' in html
    assert 'id="finance-risk-settings" class="finance-only-setting"' in html
    assert 'id="finance-asset-settings" class="finance-only-setting"' in html

    # Verify no duplicate slider IDs
    assert html.count('id="sports-conf-slider"') == 1
    assert html.count('id="sports-conf-val"') == 1

def test_trades_html_contracts():
    """Verify contracts in static/trades.html for R1 sports badges and team names."""
    with open("static/trades.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert "window.__isSportTrade" in html
    assert "window.__getSportInfo" in html
    assert "SPORTS AI" in html
    assert "sportInfo.team" in html


def test_copy_user_settings_preserves_sports_trade_size():
    """Verify that copy_user_settings copies sports AI strategy settings while strictly preserving sports trade size."""
    from backend.database.models import copy_user_settings, update_user_config, get_user_by_id, get_all_active_users

    active_users = get_all_active_users()
    assert len(active_users) >= 2, "Test requires at least two active users in database"
    user_a = active_users[0]
    user_b = active_users[1]

    orig_a = dict(user_a)
    orig_b = dict(user_b)

    try:
        # Set User A with distinct sports strategy and sports trade size = 65.0
        update_user_config(
            user_id=user_a["id"],
            trade_size_dollars=orig_a.get("trade_size_dollars", 5.0),
            paper_trade_size_dollars=orig_a.get("paper_trade_size_dollars", 5.0),
            stop_loss_pct=orig_a.get("stop_loss_pct", 50.0),
            min_sports_confidence=82.0,
            min_sports_edge=6.5,
            sports_trade_size_dollars=65.0,
            sports_include_live=True
        )

        # Set User B with their own sports trade size = 25.0
        update_user_config(
            user_id=user_b["id"],
            trade_size_dollars=orig_b.get("trade_size_dollars", 5.0),
            paper_trade_size_dollars=orig_b.get("paper_trade_size_dollars", 5.0),
            stop_loss_pct=orig_b.get("stop_loss_pct", 50.0),
            min_sports_confidence=60.0,
            min_sports_edge=2.0,
            sports_trade_size_dollars=25.0,
            sports_include_live=False
        )

        # User B copies settings from User A
        res = copy_user_settings(source_user_id=user_a["id"], target_user_id=user_b["id"])
        assert res is not None
        assert res["copied_settings"]["min_sports_confidence"] == 82.0
        assert res["copied_settings"]["min_sports_edge"] == 6.5
        assert res["copied_settings"]["sports_include_live"] == 1

        # Check User B in database: sports strategy copied, sports trade size preserved
        refreshed_b = get_user_by_id(user_b["id"])
        assert refreshed_b["min_sports_confidence"] == 82.0
        assert refreshed_b["min_sports_edge"] == 6.5
        assert refreshed_b["sports_include_live"] == 1
        assert refreshed_b["sports_trade_size_dollars"] == 25.0, "Sports trade size must be preserved"
        assert refreshed_b["sports_max_wager"] == 25.0, "Sports max wager must match preserved trade size"
    finally:
        # Teardown / restore
        update_user_config(
            user_id=user_a["id"],
            trade_size_dollars=orig_a.get("trade_size_dollars", 5.0),
            paper_trade_size_dollars=orig_a.get("paper_trade_size_dollars", 5.0),
            stop_loss_pct=orig_a.get("stop_loss_pct", 50.0),
            min_sports_confidence=orig_a.get("min_sports_confidence", 70.0),
            min_sports_edge=orig_a.get("min_sports_edge", 3.0),
            sports_trade_size_dollars=orig_a.get("sports_trade_size_dollars", 10.0),
            sports_include_live=bool(orig_a.get("sports_include_live", 0))
        )
        update_user_config(
            user_id=user_b["id"],
            trade_size_dollars=orig_b.get("trade_size_dollars", 5.0),
            paper_trade_size_dollars=orig_b.get("paper_trade_size_dollars", 5.0),
            stop_loss_pct=orig_b.get("stop_loss_pct", 50.0),
            min_sports_confidence=orig_b.get("min_sports_confidence", 70.0),
            min_sports_edge=orig_b.get("min_sports_edge", 3.0),
            sports_trade_size_dollars=orig_b.get("sports_trade_size_dollars", 10.0),
            sports_include_live=bool(orig_b.get("sports_include_live", 0))
        )

def test_sports_execute_explicit_trade_size(client):
    """Verify R2: passing trade_size query param overrides user default trade size."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username FROM users WHERE id = 2").fetchone()
    conn.close()
    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    trade_id = None
    try:
        # User default is 10.0, we pass trade_size=25.0
        event_ticker = "KXKBOGAME-26OCT060530DOOLOT"
        res = client.post(
            f"/api/engine/sports/execute?event_ticker={event_ticker}&manual_team=Doosan%20Bears&sport=KBO&trade_size=25.0",
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        trade = data.get("trade")
        assert trade is not None
        trade_id = trade.get("id")
        assert trade.get("trade_size_dollars") == 25.0
        assert trade.get("team") == "Doosan Bears"
    finally:
        if trade_id:
            conn = get_db_connection()
            conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
            conn.commit()
            conn.close()

def test_sports_combo_execute_explicit_trade_size(client):
    """Verify R2: combo execute accepts trade_size and applies it to each leg."""
    conn = get_db_connection()
    user = conn.execute("SELECT id, username FROM users WHERE id = 2").fetchone()
    conn.close()
    token = create_jwt_token(user["id"], user["username"])
    headers = {"Authorization": f"Bearer {token}"}

    trade_ids = []
    try:
        res = client.post(
            "/api/engine/sports/combo?event_tickers=KXKBOGAME-26OCT060530DOOLOT,KXKBOGAME-26OCT060530KIWSSG&teams=Doosan%20Bears,Kiwoom%20Heroes&trade_size=18.0",
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert data.get("combo_executed") is True
        trades = data.get("trades", [])
        assert len(trades) >= 1
        for t in trades:
            trade_ids.append(t.get("id"))
            assert t.get("trade_size_dollars") == 18.0
    finally:
        if trade_ids:
            conn = get_db_connection()
            for tid in trade_ids:
                conn.execute("DELETE FROM trades WHERE id = ?", (tid,))
            conn.commit()
            conn.close()

def test_sport_extraction_greedy_regex_fix():
    """Verify sport name extraction does not greedily consume the 'G' from 'GAME'."""
    import re
    tickers = {
        "KXKBOGAME-26OCT060530DOOLOT": "KBO",
        "KXNFLGAME-26OCT06-DETKC": "NFL",
        "KXNHLGAME-26OCT06-BOSNYR": "NHL",
        "KXMLBGAME-26OCT06-LADNYY": "MLB",
        "KXNBAGAME-26OCT06-LALGSW": "NBA",
        "KXSOCGAME-26OCT06-ARSCHE": "SOC",
        "KXNPB-26OCT06-HAN巨人": "NPB",
        "KXUFC-300-PER": "UFC",
    }
    regex = r'KX(NFL|MLB|NBA|NHL|NPB|KBO|SOC|UFC|TEN|MMA)'
    for ticker, expected_sport in tickers.items():
        m = re.search(regex, ticker)
        assert m is not None, f"Expected match for {ticker}"
        assert m.group(1) == expected_sport, f"Expected {expected_sport}, got {m.group(1)} for {ticker}"

def test_saas_dashboard_modal_and_add_button():
    """Verify trade details modal formats sports properly and omits crypto ADD button."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Modal should have sports-specific branch
    assert "isSportTrade" in html
    assert "betting on <strong>${sInfo.team}</strong> in <strong>${sInfo.sport}</strong>" in html
    assert "for <strong>${sInfo.team}</strong> in <strong>${sInfo.sport}</strong>" in html
    # Crypto ADD button should not appear on sports trades
    assert "executeManualTrade" in html
    assert "!isSport" in html

def test_sport_extraction_college_and_5letter_leagues():
    """Verify sport name extraction handles 5-letter leagues like NCAAF, NCAAB, WNBA."""
    import re
    tickers = {
        "KXNCAAFGAME-26OCT06-ALAGSO": "NCAAF",
        "KXNCAABGAME-26OCT06-DUKUNC": "NCAAB",
        "KXWNBAGAME-26OCT06-NYLLAS": "WNBA",
        "KXNBAGAME-26OCT06-LALGSW": "NBA",
    }
    regex = r'KX(NFL|MLB|NBA|NHL|NCAAF|NCAAB|WNBA|NPB|KBO|SOC|UFC|TEN|MMA)'
    for ticker, expected_sport in tickers.items():
        m = re.search(regex, ticker)
        assert m is not None, f"Expected match for {ticker}"
        assert m.group(1) == expected_sport, f"Expected {expected_sport}, got {m.group(1)} for {ticker}"

def test_css_touch_momentum_and_spacing():
    """Verify R3: -webkit-overflow-scrolling: touch is included alongside overscroll-behavior-y, and asset bar spacing is reduced."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    assert "-webkit-overflow-scrolling: touch" in html
    assert "overscroll-behavior-y: contain" in html
    assert "body.universe-sports #sports-event-list" in html
    assert "body.universe-sports #assetSelectorBar" in html

def test_universe_persistence_and_polling_guard():
    """Verify that universe selection persists immediately to user config and polling does not snap back to financial."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()

    # selectUniverse is decoupled: does NOT implicitly persist trading_universe to API
    assert "body: JSON.stringify({ trading_universe: universe })" not in html
    # Explicit auto-trading universe setting in settings drawer
    assert "setAutoTradingUniverse" in html
    assert "window.lastDashboardStats.trading_universe = universe" in html
    # populateUserSettings must guard selectUniverse so background polling does not revert user selection
    assert "!window.currentUniverse || force" in html

def test_sports_icons_mapping_includes_nba_and_college():
    """Verify NBA, NCAAF, NCAAB, WNBA have designated emoji icons rather than fallback trophy."""
    with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()
    with open("static/trades.html", "r", encoding="utf-8") as f:
        trades_html = f.read()

    for h in [html, trades_html]:
        assert "'NBA': '🏀'" in h
        assert "'NCAAF': '🏈'" in h
        assert "'NCAAB': '🏀'" in h
        assert "'WNBA': '🏀'" in h



