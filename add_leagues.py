with open("backend/sports_bridge/prediction_client.py", "r", encoding="utf-8") as f:
    c = f.read()

new_block = """
        # Fetch MLB, NFL, NHL games
        for sport_key, path in [("MLB", "/api/mlb/games"), ("NFL", "/api/nfl/games"), ("NHL", "/api/nhl/games")]:
            try:
                r = self.client.get(f"{self.base_url}{path}")
                if r.status_code == 200:
                    data = r.json()
                    for g in data.get("games", []):
                        ml = g.get("ml_prediction") or {}
                        home_team = g.get("home_team", {}).get("name", "Unknown")
                        away_team = g.get("away_team", {}).get("name", "Unknown")
                        if ml and ml.get("pick"):
                            pick = ml.get("pick")
                            prob = float(ml.get("home_win_prob") if pick == home_team else ml.get("away_win_prob") or 50.0)
                            edge = float(ml.get("edge_val", 0.0))
                            all_picks.append({
                                "sport": sport_key,
                                "league": sport_key,
                                "market_type": "MONEYLINE",
                                "predicted_team": pick,
                                "opponent": f"{away_team} at {home_team}",
                                "confidence_pct": prob,
                                "edge_pct": edge,
                                "metadata": {
                                    "name": pick,
                                    "matchup": f"{away_team} at {home_team}",
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": sport_key,
                                    "game_id": g.get("game_id"),
                                    "start_label": g.get("start_time") or g.get("game_time")
                                }
                            })
                        
                        tot = g.get("total_prediction") or g.get("total_runs") or g.get("totals") or {}
                        if tot and tot.get("pick"):
                            pick = tot.get("pick")
                            prob = float(tot.get("prob", 50.0))
                            edge = float(tot.get("edge_val", 0.0))
                            all_picks.append({
                                "sport": sport_key,
                                "league": sport_key,
                                "market_type": "TOTAL",
                                "predicted_team": pick,
                                "opponent": f"{away_team} at {home_team}",
                                "confidence_pct": prob,
                                "edge_pct": edge,
                                "metadata": {
                                    "name": pick,
                                    "matchup": f"{away_team} at {home_team}",
                                    "home_team": home_team,
                                    "away_team": away_team,
                                    "league": sport_key,
                                    "game_id": g.get("game_id"),
                                    "start_label": g.get("start_time") or g.get("game_time")
                                }
                            })
            except Exception as e:
                logger.debug(f"Failed to fetch {sport_key} games: {e}")
"""

if "# Fetch MLB, NFL, NHL games" not in c:
    target = "# 2. Fetch NPB and KBO slate games from local AI engine"
    c = c.replace(target, new_block + "\n        " + target)
    with open("backend/sports_bridge/prediction_client.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("Added MLB, NFL, NHL to fetch_latest_picks")
else:
    print("Already added")
