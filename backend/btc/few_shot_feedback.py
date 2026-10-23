"""
backend/btc/few_shot_feedback.py
In-Context Few-Shot Execution Feedback for Gemini 15M Gate.

Fetches the most recent closed trades for the current asset and summarizes:
  - Entry direction vs actual outcome (WIN vs LOSS).
  - Entry price vs settlement price.
  - Root cause / failure diagnosis if loss, or catalyst driver if win.

Injected into the prompt so Gemini has live session self-correction memory.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from backend.database.models import get_db_connection

logger = logging.getLogger(__name__)


def get_recent_execution_feedback(asset: str = "BTC", limit: int = 4) -> List[Dict[str, Any]]:
    """
    Returns the last N closed trades for the asset with clear post-mortem lessons.
    """
    feedback = []
    a_up = str(asset or "BTC").upper().strip()
    ticker_pattern = f"%{a_up}%"

    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT ticker, side, entry_price, exit_price, pnl, exit_reason, catalysts, raw_json, timestamp
                FROM trades
                WHERE ticker LIKE ? AND status = 'CLOSED' AND pnl IS NOT NULL
                ORDER BY rowid DESC
                LIMIT ?
            """, (ticker_pattern, limit))
            rows = c.fetchall()

            for r in rows:
                tk, side, entry, exit_p, pnl, exit_reason, catalysts, raw_json, ts = r
                pnl_f = float(pnl or 0.0)
                entry_f = float(entry or 0.0)
                exit_f = float(exit_p or 0.0) if exit_p is not None else (1.0 if pnl_f > 0 else 0.0)
                is_win = pnl_f > 0

                lesson = ""
                category = "STANDARD_EXECUTION"
                if raw_json:
                    try:
                        d = json.loads(raw_json)
                        if "loss_analysis" in d:
                            la = d["loss_analysis"]
                            category = la.get("category", "LOSS")
                            lesson = la.get("summary", "")
                    except Exception:
                        pass

                if not lesson:
                    if is_win:
                        lesson = f"Clean trend expansion and follow-through in direction ({side}); settled in-the-money."
                    else:
                        er = str(exit_reason or "")
                        if "STOP_LOSS" in er:
                            lesson = f"Contract dropped {er}; market momentum reversed against entry."
                        elif exit_f == 0.0:
                            lesson = f"Settled at $0.00; spot crossed back over strike line into expiration."
                        else:
                            lesson = f"Trade exited at {exit_f*100:.0f}¢ with ${pnl_f:+.2f} PnL."

                feedback.append({
                    "contract": tk,
                    "call": side,
                    "outcome": "WIN" if is_win else "LOSS",
                    "entry_cents": round(entry_f * 100, 1),
                    "exit_cents": round(exit_f * 100, 1),
                    "pnl": round(pnl_f, 2),
                    "category": category,
                    "post_mortem_lesson": lesson,
                })
    except Exception as e:
        logger.debug(f"[FewShotFeedback] Error querying recent trade memory: {e}")

    return feedback
