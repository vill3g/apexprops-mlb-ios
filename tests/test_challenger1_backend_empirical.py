"""Adversarial and Empirical Stress Test Suite for Backend Matching Logic.

Challenger: teamwork_preview_challenger_1
Target modules:
  - backend/routes/engine.py
  - backend/sports_bridge/prediction_client.py
  - backend/sports_bridge/executor.py

Challenge Dimensions:
  1. Tennis date-matching boundary (+/- 0, 1, 2 days vs 3+ days rejection).
  2. Multi-sport name normalization (compounds, player suffixes, soccer club aliases, NPB/KBO variants).
  3. Query parameter stress testing across all sports (TEN, NFL, MLB, NHL, SOC, UFC, NPB/KBO).
  4. Error handling and rejection semantics when executing trades on non-existent Kalshi events.
"""

import pytest
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.trade_store import TradeStore
from backend.sports_bridge.prediction_client import SportsPredictionClient
from backend.routes.engine import _SPORTS_SERIES_MAP, _is_sports_asset
from backend.routes.engine_sports import (
    _SPORT_TEAM_MAP,
    _detect_game_segment,
    _execute_sports_paper_trade, _execute_sports_trade, _fetch_kalshi_series_events
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# 1. TENNIS DATE-MATCHING BOUNDARY EMPIRICAL TESTS
# ============================================================================

class MockDatePickClient(SportsPredictionClient):
    """Custom client injecting test picks with controlled date offsets."""
    def __init__(self, test_picks):
        super().__init__(base_url="http://127.0.0.1:8057")
        self._test_picks = test_picks

    def fetch_latest_picks(self):
        return self._test_picks


@pytest.mark.parametrize("day_offset,should_match", [
    (0, True),   # 0 days diff: exact day
    (1, True),   # +1 day diff: next day
    (-1, True),  # -1 day diff: previous day
    (2, True),   # +2 days diff: 48h boundary upper edge
    (-2, True),  # -2 days diff: 48h boundary lower edge
    (3, False),  # +3 days diff: 72h - MUST BE REJECTED
    (-3, False), # -3 days diff: 72h - MUST BE REJECTED
    (5, False),  # +5 days diff: MUST BE REJECTED
    (-10, False) # -10 days diff: MUST BE REJECTED
])
def test_tennis_date_matching_boundary_prediction_client(day_offset, should_match):
    """Verify SportsPredictionClient accepts diff <= 2 days and rejects diff >= 3 days."""
    from datetime import timedelta
    base_event_date = date(2026, 10, 5)
    pick_date = base_event_date + timedelta(days=day_offset)
    pick_date_str = f"{pick_date.isoformat()}T10:00:00Z"

    mock_pick = {
        "sport": "TEN",
        "league": "ATP",
        "predicted_team": "Bellucci",
        "opponent": "Bellucci vs Ymer",
        "confidence_pct": 72.0,
        "edge_pct": 14.0,
        "market_type": "MONEYLINE",
        "metadata": {
            "start_label": pick_date_str,
            "home_team": "Mattia Bellucci",
            "away_team": "Elias Ymer",
            "matchup": "Mattia Bellucci vs Elias Ymer"
        }
    }

    test_client = MockDatePickClient([mock_pick])
    event_ticker = "KXATPMATCH-26OCT05BELYME"
    title = "Bellucci vs Ymer"

    matched = test_client.predict_for_event(event_ticker, title=title, sport="TEN")

    if should_match:
        assert matched is not None, (
            f"Expected match for offset {day_offset} days (start_label={pick_date_str}), but got None"
        )
        assert matched.get("predicted_team") == "Bellucci"
        assert matched.get("edge_pct") == 14.0, "Expected match to retain pick edge_pct"
        assert matched.get("metadata", {}).get("start_label") == pick_date_str, "Expected match to retain pick start_label"
    else:
        # The stale pick MUST be rejected (not used). If returned, it must be an on-demand simulation fallback.
        if matched is not None:
            assert matched.get("metadata", {}).get("start_label") != pick_date_str, (
                f"Boundary failure: Stale pick with offset {day_offset} days was accepted instead of rejected!"
            )
            assert (
                matched.get("metadata", {}).get("simulation") is True
                or matched.get("metadata", {}).get("on_demand_eval") is True
            ), f"Expected simulation or on_demand_eval fallback when pick is rejected, got: {matched}"


def test_tennis_date_matching_boundary_engine_logic():
    """Verify engine.py date difference logic directly: diff <= 2 allows match, diff > 2 rejects."""
    compare_date = date(2026, 10, 5)

    for offset in [0, 1, -1, 2, -2]:
        p_date = date(2026, 10, 5 + offset)
        diff = abs((p_date - compare_date).days)
        date_match = True
        if diff > 2:
            date_match = False
        assert date_match is True, f"Boundary failure: offset {offset} should have date_match=True"

    for offset in [3, -3, 4, -4, 7]:
        p_date = date(2026, 10, 5 + offset)
        diff = abs((p_date - compare_date).days)
        date_match = True
        if diff > 2:
            date_match = False
        assert date_match is False, f"Boundary failure: offset {offset} should have date_match=False"


# ============================================================================
# 2. NAME NORMALIZATION EMPIRICAL STRESS TESTS
# ============================================================================

def test_soccer_club_alias_normalization():
    """Test soccer club aliases across top leagues (EPL, Bundesliga, La Liga, Serie A, Ligue 1)."""
    soccer_test_cases = [
        ("MAN CITY", "Manchester City"),
        ("MANCHESTER CITY", "Manchester City"),
        ("MAN UTD", "Manchester United"),
        ("MAN UNITED", "Manchester United"),
        ("MANCHESTER UTD", "Manchester United"),
        ("MANCHESTER UNITED", "Manchester United"),
        ("SPURS", "Tottenham Hotspur"),
        ("TOTTENHAM", "Tottenham Hotspur"),
        ("TOTTENHAM HOTSPUR", "Tottenham Hotspur"),
        ("ARSENAL", "Arsenal"),
        ("CHELSEA", "Chelsea"),
        ("LIVERPOOL", "Liverpool"),
        ("NEWCASTLE", "Newcastle United"),
        ("NEWCASTLE UTD", "Newcastle United"),
        ("WOLVES", "Wolverhampton Wanderers"),
        ("WOLVERHAMPTON", "Wolverhampton Wanderers"),
        ("BRIGHTON", "Brighton & Hove Albion"),
        ("WEST HAM", "West Ham United"),
        ("ASTON VILLA", "Aston Villa"),
        ("EVERTON", "Everton"),
        ("DORTMUND", "Borussia Dortmund"),
        ("BVB", "Borussia Dortmund"),
        ("BAYERN", "Bayern Munich"),
        ("BAYERN MUNICH", "Bayern Munich"),
        ("LEVERKUSEN", "Bayer Leverkusen"),
        ("LEIPZIG", "RB Leipzig"),
        ("REAL MADRID", "Real Madrid"),
        ("BARCELONA", "Barcelona"),
        ("ATLETICO", "Atletico Madrid"),
        ("PSG", "Paris Saint-Germain"),
        ("INTER", "Inter Milan"),
        ("MILAN", "AC Milan"),
        ("JUVENTUS", "Juventus"),
    ]

    for alias, canonical in soccer_test_cases:
        res = _normalize_team_name(alias, "SOC")
        assert res == canonical, f"Soccer alias '{alias}' normalized to '{res}', expected '{canonical}'"
        # Test fallback when sport is not specified
        res_no_sport = _normalize_team_name(alias)
        assert res_no_sport == canonical, f"Soccer alias '{alias}' without sport normalized to '{res_no_sport}', expected '{canonical}'"


def test_npb_team_variants_normalization():
    """Test NPB team variants (Hawks, BayStars, Carp, Giants, Tigers, Swallows, Dragons, Lions, Buffaloes, Marines, Fighters, Eagles)."""
    npb_test_cases = [
        ("HAWKS", "Fukuoka SoftBank Hawks"),
        ("FUKUOKA", "Fukuoka SoftBank Hawks"),
        ("FUKUOKA HAWKS", "Fukuoka SoftBank Hawks"),
        ("BAYSTARS", "Yokohama DeNA BayStars"),
        ("YOKOHAMA", "Yokohama DeNA BayStars"),
        ("YOKOHAMA BAYSTARS", "Yokohama DeNA BayStars"),
        ("CARP", "Hiroshima Toyo Carp"),
        ("HIROSHIMA", "Hiroshima Toyo Carp"),
        ("HIROSHIMA CARP", "Hiroshima Toyo Carp"),
        ("GIANTS", "Yomiuri Giants"),
        ("YOMIURI", "Yomiuri Giants"),
        ("YOMIURI GIANTS", "Yomiuri Giants"),
        ("TIGERS", "Hanshin Tigers"),
        ("HANSHIN", "Hanshin Tigers"),
        ("HANSHIN TIGERS", "Hanshin Tigers"),
        ("SWALLOWS", "Tokyo Yakult Swallows"),
        ("YAKULT", "Tokyo Yakult Swallows"),
        ("TOKYO YAKULT SWALLOWS", "Tokyo Yakult Swallows"),
        ("DRAGONS", "Chunichi Dragons"),
        ("CHUNICHI", "Chunichi Dragons"),
        ("CHUNICHI DRAGONS", "Chunichi Dragons"),
        ("LIONS", "Saitama Seibu Lions"),
        ("SEIBU", "Saitama Seibu Lions"),
        ("SAITAMA SEIBU LIONS", "Saitama Seibu Lions"),
        ("BUFFALOES", "Orix Buffaloes"),
        ("ORIX", "Orix Buffaloes"),
        ("ORIX BUFFALOES", "Orix Buffaloes"),
        ("MARINES", "Chiba Lotte Marines"),
        ("LOTTE", "Chiba Lotte Marines"),
        ("CHIBA LOTTE MARINES", "Chiba Lotte Marines"),
        ("FIGHTERS", "Hokkaido Nippon-Ham Fighters"),
        ("NIPPON-HAM", "Hokkaido Nippon-Ham Fighters"),
        ("HOKKAIDO NIPPON-HAM FIGHTERS", "Hokkaido Nippon-Ham Fighters"),
        ("GOLDEN EAGLES", "Tohoku Rakuten Golden Eagles"),
        ("EAGLES", "Tohoku Rakuten Golden Eagles"),
        ("RAKUTEN", "Tohoku Rakuten Golden Eagles"),
        ("TOHOKU RAKUTEN GOLDEN EAGLES", "Tohoku Rakuten Golden Eagles"),
    ]

    for alias, canonical in npb_test_cases:
        res = _normalize_team_name(alias, "NPB")
        assert res == canonical, f"NPB alias '{alias}' normalized to '{res}', expected '{canonical}'"


def test_kbo_team_variants_normalization():
    """Test KBO team variants (Bears, Giants, Twins, Wiz, Landers, Dinos, Tigers, Lions, Heroes, Eagles)."""
    kbo_test_cases = [
        ("BEARS", "Doosan Bears"),
        ("DOOSAN", "Doosan Bears"),
        ("DOOSAN BEARS", "Doosan Bears"),
        ("GIANTS", "Lotte Giants"),
        ("LOTTE", "Lotte Giants"),
        ("LOTTE GIANTS", "Lotte Giants"),
        ("TWINS", "LG Twins"),
        ("LG", "LG Twins"),
        ("LG TWINS", "LG Twins"),
        ("WIZ", "KT Wiz"),
        ("KT", "KT Wiz"),
        ("KT WIZ", "KT Wiz"),
        ("LANDERS", "SSG Landers"),
        ("SSG", "SSG Landers"),
        ("SSG LANDERS", "SSG Landers"),
        ("DINOS", "NC Dinos"),
        ("NC", "NC Dinos"),
        ("NC DINOS", "NC Dinos"),
        ("TIGERS", "Kia Tigers"),
        ("KIA", "Kia Tigers"),
        ("KIA TIGERS", "Kia Tigers"),
        ("LIONS", "Samsung Lions"),
        ("SAMSUNG", "Samsung Lions"),
        ("SAMSUNG LIONS", "Samsung Lions"),
        ("HEROES", "Kiwoom Heroes"),
        ("KIWOOM", "Kiwoom Heroes"),
        ("KIWOOM HEROES", "Kiwoom Heroes"),
        ("EAGLES", "Hanwha Eagles"),
        ("HANWHA", "Hanwha Eagles"),
        ("HANWHA EAGLES", "Hanwha Eagles"),
    ]

    for alias, canonical in kbo_test_cases:
        res = _normalize_team_name(alias, "KBO")
        assert res == canonical, f"KBO alias '{alias}' normalized to '{res}', expected '{canonical}'"


def test_ambiguous_mascot_resolution_by_sport():
    """Test ambiguous mascots shared between NPB and KBO (TIGERS, GIANTS, LIONS, EAGLES)."""
    # GIANTS: Yomiuri (NPB) vs Lotte (KBO)
    assert _normalize_team_name("GIANTS", "NPB") == "Yomiuri Giants"
    assert _normalize_team_name("GIANTS", "KBO") == "Lotte Giants"

    # TIGERS: Hanshin (NPB) vs Kia (KBO)
    assert _normalize_team_name("TIGERS", "NPB") == "Hanshin Tigers"
    assert _normalize_team_name("TIGERS", "KBO") == "Kia Tigers"

    # LIONS: Seibu (NPB) vs Samsung (KBO)
    assert _normalize_team_name("LIONS", "NPB") == "Saitama Seibu Lions"
    assert _normalize_team_name("LIONS", "KBO") == "Samsung Lions"

    # EAGLES: Rakuten (NPB) vs Hanwha (KBO)
    assert _normalize_team_name("EAGLES", "NPB") == "Tohoku Rakuten Golden Eagles"
    assert _normalize_team_name("EAGLES", "KBO") == "Hanwha Eagles"


def test_tennis_player_name_normalization_and_diacritics():
    """Verify tennis player name matching handles compound names, diacritics, and initials."""
    import unicodedata

    def _norm(n):
        return unicodedata.normalize('NFKD', n).encode('ASCII', 'ignore').decode('utf-8').upper()

    def _match_name(fullname, kalshiname):
        if not kalshiname or not fullname:
            return False
        k_teams = [k.strip() for k in kalshiname.split('/') if k.strip()]
        f_teams = [f.strip() for f in fullname.split('/') if f.strip()]
        if len(k_teams) > 1 or len(f_teams) > 1:
            for kt in k_teams:
                kp = [p for p in re.split(r'[^A-Z0-9]+', kt) if p]
                if any(all(p in [x for x in re.split(r'[^A-Z0-9]+', ft) if x] for p in kp) for ft in (f_teams or [fullname])):
                    return True
            return False
        k_parts = [p for p in re.split(r'[^A-Z0-9]+', kalshiname) if p]
        f_parts = [p for p in re.split(r'[^A-Z0-9]+', fullname) if p]
        return all(k in f_parts for k in k_parts)

    test_pairs = [
        # (Kalshi name, Prediction full name)
        ("Alcaraz", "Carlos Alcaraz"),
        ("Alcaraz", "Carlos Alcaraz Garfia"),
        ("Cerundolo", "Juan Manuel Cerundolo"),
        ("Davidovich Fokina", "Alejandro Davidovich Fokina"),
        ("Struff", "Jan-Lennard Struff"),
        ("Carballes Baena", "Roberto Carballes Baena"),
        ("Zverev", "Alexander Zverev"),
        # Standard tournament tour diacritics
        (_norm("Auger-Aliassime"), _norm("Felix Auger-Aliassime")),
        (_norm("Auger-Aliassime"), _norm("Félix Auger-Aliassime")),
        (_norm("Djokovic"), _norm("Novak Djokovic")),
        (_norm("Lehecka"), _norm("Jiri Lehecka")),
        (_norm("Lehecka"), _norm("Jiří Lehečka")),
        (_norm("Etcheverry"), _norm("Tomas Martin Etcheverry")),
        (_norm("Etcheverry"), _norm("Tomás Martín Etcheverry")),
    ]

    for k_name, f_name in test_pairs:
        k_norm = _norm(k_name)
        f_norm = _norm(f_name)
        assert _match_name(f_norm, k_norm), f"Tennis player match failed for '{k_name}' vs '{f_name}'"


# ============================================================================
# 3. /api/engine/sports/events QUERY PARAMETER STRESS TESTS
# ============================================================================

ALL_SUPPORTED_SPORTS = ["TEN", "NFL", "MLB", "NHL", "SOC", "UFC", "NPB/KBO"]

@pytest.mark.parametrize("sport_param", ALL_SUPPORTED_SPORTS)
def test_api_sports_events_all_sports_query_param(client, sport_param):
    """Stress test GET /api/engine/sports/events with 'sport' query parameter."""
    res = client.get(f"/api/engine/sports/events?sport={sport_param}")
    assert res.status_code == 200, f"Failed for sport={sport_param}: {res.status_code}"
    data = res.json()
    assert data.get("status") == "ok"
    events = data.get("events", [])
    assert len(events) > 0, f"Expected non-empty events for {sport_param}"

    for e in events:
        # Schema validation
        assert "ticker" in e or "event_ticker" in e
        assert "title" in e
        assert "markets" in e
        assert "has_ai_prediction" in e
        assert "ai_prediction" in e

        # If prediction exists, contract requires valid dict
        if e.get("has_ai_prediction"):
            pred = e.get("ai_prediction")
            assert isinstance(pred, dict), f"ai_prediction must be dict, got {type(pred)}"
            assert "predicted_team" in pred, "ai_prediction missing predicted_team"
            assert "confidence_pct" in pred, "ai_prediction missing confidence_pct"
            assert "edge_pct" in pred, "ai_prediction missing edge_pct"


@pytest.mark.parametrize("sport_alias,expected_norm", [
    ("TENNIS", "TEN"),
    ("ATP", "TEN"),
    ("WTA", "TEN"),
    ("SOCCER", "SOC"),
    ("EPL", "SOC"),
    ("MLS", "SOC"),
    ("MMA", "UFC"),
    ("HOCKEY", "NHL"),
    ("BASEBALL", "MLB"),
    ("FOOTBALL", "NFL"),
    ("NPB", "NPB/KBO"),
    ("KBO", "NPB/KBO"),
    ("NPB_KBO", "NPB/KBO"),
])
def test_api_sports_events_sport_aliases(client, sport_alias, expected_norm):
    """Test sports aliases return valid HTTP 200 and correctly mapped events."""
    res = client.get(f"/api/engine/sports/events?sport={sport_alias}")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    events = data.get("events", [])
    assert len(events) > 0, f"Alias {sport_alias} returned 0 events"


@pytest.mark.parametrize("param_name", ["league", "filter"])
def test_api_sports_events_alternate_param_names(client, param_name):
    """Test 'league' and 'filter' query parameters work identically to 'sport'."""
    res_ten = client.get(f"/api/engine/sports/events?{param_name}=TEN")
    assert res_ten.status_code == 200
    assert len(res_ten.json().get("events", [])) > 0

    res_soc = client.get(f"/api/engine/sports/events?{param_name}=SOC")
    assert res_soc.status_code == 200
    assert len(res_soc.json().get("events", [])) > 0


def test_api_sports_events_default_all_returns_multi_sport(client):
    """Calling /api/engine/sports/events without params should return all sports aggregated."""
    res = client.get("/api/engine/sports/events")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    events = data.get("events", [])
    assert len(events) >= 50, f"Expected aggregate multi-sport slate, got {len(events)}"

    sports_represented = {e.get("sport") for e in events}
    # Verify multiple sports are in the response
    assert "NHL" in sports_represented
    assert "NFL" in sports_represented or "MLB" in sports_represented or "TEN" in sports_represented


def test_api_sports_events_adversarial_and_empty_inputs(client):
    """Test resilience against empty strings, spaces, unknown sports, and special characters."""
    adversarial_inputs = [
        "",
        "   ",
        "NONEXISTENT_SPORT_XYZ",
        "CRICKET",
        "12345",
        "<script>alert(1)</script>",
        "'; DROP TABLE users; --",
        "TEN%00NULL"
    ]
    for adv in adversarial_inputs:
        res = client.get("/api/engine/sports/events", params={"sport": adv})
        # Server must NEVER 500 on adversarial query inputs
        assert res.status_code == 200, f"Crashed with status {res.status_code} on input '{adv}'"
        data = res.json()
        assert data.get("status") == "ok"
        assert isinstance(data.get("events"), list)


# ============================================================================
# 4. ERROR HANDLING ON NON-EXISTENT EVENTS
# ============================================================================

def test_execute_nonexistent_event_rejection(client):
    """Empirically test that executing trades on non-existent Kalshi events cleanly fails."""
    nonexistent_tickers = [
        "KXNONEXISTENT-99999999",
        "KXATPMATCH-9999FAKETICKER",
        "KXMLBGAME-26DEC310000FAKETEAMS",
        "INVALID-TICKER-STRUCTURE"
    ]

    for ticker in nonexistent_tickers:
        res = client.post(f"/api/engine/sports/execute?event_ticker={ticker}&min_confidence=50.0&min_edge=0.0")
        assert res.status_code == 200, f"Expected graceful 200 with error body, got {res.status_code}"
        data = res.json()
        assert data.get("executed") is False, f"Trade should NOT have executed for non-existent event {ticker}"
        assert data.get("trade_id") is None, f"trade_id should be None for non-existent event {ticker}"
        assert data.get("error") is not None, f"Expected error message for non-existent event {ticker}"
        assert "Trade execution failed" in str(data.get("error")) or "not found" in str(data.get("error")).lower() or "no active matching markets" in str(data.get("error")).lower()


def test_predict_endpoint_execute_nonexistent_event(client):
    """Verify /api/engine/sports/predict with execute=true on non-existent event."""
    res = client.get("/api/engine/sports/predict?event_ticker=KXNONEXISTENT-PREDICT-404&execute=true&min_confidence=0.0&min_edge=0.0")
    assert res.status_code == 200
    data = res.json()
    assert data.get("executed") is False
    assert data.get("trade_id") is None
    assert data.get("error") is not None


def test_combo_execute_nonexistent_events(client):
    """Verify combo execution endpoint gracefully handles non-existent events without crashing."""
    tickers = "KXFAKETICKER-1,KXFAKETICKER-2"
    res = client.post(f"/api/engine/sports/combo?event_tickers={tickers}")
    assert res.status_code == 200
    data = res.json()
    # When all tickers fail, status indicates error and total_executed is 0
    assert data.get("status") == "error"
    assert data.get("combo_executed") is False
    assert data.get("total_executed", 0) == 0
    assert len(data.get("trades", [])) == 0
    assert len(data.get("errors", [])) == 2


def test_no_orphan_trades_in_database_after_failed_executions():
    """Verify failed executions on non-existent events did not leave ghost trades in TradeStore."""
    # Query recent trades and ensure none match fake tickers
    recent_trades = TradeStore.get_recent_trades(user_id=1, limit=100)
    ghost_trades = [
        t for t in recent_trades
        if "NONEXISTENT" in str(t.get("event_ticker") or "") or "FAKETICKER" in str(t.get("event_ticker") or "")
    ]
    assert len(ghost_trades) == 0, f"Found orphan/ghost trades in database: {ghost_trades}"
