with open("backend/routes/engine.py", "r", encoding="utf-8") as f:
    text = f.read()

old_valid = """                    if prop_type == "Total (O/U)" and not any(k in pred_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                        ai_lean_team = matched_pred_team
                        ai_lean_pct = conf
                        conf = 0.0
                        edge = 0.0
                        has_valid_pick = False"""

new_valid = """                    if prop_type == "Total (O/U)" and not any(k in pred_mtype for k in ("TOTAL", "OVER", "UNDER", "O/U")):
                        ai_lean_team = matched_pred_team
                        ai_lean_pct = conf
                        conf = 0.0
                        edge = 0.0
                        has_valid_pick = False
                    if prop_type in ("Player Prop", "PLAYER PROP") and not any(k in pred_mtype for k in ("PROP", "PLAYER")):
                        ai_lean_team = matched_pred_team
                        ai_lean_pct = conf
                        conf = 0.0
                        edge = 0.0
                        has_valid_pick = False"""

if old_valid in text:
    text = text.replace(old_valid, new_valid)
    with open("backend/routes/engine.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Replaced successfully")
else:
    print("Not found!")
