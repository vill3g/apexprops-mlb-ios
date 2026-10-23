import re

with open('backend/routes/engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

target = '''def api_sports_events(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    filter: Optional[str] = None
):'''

replace = '''def api_sports_events(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    filter: Optional[str] = None
):
    print("THIS IS MY CODE!")
    raise ValueError("MY INTENTIONAL CRASH")'''

if target in code:
    code = code.replace(target, replace)
    with open('backend/routes/engine.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("Injected crash!")
else:
    print("Target not found")
