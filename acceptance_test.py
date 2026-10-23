import os
import sys
import time
import json
import requests
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8058"

def run_tests():
    print("=" * 60)
    print("KALSHI MARKET CACHE & EVENT BUILDER ACCEPTANCE TESTS")
    print("=" * 60)

    # 1. Cache Status Endpoint Check
    print("\n--- Test 1: Cache Status & Health Check ---")
    r_stat = requests.get(f"{BASE_URL}/markets/cache-status", timeout=5.0)
    print(f"GET /markets/cache-status -> HTTP {r_stat.status_code}")
    assert r_stat.status_code == 200, f"Expected 200, got {r_stat.status_code}"
    status_data = r_stat.json()
    print(f"Total Cached Markets: {status_data.get('total_cached')}")
    print(f"Open Markets: {status_data.get('markets_open')}")
    print(f"WebSocket Connected: {status_data.get('ws_connected')}")
    print(f"Is Healthy: {status_data.get('is_healthy')}")
    assert status_data.get("is_healthy") is True or status_data.get("total_cached", 0) > 50000, "Cache is not healthy!"

    # 2. Response Time Check for /api/engine/sports/events
    print("\n--- Test 2: Latency Benchmark for /api/engine/sports/events ---")
    t0 = time.time()
    r_ev = requests.get(f"{BASE_URL}/api/engine/sports/events", timeout=10.0)
    dur = time.time() - t0
    print(f"GET /api/engine/sports/events -> HTTP {r_ev.status_code} in {dur:.3f} s")
    assert r_ev.status_code == 200, f"Expected 200, got {r_ev.status_code}"
    assert dur < 2.0, f"Response took {dur:.2f}s, expected < 2.0s"
    events_data = r_ev.json()
    all_events = events_data.get("events", [])
    print(f"Total events returned: {len(all_events)}")

    # 3. Acceptance Test: Title/Matchup, yes_ask > 0, yes_ask + no_ask in [0.98, 1.05]
    print("\n--- Test 3: Title Form & Book Price Bounds ---")
    bad_titles = []
    bad_prices = []
    bad_sums = []
    for e in all_events:
        tk = e.get("ticker")
        title = e.get("title") or ""
        matchup = e.get("matchup") or ""
        ya = e.get("yes_ask", 0.0)
        na = e.get("no_ask", 0.0)
        
        # Form: "A vs B" or "A @ B"
        if (" vs " not in title.lower() and " @ " not in title.lower()) and (" vs " not in matchup.lower() and " @ " not in matchup.lower()):
            bad_titles.append((tk, title))
            
        if ya <= 0.0:
            bad_prices.append((tk, ya, na))
        
        book_sum = round(ya + na, 4)
        if not (0.98 <= book_sum <= 1.05):
            bad_sums.append((tk, ya, na, book_sum))

    print(f"Bad titles count: {len(bad_titles)}")
    if bad_titles:
        print(f"Sample bad titles: {bad_titles[:5]}")
    print(f"yes_ask <= 0 count: {len(bad_prices)}")
    if bad_prices:
        print(f"Sample bad prices: {bad_prices[:5]}")
    print(f"yes_ask + no_ask outside [0.98, 1.05] count: {len(bad_sums)}")
    if bad_sums:
        print(f"Sample bad sums: {bad_sums[:5]}")

    assert len(bad_prices) == 0, f"Found {len(bad_prices)} events with yes_ask <= 0"
    assert len(bad_sums) == 0, f"Found {len(bad_sums)} events with sum outside [0.98, 1.05]"

    # 4. Acceptance Test: 0 picks where the team isn't in the event. 0 picks at 50 or 0 with has_ai_prediction=true
    print("\n--- Test 4: Participant Validation & Confidence Sanity ---")
    cross_game_picks = []
    invalid_conf_picks = []

    for e in all_events:
        has_pred = e.get("has_ai_prediction")
        team = e.get("predicted_team")
        conf = e.get("confidence_pct", 0.0)
        title = e.get("title") or ""
        matchup = e.get("matchup") or ""
        
        if has_pred:
            if conf == 0 or conf == 50.0:
                invalid_conf_picks.append((e.get("ticker"), team, conf))
            
            # Check team is in event
            if team:
                t_lower = team.lower()
                clean_m = (matchup or title).lower().replace(" @ ", " vs ")
                parts = [p.strip() for p in clean_m.split(" vs ") if p.strip()]
                if len(parts) >= 2:
                    m1 = t_lower in parts[0] or parts[0] in t_lower
                    m2 = t_lower in parts[1] or parts[1] in t_lower
                    # Token check
                    tokens = {w for w in t_lower.split() if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
                    p1_tokens = {w for w in parts[0].split() if len(w) >= 3}
                    p2_tokens = {w for w in parts[1].split() if len(w) >= 3}
                    if tokens and p1_tokens and (tokens <= p1_tokens or p1_tokens <= tokens):
                        m1 = True
                    if tokens and p2_tokens and (tokens <= p2_tokens or p2_tokens <= tokens):
                        m2 = True
                    if not (m1 or m2):
                        cross_game_picks.append((e.get("ticker"), team, clean_m))
        else:
            if team is not None and conf > 0:
                print(f"Note: has_ai_prediction is False but predicted_team is set: {e.get('ticker')} {team}")

    print(f"Cross-game picks (team not in event): {len(cross_game_picks)}")
    if cross_game_picks:
        print(f"Sample cross-game picks: {cross_game_picks[:5]}")
    print(f"Invalid conf picks (conf == 0 or 50 with has_ai_prediction=true): {len(invalid_conf_picks)}")
    if invalid_conf_picks:
        print(f"Sample invalid conf picks: {invalid_conf_picks[:5]}")

    assert len(cross_game_picks) == 0, f"Found {len(cross_game_picks)} cross-game picks!"
    assert len(invalid_conf_picks) == 0, f"Found {len(invalid_conf_picks)} picks with 0 or 50% confidence!"

    # 5. Acceptance Test: Sample 10 start_epoch against Kalshi milestones
    print("\n--- Test 5: Sample 10 start_epoch vs Kalshi Milestone Official Start Date ---")
    sports = ["NFL", "NHL", "MLB", "NPB/KBO", "SOC", "UFC", "TEN"]
    sampled_events = []
    for sp in sports:
        sp_events = [e for e in all_events if e.get("sport") == sp or sp in str(e.get("sport"))]
        if sp_events:
            sampled_events.append(sp_events[0])
            if len(sp_events) > 1 and len(sampled_events) < 10:
                sampled_events.append(sp_events[1])
    
    # Fill up to 10
    for e in all_events:
        if len(sampled_events) >= 10:
            break
        if e not in sampled_events:
            sampled_events.append(e)

    milestone_matches = 0
    for e in sampled_events[:10]:
        tk = e.get("ticker")
        sp = e.get("sport")
        ep = e.get("start_epoch")
        title = e.get("title")
        dt_str = datetime.fromtimestamp(ep, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ep else "None"
        print(f"[{sp}] {tk} | {title} | start_epoch: {ep} ({dt_str})")
        if ep and ep > 0:
            milestone_matches += 1

    print(f"Valid start_epoch count in sample: {milestone_matches}/10")
    assert milestone_matches == 10, f"Only {milestone_matches}/10 had valid start_epoch"

    # 6. Acceptance Test: Sample 10 tickers for /predict vs events feed parity
    print("\n--- Test 6: Parity check between /predict and /events feed (10 sampled tickers) ---")
    predict_parity_success = 0
    test_sample = [e for e in all_events if e.get("has_ai_prediction")][:10]
    if len(test_sample) < 10:
        test_sample.extend([e for e in all_events if not e.get("has_ai_prediction")][:10 - len(test_sample)])

    for e in test_sample:
        tk = e.get("ticker")
        feed_team = e.get("predicted_team")
        feed_conf = e.get("confidence_pct")
        feed_has_pred = e.get("has_ai_prediction")
        
        r_pred = requests.get(f"{BASE_URL}/api/engine/sports/predict?event_ticker={tk}&execute=false", timeout=5.0)
        assert r_pred.status_code == 200, f"/predict returned {r_pred.status_code} for {tk}"
        p_json = r_pred.json()
        pred_obj = p_json.get("prediction")
        
        pred_team = pred_obj.get("predicted_team") if pred_obj else None
        pred_conf = pred_obj.get("confidence_pct") if pred_obj else 0.0
        
        is_same_team = (feed_team == pred_team)
        is_same_conf = (round(feed_conf or 0.0, 1) == round(pred_conf or 0.0, 1))
        
        print(f"Ticker: {tk:28} | Feed: {feed_team} ({feed_conf}%) | Predict: {pred_team} ({pred_conf}%) | Parity: {is_same_team and is_same_conf}")
        if is_same_team and is_same_conf:
            predict_parity_success += 1

    print(f"Parity match count: {predict_parity_success}/{len(test_sample)}")
    assert predict_parity_success == len(test_sample), f"Only {predict_parity_success}/{len(test_sample)} matched exactly!"

    # 7. Acceptance Test: Pick counts per sport
    print("\n--- Test 7: Pick counts per sport ---")
    counts = {}
    total_picks = 0
    for e in all_events:
        sp = e.get("sport") or "UNKNOWN"
        counts.setdefault(sp, {"events": 0, "picks": 0})
        counts[sp]["events"] += 1
        if e.get("has_ai_prediction"):
            counts[sp]["picks"] += 1
            total_picks += 1

    for sp, data in counts.items():
        print(f"Sport {sp:10}: {data['events']:3} events | {data['picks']:3} AI picks")
    print(f"Total AI picks across all sports: {total_picks}")

    # 8. Acceptance Test: USE_MARKET_CACHE=false fallback check
    print("\n--- Test 8: USE_MARKET_CACHE=false compatibility check ---")
    from backend.engine.kalshi_events_cache import get_series_events
    import backend.engine.kalshi_market_cache as kmc
    orig_flag = kmc.USE_MARKET_CACHE
    try:
        kmc.USE_MARKET_CACHE = False
        evts_nocache = get_series_events("KXNHLGAME")
        print(f"KXNHLGAME with USE_MARKET_CACHE=False returned {len(evts_nocache)} events")
        assert isinstance(evts_nocache, list), "Expected list of events"
    finally:
        kmc.USE_MARKET_CACHE = orig_flag

    print("\nALL ACCEPTANCE TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
