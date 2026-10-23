import json
import re
import difflib
import unicodedata

SOCCER_ALIASES = {
    "los angeles g": "la galaxy",
    "los angeles galaxy": "la galaxy",
    "la galaxy": "la galaxy",
    "los angeles f": "los angeles fc",
    "los angeles fc": "los angeles fc",
    "lafc": "los angeles fc",
    "saint louis": "st. louis",
    "st louis": "st. louis",
    "st. louis city sc": "st. louis",
    "st. louis city": "st. louis",
    "new york rb": "new york red bulls",
    "red bull new york": "new york red bulls",
    "nyrb": "new york red bulls",
    "kansas city": "sporting kansas city",
    "sporting kc": "sporting kansas city",
    "salt lake": "real salt lake",
    "rsl": "real salt lake",
    "dc united": "d.c. united",
    "dcu": "d.c. united",
    "brighton": "brighton & hove albion",
    "brighton and hove albion": "brighton & hove albion",
    "tottenham": "tottenham hotspur",
    "manchester utd": "manchester united",
    "man utd": "manchester united",
    "man city": "manchester city",
    "newcastle": "newcastle united",
    "west ham": "west ham united",
    "wolves": "wolverhampton wanderers",
}
SOCCER_STOP_WORDS = {'the', 'team', 'club', 'wins', 'fc', 'sc', 'cf', 'new', 'real', 'san', 'st', 'city', 'united', 'is', 'result'}

def recompute_alt_line_prob(original_prob: float, original_line: float, kalshi_line: float, is_over: bool, sport: str = "NHL") -> float:
    diff = kalshi_line - original_line
    if diff == 0:
        return original_prob
        
    s = str(sport or "NHL").upper()
    # Calibrated points per unit shift (e.g. 1 goal in NHL moves prob ~13%, 1 goal in Soccer ~19.5%, 1 run in MLB ~10%, 1 pt in NFL ~3.2%)
    if "NHL" in s or "HOCKEY" in s:
        step = 13.0
    elif any(k in s for k in ("SOC", "SOCCER", "EPL", "MLS", "UCL", "LALIGA", "BUNDES", "SERIE", "LIGUE", "EFL", "USL", "CONMEBOL")):
        step = 19.5
    elif "MLB" in s or "BASEBALL" in s:
        step = 10.0
    elif "NFL" in s or "FOOTBALL" in s:
        step = 3.2
    elif "NBA" in s or "BASKETBALL" in s:
        step = 2.5
    else:
        step = 10.0

    shift = (diff * step)
    if is_over:
        new_prob = original_prob - shift
    else:
        new_prob = original_prob + shift

    # Floor cap corridors
    return max(1.0, min(97.5, round(new_prob, 1)))

def match_team_by_id(team_name, custom_strike, milestone):
    if not custom_strike or not milestone or not milestone.get("details"):
        return False

    if isinstance(custom_strike, str):
        try:
            custom_strike = json.loads(custom_strike)
        except Exception:
            return False

    if not isinstance(custom_strike, dict):
        return False

    target_id = None
    for k, v in custom_strike.items():
        if "team" in k or k == "id":
            target_id = v
            break

    if not target_id:
        return False
        
    details = milestone["details"]
    home_id = details.get("home_team_id")
    away_id = details.get("away_team_id")
    
    title = milestone.get("title", "").upper()
    name_upper = team_name.upper()
    
    parts = re.split(r'\s+(?:AT|VS\.?|@)\s+', title)
    if len(parts) == 2:
        away_str, home_str = parts[0].strip(), parts[1].strip()
        
        def is_match(a, b):
            return a in b or b in a or (a[:4] in b and len(a)>3)
            
        is_away = is_match(name_upper, away_str)
        is_home = is_match(name_upper, home_str)
        
        if is_away and target_id == away_id: return True
        if is_home and target_id == home_id: return True
        
    return False

def _get_price(m, field):
    if not m:
        return 0.0
    val = m.get(field + '_dollars')
    if val is not None:
        try: return float(val) * 100.0
        except: pass
    val2 = m.get(field)
    if val2 is not None:
        try:
            f = float(val2)
            return f * 100.0 if f <= 1.0 else f
        except: pass
    return 0.0

