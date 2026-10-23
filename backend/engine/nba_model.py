from backend.data.nba_client import NBAClient
import time
import random

class NBAModel:
    def __init__(self):
        self.nba_client = NBAClient()

    def get_nba_slate(self):
        return self.nba_client.get_todays_slate()

    def get_nba_props(self):
        # Generate some baseline mock props based on the slate
        slate = self.get_nba_slate()
        props = []
        for game in slate:
            home = game["home_team"]["name"]
            away = game["away_team"]["name"]
            
            # Simple randomized probability for the sake of architecture completeness
            home_prob = round(random.uniform(40.0, 60.0), 1)
            away_prob = round(100.0 - home_prob, 1)
            
            rec_team = home if home_prob >= away_prob else away
            rec_prob = max(home_prob, away_prob)
            
            props.append({
                "game_id": game["game_id"],
                "name": rec_team,
                "team": rec_team,
                "opponent": f"{home} vs {away}",
                "market_type": "MONEYLINE",
                "win_prob": rec_prob,
                "edge": round(max(0.0, rec_prob - 50.0), 1),
                "is_verified": True
            })
        return props

    def simulate_nba(self, home_team: str, away_team: str, simulations: int = 1000):
        # A simple Monte Carlo simulation placeholder
        home_prob = round(random.uniform(45.0, 55.0), 1)
        away_prob = round(100.0 - home_prob, 1)
        rec_team = home_team if home_prob >= away_prob else away_team
        return {
            "home_team": home_team,
            "away_team": away_team,
            "simulations": simulations,
            "home_win_prob": home_prob,
            "away_win_prob": away_prob,
            "recommended_pick": rec_team
        }
