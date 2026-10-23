import re

with open('backend/routes/engine.py', 'r') as f:
    c = f.read()

c = c.replace(
    "event_obj=e\n                    )",
    "event_obj=e,\n                        milestone=milestone\n                    )"
)

# Update definition of parse_sports_market_details
c = c.replace(
    "event_obj: Optional[dict] = None\n) -> dict:",
    "event_obj: Optional[dict] = None,\n    milestone: Optional[dict] = None\n) -> dict:"
)

with open('backend/routes/engine.py', 'w') as f:
    f.write(c)
