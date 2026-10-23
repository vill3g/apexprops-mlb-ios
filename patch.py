with open('backend/sports_bridge/prediction_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = '''            home_team_md = md.get("home_team")
            home_abbr = home_team_md.get("abbr") if isinstance(home_team_md, dict) else ""
            away_team_md = md.get("away_team")
            away_abbr = away_team_md.get("abbr") if isinstance(away_team_md, dict) else ""
            team_abbr = (md.get("team") or home_abbr or "").lower().strip()
            opp_abbr = (md.get("opponent") or away_abbr or "").lower().strip()'''

content = content.replace(
    '            team_abbr = (md.get("team") or md.get("home_team", {}).get("abbr") or "").lower().strip()\n            opp_abbr = (md.get("opponent") or md.get("away_team", {}).get("abbr") or "").lower().strip()',
    replacement
)

with open('backend/sports_bridge/prediction_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
