with open("backend/sports_bridge/prediction_client.py", "r", encoding="utf-8") as f:
    c = f.read()

import re

# Replace soccer block
soccer_re = r'# 4\. Fetch Soccer top picks if not yet present.*?(?=# 5\. Fetch UFC top picks)'
soccer_new = """# 4. Fetch Soccer slate
        if True:
            try:
                r = self.client.get(f"{self.base_url}/api/soccer/slate")
                if r.status_code == 200:
                    soccer_data = r.json()
                    for g in soccer_data.get("matches", []) or soccer_data.get("games", []):
                        home_team = g.get("home_team", {}).get("name", "Unknown")
                        away_team = g.get("away_team", {}).get("name", "Unknown")
                        matchup = f"{home_team} vs {away_team}"
                        
                        ml = g.get("ml_prediction") or g.get("moneyline") or {}
                        if ml and ml.get("pick"):
                            pick = ml.get("pick")
                            if pick == home_team:
                                prob = ml.get("home_win_prob", 50.0)
                            elif pick == away_team:
                                prob = ml.get("away_win_prob", 50.0)
                            else:
                                prob = ml.get("draw_prob", 50.0)
                                pick = "Draw"
                                
                            all_picks.append({
                                "sport": "SOC",
                                "league": g.get("league", "SOC"),
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(prob),
                                "edge_pct": float(ml.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": g.get("league", "SOC"),
                                    "game_id": g.get("id"),
                                    "start_label": g.get("start_time")
                                }
                            })
                            
                            if pick != "Draw" and ml.get("draw_prob"):
                                all_picks.append({
                                    "sport": "SOC",
                                    "league": g.get("league", "SOC"),
                                    "market_type": "DRAW",
                                    "predicted_team": "Draw",
                                    "opponent": matchup,
                                    "confidence_pct": float(ml.get("draw_prob", 33.3)),
                                    "edge_pct": 0.0,
                                    "metadata": {
                                        "name": "Draw",
                                        "matchup": matchup,
                                        "home_team": home_team,
                                        "away_team": away_team,
                                        "league": g.get("league", "SOC"),
                                        "game_id": g.get("id"),
                                        "start_label": g.get("start_time")
                                    }
                                })

                        tot = g.get("total_prediction") or g.get("goals_prediction") or g.get("totals") or {}
                        if tot and tot.get("pick"):
                            pick = tot.get("pick")
                            all_picks.append({
                                "sport": "SOC",
                                "league": g.get("league", "SOC"),
                                "market_type": "TOTAL",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(tot.get("prob", 50.0)),
                                "edge_pct": float(tot.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": g.get("league", "SOC"),
                                    "game_id": g.get("id"),
                                    "start_label": g.get("start_time")
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch soccer slate: {e}")
        
        """

c = re.sub(soccer_re, soccer_new, c, flags=re.DOTALL)

ufc_re = r'# 5\. Fetch UFC top picks if not yet present.*?(?=if all_picks:)'
ufc_new = """# 5. Fetch UFC slate
        if True:
            try:
                r = self.client.get(f"{self.base_url}/api/ufc/slate")
                if r.status_code == 200:
                    ufc_data = r.json()
                    for f_match in ufc_data.get("fights", []):
                        home_team = f_match.get("home_team", {}).get("name", "Unknown")
                        away_team = f_match.get("away_team", {}).get("name", "Unknown")
                        matchup = f"{home_team} vs {away_team}"
                        
                        ml = f_match.get("ml_prediction") or {}
                        if ml and ml.get("pick"):
                            pick = ml.get("pick")
                            if pick == home_team:
                                prob = ml.get("prob_a", 50.0)
                            else:
                                prob = ml.get("prob_b", 50.0)
                                
                            all_picks.append({
                                "sport": "UFC",
                                "league": f_match.get("league", "UFC"),
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(prob),
                                "edge_pct": float(ml.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": f_match.get("league", "UFC"),
                                    "game_id": f_match.get("id", f_match.get("event_id")),
                                    "start_label": f_match.get("start_time")
                                }
                            })

                        tot = f_match.get("total_prediction") or f_match.get("totals") or {}
                        if tot and tot.get("pick"):
                            pick = tot.get("pick")
                            all_picks.append({
                                "sport": "UFC",
                                "league": f_match.get("league", "UFC"),
                                "market_type": "TOTAL",
                                "predicted_team": pick,
                                "opponent": matchup,
                                "confidence_pct": float(tot.get("prob", 50.0)),
                                "edge_pct": float(tot.get("edge_val", 0.0)),
                                "metadata": {
                                    "name": pick,
                                    "matchup": matchup,
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": f_match.get("league", "UFC"),
                                    "game_id": f_match.get("id", f_match.get("event_id")),
                                    "start_label": f_match.get("start_time")
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch ufc slate: {e}")
        
        """

c = re.sub(ufc_re, ufc_new, c, flags=re.DOTALL)

with open("backend/sports_bridge/prediction_client.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Done with prediction client patches")
