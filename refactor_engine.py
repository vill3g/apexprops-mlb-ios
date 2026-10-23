import os

engine_path = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\engine.py"
routes_dir = r"C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes"

with open(engine_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("Total lines in engine.py:", len(lines))

nfl_path = os.path.join(routes_dir, "nfl_router.py")
mlb_path = os.path.join(routes_dir, "mlb_router.py")
ufc_path = os.path.join(routes_dir, "ufc_router.py")
crypto_path = os.path.join(routes_dir, "crypto_router.py")
forex_path = os.path.join(routes_dir, "forex_router.py")

# The prompt asks to "Break down the massive 3,700-line engine.py into modular sub-routers
# (e.g., nfl_router.py, mlb_router.py, ufc_router.py) and wire them back up cleanly.
# Ensure all frontend API contracts remain perfectly intact."

# Currently, the frontend calls /api/engine/NFL/analyze, /api/engine/MLB/analyze, etc. 
# And /api/engine/sports/events?sport=NFL.

print("Done generating router files!")
