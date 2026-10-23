import re

with open('backend/routes/engine.py', 'r') as f:
    engine_code = f.read()

# First replace the slate_time_str logic in api_sports_events
target = """                    slate_time_str = None
                    title_clean = re.sub(r'[^a-zA-Z0-9]', '', title).lower()
                    if title_clean in slate_map.get(sport_tag, {}):
                        slate_time_str = slate_map.get(sport_tag, {}).get(title_clean)
                    else:
                        for token in re.split(r'\s+(?:vs\.?|at|@)\s+', title, flags=re.IGNORECASE):
                            token = re.sub(r'Game\s+\d+:\s*', '', token, flags=re.IGNORECASE)
                            t_clean = re.sub(r'[^a-zA-Z0-9]', '', token).lower()
                            if t_clean in slate_map.get(sport_tag, {}):
                                slate_time_str = slate_map.get(sport_tag, {}).get(t_clean)
                                break
                            # fallback mascot matching
                            for m_word in ["sox", "jays"]:
                                if t_clean.endswith(m_word):
                                    if t_clean[-8:] in slate_map.get(sport_tag, {}): slate_time_str = slate_map.get(sport_tag, {}).get(t_clean[-8:])
                                    break
                            if not slate_time_str:
                                for p in re.split(r'[^a-zA-Z0-9]', token):
                                    p_clean = p.lower().strip()
                                    if len(p_clean) > 2 and p_clean in slate_map.get(sport_tag, {}):
                                        slate_time_str = slate_map.get(sport_tag, {}).get(p_clean)
                                        break
    
                                
                    ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=e, slate_time_str=slate_time_str)"""

target = target.replace('slate_map', 'milestone_map') # Because we did that in previous script!
replacement = """                    milestone = milestone_map.get(event_ticker)
                    
                    ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=e, milestone=milestone)"""
engine_code = engine_code.replace(target, replacement)

with open('backend/routes/engine.py', 'w') as f:
    f.write(engine_code)
