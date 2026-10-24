"""Read-only audit of Gemini decisions and the trades they drove, over a time window.

Usage: python -I scripts/gemini_audit.py [hours]   (default 24)
  * Every decision is scored against Kalshi's official result (backend/data/market_results.json).
  * Trades that Gemini drove are summarised separately from the rest of the bot's trades.
"""
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.core.trade_time import trade_epoch  # noqa: E402

HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0    # 0 = all time
SPLIT = sys.argv[2] if len(sys.argv) > 2 else None           # e.g. 2026-10-21: report before / after this date (ET)
CUTOFF = time.time() - HOURS * 3600 if HOURS > 0 else 0.0
DATA = os.path.join(ROOT, "backend", "data")


def load_json(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f) or default
    except (OSError, ValueError):
        return default


def band(conf):
    lo = int(float(conf) // 5 * 5)
    return f"{lo}-{lo + 5}%"


def pct(w, n):
    return f"{100.0 * w / n:5.1f}%" if n else "   n/a"


# ── 1. Gemini decisions, scored against Kalshi results ─────────────────
results = load_json("market_results.json", {})
calls = [c for c in load_json("gemini_calls.json", []) if isinstance(c, dict) and float(c.get("ts", 0)) >= CUTOFF]
scored, pending = [], 0
for c in calls:
    d = str(c.get("direction", "")).upper()
    r = results.get(c.get("ticker"))
    if d not in ("YES", "NO") or r not in ("YES", "NO"):
        pending += 1
        continue
    scored.append({**c, "won": d == r})

print(f"== Gemini decisions, last {HOURS:g}h: {len(calls)} total | {len(scored)} scored | "
      f"{pending} unscored (PASS or market not settled yet)")
w = sum(1 for s in scored if s["won"])
print(f"   overall: {w} wins / {len(scored) - w} losses  ({pct(w, len(scored))})")

for title, key in (("by asset", lambda s: s.get("asset")), ("by direction", lambda s: str(s.get("direction")).upper()),
                   ("by confidence band", lambda s: band(s.get("confidence", 50)))):
    groups = defaultdict(lambda: [0, 0])
    for s in scored:
        g = groups[key(s)]
        g[0] += 1
        g[1] += 1 if s["won"] else 0
    print(f"   {title}:")
    for k in sorted(groups, key=str):
        n, wins = groups[k]
        print(f"      {str(k):<12} {wins:>3}W {n - wins:>3}L  {pct(wins, n)}")

# ── 2. Trades Gemini drove (both databases) ────────────────────────────
def is_gemini(t):
    """Only explicit markers: the Gemini reasoning style, or the GEMINI conviction badge the executor sets."""
    return ("GEMINI" in str(t.get("trading_style", "")).upper()
            or str(t.get("conviction_badge", "")).upper().startswith("🧠 GEMINI")
            or str(t.get("conviction_badge", "")).upper().startswith("GEMINI"))


trades = {}
for db in ("users.db", "trades.db"):
    path = os.path.join(DATA, db)
    if not os.path.exists(path):
        continue
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT raw_json FROM trades").fetchall()
    except sqlite3.Error:
        continue
    for (raw,) in rows:
        try:
            t = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if trade_epoch(t.get("timestamp")) < CUTOFF:
            continue
        trades[(db, t.get("id"), t.get("ticker"), t.get("timestamp"))] = t

gem = [t for t in trades.values() if is_gemini(t)]
other = [t for t in trades.values() if not is_gemini(t)]


def summary(label, items):
    closed = [t for t in items if str(t.get("status", "")).upper() in ("CLOSED", "SETTLED")]
    wins = [t for t in closed if float(t.get("pnl") or 0) > 0]
    losses = [t for t in closed if float(t.get("pnl") or 0) < 0]
    pnl = sum(float(t.get("pnl") or 0) for t in closed)
    still_open = len(items) - len(closed)
    print(f"== {label}: {len(items)} trades | {len(closed)} closed | {still_open} still open")
    print(f"   {len(wins)} wins / {len(losses)} losses ({pct(len(wins), len(wins) + len(losses))}) | net pnl ${pnl:,.2f}")
    if losses:
        worst = sorted(losses, key=lambda t: float(t.get("pnl") or 0))[:5]
        print("   worst losses:")
        for t in worst:
            print(f"      ${float(t.get('pnl') or 0):>9,.2f}  {str(t.get('mode', '?')):5} {str(t.get('ticker', ''))[:34]:34} "
                  f"{str(t.get('side', '?')):3} x{t.get('count', '?')} @ {t.get('entry_price')}  {str(t.get('exit_reason', ''))[:24]}")


if SPLIT:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    cut_epoch = datetime.fromisoformat(SPLIT).replace(tzinfo=ZoneInfo("America/New_York")).timestamp()
    for label, pred in (("BEFORE", lambda e: e < cut_epoch), ("ON/AFTER", lambda e: e >= cut_epoch)):
        print()
        print(f"######## {label} {SPLIT}")
        summary("Gemini-driven trades", [t for t in gem if pred(trade_epoch(t.get("timestamp")))])
        print()
        summary("All other trades (for comparison)", [t for t in other if pred(trade_epoch(t.get("timestamp")))])
else:
    print()
    summary("Gemini-driven trades", gem)
    print()
    summary("All other trades (for comparison)", other)
