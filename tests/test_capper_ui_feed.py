import pytest
from backend.routes.engine_sports import fetch_sports_events_data

def test_capper_fields_in_sports_feed():
    """Verify that sports events with AI predictions include Master Capper conviction grades and Net EV."""
    events = fetch_sports_events_data(query_filter="ALL")
    assert isinstance(events, list)
    
    ai_events = [e for e in events if e.get("has_ai_prediction")]
    assert len(ai_events) > 0, "Expected active AI events in the sports feed"
    
    # Check that capper data is attached
    sample = ai_events[0]
    assert "capper" in sample
    assert "capper_grade" in sample
    assert "capper_stars" in sample
    assert "capper_tier" in sample
    assert "net_ev_pct" in sample
    assert "kelly_bankroll_pct" in sample
    
    # Check metadata integrity
    assert "capper" in sample["metadata"]
    assert sample["capper_grade"] in ("A+", "A", "B+", "B", "F")
    assert isinstance(sample["capper"], dict)
    assert "capper_thesis" in sample["capper"]
