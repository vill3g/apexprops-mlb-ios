# ApexProps MLB: Hits + Runs + RBIs Analytics & Prop Prediction Engine

An advanced sports analytics application designed to identify the **Top 5 daily highest-probability MLB Hits + Runs + RBIs (H+R+RBI)** player props using live ESPN API feeds and a correlated Monte Carlo simulation engine.

---

## Key Features

1. **Top 5 Daily Highest Probability Hero Cards**:
   - Automated ranking of the top 5 highest probability Over plays from the day's active slate.
   - Built-in **Portfolio Diversification** (max 2 batters per team) to prevent single-game correlation risks.
   - Transparent ESPN player headshots and authentic team logos.
   - Visual probability radial meters, book comparison odds, positive EV edge (+20% to +25%), and recent L10 hit rates.

2. **Live ESPN API Integration**:
   - **Scoreboard Endpoint** (`site.api.espn.com/.../mlb/scoreboard`): Pulls real-time daily games, game times, probable starting pitchers, and season ERAs.
   - **Game Summary & Rosters** (`site.api.espn.com/.../mlb/summary`): Ingests confirmed starting batting orders (1–9), player positions, and real-time scratch/injury reports.
   - **PickCenter Odds Feed**: Ingests live **DraftKings** Over/Under totals and run-line spreads to derive each team's Implied Team Total (ITT).
   - **High-Speed Concurrency**: Multi-threaded batch ingestion queries all 15 MLB games simultaneously in parallel.

3. **Correlated Monte Carlo Simulation Engine**:
   - Hits, Runs, and RBIs are correlated events (e.g. a Home Run produces 1 H, 1 R, and 1+ RBIs simultaneously).
   - Simulates 5,000 to 10,000 plate appearances per batter conditioned on batting order (spots 1–5 average 4.2–4.8 PAs), home/away status, stadium park factor, and opposing pitcher ERA.

4. **Interactive Screener & Deep Dive Modal**:
   - Searchable, sortable slate table with probability sliders and line filters (Over 1.5 and Over 2.5).
   - Deep dive analytical modal showing the full simulated outcome distribution (0 to 5+ totals), component breakdown (Expected Hits, Runs, RBIs), and qualitative matchup catalysts.
   - Built-in **Custom Slip Builder / Parlay Calculator** for computing joint win probabilities and fair multipliers.

---

## Directory Structure

```
mlb_props_app/
├── backend/
│   ├── data/
│   │   ├── espn_client.py       # Live ESPN API client (Scoreboard, Summary, PickCenter)
│   │   └── __init__.py
│   ├── engine/
│   │   ├── simulator.py         # Correlated Monte Carlo plate appearance simulation
│   │   ├── top5_selector.py     # Top 5 ranking, catalysts, and diversification
│   │   └── __init__.py
│   └── main.py                  # FastAPI REST API & static file server
├── static/
│   └── index.html               # Graphical user interface (Tailwind, dark mode)
├── run_app.bat                  # One-click Windows batch launcher
├── test_sim.py                  # CLI simulation test script
└── README.md
```

---

## How to Run

### Option 1: Double click `run_app.bat`
Double-click `run_app.bat` in Windows File Explorer.

### Option 2: From PowerShell or Terminal
```powershell
cd C:\Users\vill3\.gemini\antigravity\scratch\mlb_props_app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8055 --reload
```

Then open your browser to:
**http://localhost:8055**

---

## REST API Endpoints

- `GET /api/picks/top5` — Returns the Top 5 daily highest-probability picks with simulation breakdown.
- `GET /api/props` — Returns all slate batter props with query filters (`search`, `min_prob`, `line`).
- `GET /api/slate` — Today's active MLB games, venues, and probable starting pitchers.
- `POST /api/refresh` — Forces an instant live sync with ESPN and re-runs Monte Carlo simulations.
