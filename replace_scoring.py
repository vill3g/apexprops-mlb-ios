with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_scoring = """                            if is_total_market:
                                if is_total_pick:
                                    score += 150
                                else:
                                    score -= 100
                            elif is_spread_market:
                                if is_spread_pick:
                                    score += 150
                                else:
                                    score -= 100
                            elif is_player_prop_market:
                                if is_player_prop_pick:
                                    score += 150
                                else:
                                    score -= 100
                            else:
                                if "MONEYLINE" in p_mtype or "WINNER" in p_mtype:
                                    score += 100
                                if is_total_pick:
                                    score -= 100"""

new_scoring = """                            if is_total_market:
                                if is_total_pick:
                                    score += 150
                                else:
                                    continue
                            elif is_spread_market:
                                if is_spread_pick:
                                    score += 150
                                else:
                                    continue
                            elif is_player_prop_market:
                                if is_player_prop_pick:
                                    score += 150
                                else:
                                    continue
                            else:
                                if "MONEYLINE" in p_mtype or "WINNER" in p_mtype or p_mtype == "":
                                    score += 100
                                elif is_total_pick or is_spread_pick or is_player_prop_pick:
                                    continue"""

if old_scoring in text:
    text = text.replace(old_scoring, new_scoring)
    with open("backend/routes/engine.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Replaced successfully")
else:
    print("Old scoring block not found!")
