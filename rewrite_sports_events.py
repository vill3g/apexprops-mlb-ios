import re

with open("backend/routes/engine.py", "r") as f:
    c = f.read()

start_idx = c.find("def api_sports_events(")
end_idx = c.find("def api_sports_predict(")

if start_idx == -1 or end_idx == -1:
    print("Could not find functions")
    exit(1)

new_func = """def api_sports_events(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    filter: Optional[str] = None
):
    try:
        from backend.engine.kalshi_events_cache import get_series_events, get_milestone_map
        from backend.engine.market_matcher import find_best_market_for_pick
        
        raw_filter = sport or league or filter or ""
        if hasattr(raw_filter, "default"):
            raw_filter = ""
        query_filter = str(raw_filter or "").strip().upper()
        now = time.time()
        
        with _SPORTS_AGG_CACHE_LOCK:
            if query_filter in _SPORTS_AGG_CACHE:
                ts, cached_resp = _SPORTS_AGG_CACHE[query_filter]
                if now - ts < _SPORTS_AGG_CACHE_TTL:
                    return cached_resp
    
        if query_filter in ("NPB/KBO", "NPB_KBO", "NPB-KBO", "NPB", "KBO"):
            target_sports = [("NPB", "NPB/KBO", "NPB"), ("KBO", "NPB/KBO", "KBO")]
        elif query_filter in ("SOC", "SOCCER"):
            target_sports = [("SOC", "SOC", "SOC")]
        elif query_filter in ("TEN", "TENNIS"):
            target_sports = [("TEN", "TEN", "TEN")]
        elif query_filter in ("UFC", "MMA"):
            target_sports = [("UFC", "UFC", "UFC")]
        elif query_filter in _SPORTS_SERIES_MAP:
            target_sports = [(query_filter, query_filter, query_filter)]
        else:
            target_sports = [
                ("NPB", "NPB/KBO", "NPB"),
                ("KBO", "NPB/KBO", "KBO"),
                ("NFL", "NFL", "NFL"),
                ("MLB", "MLB", "MLB"),
                ("NHL", "NHL", "NHL"),
                ("SOC", "SOC", "SOC"),
                ("UFC", "UFC", "UFC"),
                ("TEN", "TEN", "TEN"),
            ]
            
        client = SportsPredictionClient()
        latest_picks = []
        try:
            latest_picks = client.fetch_latest_picks()
        except:
            pass
            
        milestone_map = get_milestone_map()
        kalshi_events = []
        seen_tickers = set()
        
        for series_key, sport_tag, league_tag in target_sports:
            series_tickers = _SPORTS_SERIES_MAP.get(series_key, [])
            for series in series_tickers:
                events_data = get_series_events(series)
                
                for e in events_data:
                    event_ticker = e.get('event_ticker') or ''
                    if not event_ticker or event_ticker in seen_tickers:
                        continue
                        
                    now_et = datetime.now(ZoneInfo("America/New_York"))
                    today_et = now_et.date()
                    title = e.get('title') or 'Event'
                    sub = e.get('sub_title') or 'Match'
                    
                    milestone = milestone_map.get(event_ticker)
                    start_epoch = None
                    ev_date = None
                    if milestone and milestone.get('start_date'):
                        try:
                            dt = datetime.fromisoformat(milestone['start_date'].replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York'))
                            ev_date = dt.date()
                            start_epoch = dt.timestamp()
                        except:
                            pass
                    if not ev_date or not start_epoch:
                        ev_date, start_epoch = extract_sports_event_date_and_time(event_ticker, event_obj=e)
                        
                    is_live = start_epoch and start_epoch < time.time()
                    if ev_date and ev_date < today_et and not is_live:
                        continue
                        
                    seen_tickers.add(event_ticker)
                    is_today = (ev_date == today_et)
                    
                    clean_matchup = title
                    if ':' in clean_matchup:
                        clean_matchup = clean_matchup.split(':', 1)[1].strip()
                        
                    team_tokens = {w for w in re.findall(r'[a-z0-9]+', clean_matchup.lower()) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc')}
                    
                    best_pick = None
                    has_valid_pick = False
                    
                    for p in latest_picks:
                        p_sport = (p.get("sport") or "").upper()
                        if p_sport not in (series_key, sport_tag, league_tag):
                            continue
                            
                        p_team = (p.get("predicted_team") or "").lower()
                        p_matchup = (p.get("metadata", {}).get("matchup") or "").lower()
                        
                        is_match = False
                        if p_matchup:
                            p_m_tokens = {w for w in re.findall(r'[a-z0-9]+', p_matchup) if len(w) >= 3}
                            if team_tokens and (team_tokens == p_m_tokens or team_tokens.issubset(p_m_tokens) or p_m_tokens.issubset(team_tokens)):
                                is_match = True
                        
                        if not is_match:
                            p_tokens = {w for w in re.findall(r'[a-z0-9]+', p_team) if len(w) >= 3}
                            if team_tokens and (p_tokens <= team_tokens):
                                is_match = True
                            elif p_team in clean_matchup.lower():
                                is_match = True
                                
                        if not is_match and sport_tag == "TEN":
                            def strip_accents(s):
                                import unicodedata
                                return ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
                            
                            c_m = strip_accents(clean_matchup.lower())
                            p_m = strip_accents(p_matchup.lower() if p_matchup else p_team)
                            
                            c_parts = re.split(r'\s+(?:vs\.?|at|@)\s+', c_m)
                            p_parts = re.split(r'\s+(?:vs\.?|at|@)\s+', p_m)
                            
                            if len(c_parts) == 2 and len(p_parts) == 2:
                                c1, c2 = c_parts[0].split()[-1], c_parts[1].split()[-1]
                                p1, p2 = p_parts[0].split()[-1], p_parts[1].split()[-1]
                                if (c1 in p_m and c2 in p_m) or (p1 in c_m and p2 in c_m):
                                    try:
                                        p_date_str = p.get("metadata", {}).get("date")
                                        if p_date_str and ev_date:
                                            p_dt = datetime.fromisoformat(p_date_str.replace("Z", "+00:00")).date()
                                            if abs((p_dt - ev_date).days) <= 1:
                                                is_match = True
                                    except:
                                        is_match = True
                                        
                        if is_match:
                            has_valid_pick = True
                            best_pick = p
                            break
                            
                    markets = e.get("markets", [])
                    if not markets:
                        continue
                        
                    pred_pick_name = best_pick.get("predicted_team") if best_pick else None
                    conf = best_pick.get("confidence_pct", 0.0) if best_pick else 0.0
                    edge = best_pick.get("edge_pct", 0.0) if best_pick else 0.0
                    
                    best_mkt = None
                    is_alt_line = False
                    is_yes_side = True
                    
                    if conf > 0 and has_valid_pick:
                        best_mkt, is_yes_side, edge, conf, is_alt_line = find_best_market_for_pick(markets, best_pick, milestone)
                        if best_mkt:
                            markets = [best_mkt] + [m for m in markets if m != best_mkt]
                            
                    if not best_mkt:
                        best_mkt = markets[0]
                        
                    m_yes = float(best_mkt.get('yes_ask') or 0.0) / 100.0
                    m_no = float(best_mkt.get('no_ask') or 0.0) / 100.0
                    m_last = float(best_mkt.get('last_price') or 0.0) / 100.0
                    
                    ai_source_label = "Sports AI"
                    if sport_tag == "TEN" and edge == 0.0:
                        ai_source_label = "Sportsbook consensus"
                        
                    kalshi_events.append({
                        "ai_source": ai_source_label,
                        "ticker": event_ticker,
                        "title": title,
                        "sport": sport_tag,
                        "league": league_tag,
                        "matchup": clean_matchup,
                        "predicted_team": pred_pick_name or clean_matchup,
                        "has_ai_prediction": has_valid_pick and best_mkt is not None,
                        "ai_pick": pred_pick_name,
                        "ai_prediction": best_pick if has_valid_pick else None,
                        "pick_side": "YES" if is_yes_side else "NO",
                        "is_alt_line": is_alt_line,
                        "market_type": best_mkt.get("market_type_label", "Game/Match"),
                        "segment": "Main",
                        "prop_type": best_mkt.get("prop_type"),
                        "sub_title": best_mkt.get("sub_title", sub),
                        "confidence_pct": conf,
                        "edge_pct": edge,
                        "event_ticker": event_ticker,
                        "series_ticker": series,
                        "start_epoch": start_epoch,
                        "is_today": is_today,
                        "is_live": is_live,
                        "event_date": str(ev_date) if ev_date else None,
                        "yes_ask": m_yes,
                        "no_ask": m_no,
                        "last_price": m_last,
                        "markets": markets,
                        "metadata": {
                            "is_live": is_live,
                            "name": pred_pick_name,
                            "matchup": clean_matchup,
                            "market_type_label": best_mkt.get("market_type_label", "Game/Match"),
                            "prop_type": best_mkt.get("prop_type"),
                        }
                    })

        kalshi_events = [e for e in kalshi_events if e.get("is_today") or not (e.get("event_date") and datetime.strptime(e.get("event_date"), "%Y-%m-%d").date() < today_et and not e.get("is_live"))]
        kalshi_events.sort(key=lambda x: float(x.get("start_epoch") or 9999999999.0))
        
        result = {"status": "ok", "count": len(kalshi_events), "events": kalshi_events}
        with _SPORTS_AGG_CACHE_LOCK:
            _SPORTS_AGG_CACHE[query_filter] = (now, result)
        return result
    except Exception as e:
        logger.error(f"Error in api_sports_events: {e}")
        import traceback; traceback.print_exc()
        return {"status": "error", "message": str(e), "events": []}

"""

c = c[:start_idx] + new_func + c[end_idx:]

with open("backend/routes/engine.py", "w") as f:
    f.write(c)

print("Rewrote api_sports_events.")
