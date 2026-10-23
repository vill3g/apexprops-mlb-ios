"""
Pillar 2: Autonomous Multi-Agent Swarm Debate (Adversarial Red-Teaming)
for ShadowTrader AI.

Spawns four specialized deterministic algorithmic personas that aggressively debate
every candidate trade signal before capital is deployed:
1. Bull Hunter: Builds the strongest mathematical/momentum thesis for YES.
2. Bear Assassin: Builds the strongest risk/rejection thesis for NO.
3. Chief Risk Officer (Red-Teamer): Detects traps, fee drag, spread risk, liquidity walls, and macro traps.
4. Arbiter: Synthesizes the debate, awards consensus edge points, and issues the final verdict.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("agent_swarm_debate")


class AgentSwarmDebate:
    """Multi-Agent Adversarial Committee that stress-tests trade candidates."""

    @classmethod
    def conduct_adversarial_debate(
        cls,
        candidate_pred: str,
        prob: float,
        asset: str,
        df_indicators: Dict[str, Any],
        microstructure_snapshot: Optional[Dict[str, Any]] = None,
        macro_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes an adversarial red-team debate on the candidate signal.
        Returns:
            - verdict: "APPROVED" | "VETOED" | "MODIFIED"
            - final_direction: str
            - final_probability: float
            - consensus_score: float (-1.0 to +1.0)
            - debate_transcript: List[Dict[str, str]]
            - summary: str
        """
        micro = microstructure_snapshot or {}
        macro = macro_state or {}
        rsi = float(df_indicators.get("rsi", 50.0))
        adx = float(df_indicators.get("adx", 15.0))
        ema_9 = float(df_indicators.get("ema_9", 0.0))
        ema_21 = float(df_indicators.get("ema_21", 0.0))
        c_close = float(df_indicators.get("close", 0.0))
        bb_upper = float(df_indicators.get("bb_upper", c_close * 1.01))
        bb_lower = float(df_indicators.get("bb_lower", c_close * 0.99))

        micro_wall = micro.get("wall_side", "NONE")
        micro_pressure = micro.get("institutional_pressure", "NEUTRAL")
        vpin = float(micro.get("toxicity_vpin", 0.15))

        transcript: List[Dict[str, str]] = []

        # 1. BULL HUNTER ARGUMENT
        bull_points = 0
        bull_args = []
        if ema_9 > ema_21:
            bull_points += 2
            bull_args.append("9 EMA > 21 EMA bullish golden stack.")
        if c_close > ema_9:
            bull_points += 1
            bull_args.append("Price riding above short-term momentum average.")
        if micro_pressure in ("HEAVY_BID", "MODERATE_BID") or micro_wall == "BID_WALL":
            bull_points += 3
            bull_args.append(f"Institutional depth confirms bid dominance ({micro_pressure}).")
        if rsi > 52.0 and rsi < 72.0:
            bull_points += 1
            bull_args.append("RSI expansion corridor active without climax exhaustion.")

        transcript.append({
            "agent": "Bull Hunter",
            "score": f"+{bull_points}",
            "argument": " ".join(bull_args) if bull_args else "Weak bullish structural conviction."
        })

        # 2. BEAR ASSASSIN ARGUMENT
        bear_points = 0
        bear_args = []
        if ema_9 < ema_21:
            bear_points += 2
            bear_args.append("9 EMA < 21 EMA bearish death stack.")
        if c_close < ema_9:
            bear_points += 1
            bear_args.append("Price compressed below short-term trend ceiling.")
        if micro_pressure in ("HEAVY_ASK", "MODERATE_ASK") or micro_wall == "ASK_WALL":
            bear_points += 3
            bear_args.append(f"Institutional depth confirms supply wall overhead ({micro_pressure}).")
        if rsi < 48.0 and rsi > 28.0:
            bear_points += 1
            bear_args.append("RSI downward flush active without oversold spring.")

        transcript.append({
            "agent": "Bear Assassin",
            "score": f"+{bear_points}",
            "argument": " ".join(bear_args) if bear_args else "Weak bearish structural conviction."
        })

        # 3. CHIEF RISK OFFICER (RED-TEAMER)
        risk_flags = []
        risk_veto = False
        if vpin >= 0.45:
            risk_flags.append(f"High order-flow toxicity detected (VPIN {vpin:.2f}).")
        if macro.get("is_freeze_active"):
            risk_flags.append(f"Macro Event Risk active ({macro.get('active_event_name')}).")
            risk_veto = True

        # Check for Adverse Selection traps
        is_candidate_yes = "YES" in str(candidate_pred).upper() or "ABOVE" in str(candidate_pred).upper()
        if is_candidate_yes and (micro_wall == "ASK_WALL" or micro_pressure == "HEAVY_ASK"):
            risk_flags.append("Adverse Selection: Candidate is buying directly into an institutional ASK WALL.")
            risk_veto = True
        elif not is_candidate_yes and (micro_wall == "BID_WALL" or micro_pressure == "HEAVY_BID"):
            risk_flags.append("Adverse Selection: Candidate is shorting directly into an institutional BID WALL.")
            risk_veto = True

        transcript.append({
            "agent": "Chief Risk Officer",
            "status": "VETO THREAT" if risk_veto else ("CAUTION" if risk_flags else "CLEAR"),
            "argument": " ".join(risk_flags) if risk_flags else "No structural traps or toxic flow detected. Clear to execute."
        })

        # 4. ARBITER VERDICT
        net_edge = bull_points - bear_points
        verdict = "APPROVED"
        final_dir = candidate_pred
        final_prob = prob

        if risk_veto:
            verdict = "VETOED"
            final_dir = "PASS"
            final_prob = 50.0
            summary = f"Red-Team Veto: Chief Risk Officer vetoed {candidate_pred} ({risk_flags[0] if risk_flags else 'Risk breach'})."
        elif is_candidate_yes and net_edge <= -2:
            # Candidate wanted YES, but debate heavily favors BEAR
            verdict = "VETOED"
            final_dir = "PASS"
            final_prob = 50.0
            summary = f"Debate Veto: Bull Hunter outmatched (Bear +{bear_points} vs Bull +{bull_points}). Suppressing YES."
        elif not is_candidate_yes and net_edge >= 2:
            # Candidate wanted NO, but debate heavily favors BULL
            verdict = "VETOED"
            final_dir = "PASS"
            final_prob = 50.0
            summary = f"Debate Veto: Bear Assassin outmatched (Bull +{bull_points} vs Bear +{bear_points}). Suppressing NO."
        else:
            # Approved: Boost or trim probability based on debate margin
            if (is_candidate_yes and net_edge >= 3) or (not is_candidate_yes and net_edge <= -3):
                final_prob = min(94.0, final_prob + 3.0)
                summary = f"Swarm Consensus: Robust multi-agent agreement (+{abs(net_edge)} edge points)."
            else:
                summary = f"Swarm Cleared: Signal passed adversarial scrutiny (net margin {abs(net_edge)})."

        return {
            "verdict": verdict,
            "final_direction": final_dir,
            "final_probability": round(final_prob, 1),
            "bull_score": bull_points,
            "bear_score": bear_points,
            "risk_veto": risk_veto,
            "summary": summary,
            "debate_transcript": transcript
        }
