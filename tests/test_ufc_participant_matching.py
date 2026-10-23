import pytest
import requests
from backend.routes.engine_sports import _get_fighter_surname, _surname_match

def test_ufc_fighter_surname_extraction():
    assert _get_fighter_surname("Allen Rocky Frye Jr.") == "frye"
    assert _get_fighter_surname("Kai Kamaka III") == "kamaka"
    assert _get_fighter_surname("Brendan Allen") == "allen"
    assert _get_fighter_surname("RJ Harris") == "harris"
    assert _get_fighter_surname("Felipe Franco") == "franco"
    assert _get_fighter_surname("Brendson Ribeiro") == "ribeiro"
    assert _get_fighter_surname("Christian Leroy Duncan") == "duncan"
    assert _get_fighter_surname("Melissa Gatto") == "gatto"
    assert _get_fighter_surname("Ernesta Kareckaite") == "kareckaite"
    assert _get_fighter_surname("Daria Zhelezniakova") == "zhelezniakova"

def test_ufc_surname_matching():
    # Exact match
    assert _surname_match("frye", "frye")
    assert _surname_match("allen", "allen")
    
    # Transliteration / minor variation
    assert _surname_match("zhelezniakova", "zheleznyakova")
    
    # First name vs Surname should NOT match
    assert not _surname_match("frye", "allen")
    assert not _surname_match("franco", "allen")
    assert not _surname_match("ribeiro", "allen")

def test_ufc_live_endpoint_attachment():
    try:
        r = requests.get("http://127.0.0.1:8058/api/engine/sports/events?public=1&sport=UFC", timeout=5)
    except Exception as exc:
        pytest.skip(f"Live server on 8058 not reachable: {exc}")
        
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    
    events = data.get("events", [])
    ufc_bouts = [e for e in events if str(e.get("event_ticker", "")).startswith("KXUFCFIGHT-")]
    assert len(ufc_bouts) >= 1, f"Expected 12 UFC bouts, found {len(ufc_bouts)}"
    
    attached_bouts = {}
    for ev in ufc_bouts:
        ticker = ev.get("event_ticker")
        pred_team = ev.get("predicted_team")
        pred = ev.get("ai_prediction") or {}
        attached_bouts[ticker] = pred_team
        
        # Every fight with markets must have its prediction attached
        assert pred_team is not None, f"Event {ticker} missing predicted_team"
        assert pred.get("confidence_pct") is not None, f"Event {ticker} missing confidence_pct"
        
    # Verify specific critical fights
    if "KXUFCFIGHT-26OCT10FRYHAR" in attached_bouts: assert attached_bouts["KXUFCFIGHT-26OCT10FRYHAR"] == "RJ Harris"
    if "KXUFCFIGHT-26OCT10FRARIB" in attached_bouts: assert attached_bouts["KXUFCFIGHT-26OCT10FRARIB"] == "Brendson Ribeiro"
    if "KXUFCFIGHT-26OCT10ALLDUN" in attached_bouts: assert attached_bouts["KXUFCFIGHT-26OCT10ALLDUN"] in ("Christian Leroy Duncan", "Brendan Allen")
