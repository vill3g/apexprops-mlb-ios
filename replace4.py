with open('backend/routes/engine.py', 'r') as f:
    content = f.read()

content = content.replace(
    "games = d.get('games') or d.get('slate') or d.get('events') or d",
    "games = d.get('games') or d.get('matches') or d.get('slate') or d.get('events') or d"
)
content = content.replace(
    "if isinstance(games, dict) and 'games' in games:",
    "if isinstance(games, dict) and ('games' in games or 'matches' in games):"
)
content = content.replace(
    "games = games['games']",
    "games = games.get('games') or games.get('matches')"
)

with open('backend/routes/engine.py', 'w') as f:
    f.write(content)
print('Fixed matches key')
