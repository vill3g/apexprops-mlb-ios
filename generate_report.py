import requests
import json

try:
    print("Fetching events from 8058...")
    d = requests.get('http://127.0.0.1:8058/api/engine/sports/events?public=1', timeout=120).json()
    events = d.get('events', [])
    
    # Soccer and MLB pick counts
    soccer_picks = [e for e in events if e.get('sport') == 'SOCCER' and e.get('has_ai_prediction')]
    mlb_picks = [e for e in events if e.get('sport') == 'MLB' and e.get('has_ai_prediction')]
    
    print(f"Soccer Pick Count: {len(soccer_picks)}")
    print(f"MLB Pick Count: {len(mlb_picks)}")
    
    # Confidence spread per sport
    print("\nConfidence spread per sport:")
    conf_by_sport = {}
    for e in events:
        if e.get('has_ai_prediction'):
            sport = e.get('sport', 'UNKNOWN')
            conf = e.get('ai_prediction_confidence')
            if conf is not None:
                if sport not in conf_by_sport:
                    conf_by_sport[sport] = []
                conf_by_sport[sport].append(conf)
    
    for sport, confs in conf_by_sport.items():
        min_c = min(confs)
        max_c = max(confs)
        avg_c = sum(confs) / len(confs)
        print(f"  {sport}: {len(confs)} picks, Range: {min_c:.1f}% - {max_c:.1f}%, Avg: {avg_c:.1f}%")
        
    # Picks whose team isn't in the event
    # e.g., the title is "Team A vs Team B" and the predicted team is neither.
    print("\nMismatched Picks Analysis:")
    mismatch_count = 0
    for e in events:
        if e.get('has_ai_prediction'):
            pred_team = str(e.get('ai_predicted_team') or '').lower()
            title = str(e.get('title') or '').lower()
            matchup = str(e.get('matchup') or '').lower()
            
            if pred_team:
                clean_pred = pred_team.replace(" team", "").strip()
                if clean_pred not in title and clean_pred not in matchup:
                    found_in_milestone = False
                    if e.get('milestone'):
                        ms = e.get('milestone')
                        if clean_pred in str(ms.get('home_team_name')).lower() or \
                           clean_pred in str(ms.get('away_team_name')).lower() or \
                           clean_pred == str(ms.get('home_team_abbr')).lower() or \
                           clean_pred == str(ms.get('away_team_abbr')).lower():
                            found_in_milestone = True
                            
                    if not found_in_milestone:
                        # Check codes from ticker
                        ticker = e.get('ticker', '').lower()
                        import re
                        m = re.search(r'-[0-9]{2}[a-z]{3}[0-9]{2,4}([a-z]+)', ticker)
                        if m:
                            codes = m.group(1)
                            if len(codes) >= 4:
                                c1 = codes[:len(codes)//2]
                                c2 = codes[len(codes)//2:]
                                if c1 == clean_pred or c2 == clean_pred:
                                    found_in_milestone = True
                                    
                        if not found_in_milestone:
                            mismatch_count += 1
                            print(f"  MISMATCH? Event: {e.get('ticker')} | Title: {e.get('title')} | Pick: {e.get('ai_predicted_team')}")
                        
    print(f"\nTotal mismatched picks (team not in event): {mismatch_count}")
    
except Exception as e:
    print(f"Error generating report: {e}")