def find_best_market_for_pick(markets, pick, milestone, strategy=None, sport="NHL"):
    if not markets or not pick:
        return None, True, 0.0, 0.0, False
        
    pred_team = pick.get("predicted_team", "")
    pred_mtype = str(pick.get("market_type") or pick.get("metadata", {}).get("type") or "").upper()
    conf = pick.get("confidence_pct", 50.0)
    meta = pick.get("metadata", {})
    pick_line_raw = meta.get("line") or 0.0
    sport_name = str(pick.get("sport") or sport or "NHL").upper()
    
    try:
        if isinstance(pick_line_raw, str):
            m = re.search(r'[\d\.]+', pick_line_raw)
            pick_line = float(m.group(0)) if m else 0.0
        elif pick_line_raw:
            pick_line = float(pick_line_raw)
        else:
            m = re.search(r'[\d\.]+', str(pred_team))
            pick_line = float(m.group(0)) if m else 0.0
    except:
        pick_line = 0.0

    is_spread = "SPREAD" in pred_mtype or "PUCK LINE" in pred_mtype or "RUN LINE" in pred_mtype
    is_total = "TOTAL" in pred_mtype or "OVER" in pred_mtype or "UNDER" in pred_mtype
    is_prop = "PROP" in pred_mtype or "PLAYER" in pred_mtype
    
    if is_total:
        combined_text = f"{pred_mtype} {pick_line_raw} {pred_team}".upper()
        is_over = "OVER" in combined_text or "O" in str(pick_line_raw).upper()
        
        strat = str(strategy or "").upper()
        is_soc_sport = any(k in sport_name for k in ("SOC", "SOCCER", "EPL", "MLS", "UCL", "LALIGA", "BUNDES", "SERIE", "LIGUE", "EFL", "USL", "CONMEBOL"))
        is_nhl_sport = ("NHL" in sport_name or "HOCKEY" in sport_name)
        is_floor_mode = (strat in ("FLOOR_TOTALS", "POWER_COMBO", "ULTRA_COMBO", "MEGA_PARLAY")) or is_soc_sport or is_nhl_sport
        is_ultra_mode = (strat in ("ULTRA_COMBO", "MEGA_PARLAY"))

        target_mkt = None
        min_diff = 999.0
        best_floor_mkt = None
        best_floor_val = None

        # Determine sport floor cutoff threshold
        # Target Over 0.5 goals for Soccer and Over 2.5 goals for Hockey
        if is_soc_sport:
            floor_cutoff = 0.5
        elif is_nhl_sport:
            floor_cutoff = 2.5
        elif is_ultra_mode:
            floor_cutoff = 4.5 if ("MLB" in sport_name or "BASEBALL" in sport_name) else (32.5 if ("NFL" in sport_name or "FOOTBALL" in sport_name) else (200.5 if "NBA" in sport_name else 3.5))
        else:
            floor_cutoff = 6.5 if ("MLB" in sport_name or "BASEBALL" in sport_name) else 34.5

        for m in markets:
            strike = m.get("floor_strike") or m.get("cap_strike")
            if strike is None:
                continue
            strike_val = float(strike)
            diff = abs(strike_val - pick_line)
            if diff < min_diff:
                min_diff = diff
                target_mkt = m

            # Identify valid floor alternate line
            if strike_val <= floor_cutoff:
                m_ya = _get_price(m, "yes_ask")
                if best_floor_val is None or strike_val > best_floor_val or (strike_val == best_floor_val and m_ya > _get_price(best_floor_mkt, "yes_ask")):
                    best_floor_mkt = m
                    best_floor_val = strike_val

        # Fallback if exact 0.5 (SOC) or 2.5 (NHL) was not present on this event
        if best_floor_mkt is None and (is_soc_sport or is_nhl_sport):
            alt_cutoff = 1.5 if is_soc_sport else 4.5
            for m in markets:
                strike = m.get("floor_strike") or m.get("cap_strike")
                if strike is None:
                    continue
                strike_val = float(strike)
                if strike_val <= alt_cutoff:
                    if best_floor_val is None or strike_val < best_floor_val:
                        best_floor_mkt = m
                        best_floor_val = strike_val

        # Prefer the floor anchor line
        chosen_mkt = (best_floor_mkt if (is_floor_mode and best_floor_mkt) else target_mkt) or target_mkt

        if chosen_mkt:
            strike_val = float(chosen_mkt.get("floor_strike") or chosen_mkt.get("cap_strike"))
            # For floor lines, the side is OVER
            actual_is_over = True if (is_floor_mode and best_floor_mkt and chosen_mkt == best_floor_mkt) else is_over
            base_over_prob = float(conf) if (actual_is_over == is_over) else max(42.0, 100.0 - float(conf))
            eff_pick_line = pick_line if pick_line > 0 else (2.5 if is_soc_sport else (5.5 if is_nhl_sport else strike_val))
            new_conf = recompute_alt_line_prob(base_over_prob, eff_pick_line, strike_val, actual_is_over, sport=sport_name)
            
            yes_price = _get_price(chosen_mkt, "yes_ask") / 100.0
            no_price = _get_price(chosen_mkt, "no_ask") / 100.0

            # Calibrate floor lines with live market probability
            if is_floor_mode and strike_val <= (1.5 if is_soc_sport else (4.5 if is_nhl_sport else floor_cutoff)):
                if 0.55 <= yes_price <= 0.98:
                    mkt_anchored = min(97.5, round(yes_price * 100.0 + 2.4, 1))
                    new_conf = round((new_conf * 0.35) + (mkt_anchored * 0.65), 1)
                if is_ultra_mode or (is_soc_sport and strike_val <= 0.5) or (is_nhl_sport and strike_val <= 2.5):
                    if yes_price >= 0.85:
                        new_conf = max(90.0, min(97.5, new_conf))
                    else:
                        new_conf = max(72.0, min(96.5, new_conf))
                else:
                    new_conf = max(80.0, min(95.5, new_conf))

            st_type = chosen_mkt.get("strike_type", "")
            if "greater" in st_type or not st_type:
                is_yes = actual_is_over
            else:
                is_yes = not actual_is_over
                
            market_price = yes_price if is_yes else no_price
            edge = 0.0 if market_price <= 0.0 else round(new_conf - (market_price * 100.0), 1)
            
            is_alt = (strike_val != pick_line) or (chosen_mkt == best_floor_mkt)
            return chosen_mkt, is_yes, edge, new_conf, is_alt
            
    elif is_spread:
        is_positive = "+" in str(pick_line_raw) or pick_line > 0
        pick_val = abs(pick_line)
        
        for m in markets:
            strike = m.get("floor_strike") or m.get("cap_strike")
            if strike is None: continue
            if float(strike) != pick_val: continue
            
            custom = m.get("custom_strike", {})
            st_type = m.get("strike_type", "")
            
            is_team_match = match_team_by_id(pred_team, custom, milestone)
            
            if is_positive:
                if not is_team_match and "greater" in st_type:
                    yes_price = _get_price(m, "yes_ask") / 100.0
                    no_price = _get_price(m, "no_ask") / 100.0
                    edge = 0.0 if no_price <= 0.0 else round(conf - (no_price * 100.0), 1)
                    return m, False, edge, conf, False
            else:
                if is_team_match and "greater" in st_type:
                    yes_price = _get_price(m, "yes_ask") / 100.0
                    edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                    return m, True, edge, conf, False
                    
    elif is_prop:
        pred_player = pick.get("predicted_team", "").upper()
        for m in markets:
            sub = (m.get("yes_sub_title") or "").upper()
            if pred_player in sub:
                yes_price = _get_price(m, "yes_ask") / 100.0
                edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                return m, True, edge, conf, False

    else:
        # Moneyline
        for m in markets:
            custom = m.get("custom_strike", {})
            if match_team_by_id(pred_team, custom, milestone):
                yes_price = _get_price(m, "yes_ask") / 100.0
                edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                return m, True, edge, conf, False
                
        def strip_accents(s):
            return ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn').lower()

        pred_clean = strip_accents(pred_team)
        pred_tokens = {w for w in re.findall(r'[a-z0-9]+', pred_clean) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc', 'wins')}

        # Draw / Tie in soccer
        if pred_clean in ("draw", "tie"):
            for m in markets:
                sub = strip_accents(m.get("yes_sub_title") or "")
                title = strip_accents(m.get("title") or "")
                if "tie" in sub or "tie" in title or "draw" in sub or "draw" in title:
                    yes_price = _get_price(m, "yes_ask") / 100.0
                    edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                    return m, True, edge, conf, False

        for m in markets:
            sub = strip_accents(m.get("yes_sub_title") or "")
            title = strip_accents(m.get("title") or "")
            cand = sub or title
            cand_clean = re.sub(r'\s+wins?$', '', cand).strip()
            
            # Alias matching for MLS and Soccer
            n_pred = SOCCER_ALIASES.get(pred_clean, pred_clean)
            n_cand = SOCCER_ALIASES.get(cand_clean, cand_clean)
            if n_pred == n_cand or n_pred in n_cand or n_cand in n_pred:
                yes_price = _get_price(m, "yes_ask") / 100.0
                edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                return m, True, edge, conf, False

            cand_tokens = {w for w in re.findall(r'[a-z0-9]+', cand) if len(w) >= 3 and w not in ('the', 'team', 'club', 'fc', 'wins')}
            if pred_clean and (pred_clean in cand or cand in pred_clean or (pred_tokens and pred_tokens.issubset(cand_tokens)) or (pred_tokens and len(pred_tokens & cand_tokens) >= 1 and (len(pred_tokens) == 1 or len(pred_tokens & cand_tokens) >= len(pred_tokens) - 1))):
                yes_price = _get_price(m, "yes_ask") / 100.0
                edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                return m, True, edge, conf, False

            # Fuzzy token matching (handles Russian/Slavic transliterations like Zhelezniakova / Zheleznyakova)
            if pred_tokens and cand_tokens and any(difflib.SequenceMatcher(None, t1, t2).ratio() >= 0.75 for t1 in pred_tokens for t2 in cand_tokens):
                yes_price = _get_price(m, "yes_ask") / 100.0
                edge = 0.0 if yes_price <= 0.0 else round(conf - (yes_price * 100.0), 1)
                return m, True, edge, conf, False
                
    return None, True, 0.0, conf, False
