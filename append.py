with open("fixes/SPORTS_PICKS_FOR_ANTIGRAVITY.md", "a", encoding="utf-8") as f:
    f.write("\n### JSON Payloads\n")
    f.write("`json\n")
    f.write('''{
  "predictions": [
    {
      "sport": "MLB",
      "market_type": "MONEYLINE",
      "predicted_team": "Chase Meidroth",
      "opponent": "CLE",
      "confidence_pct": 72.1,
      "edge_pct": 14.5,
      "metadata": {
        "id": "805367_849832",
        "player_id": 805367,
        "game_id": "849832",
        "name": "Chase Meidroth",
        "team": "CWS",
        "opponent": "CLE"
      }
    }
  ]
}''')
    f.write("\n`\n")
