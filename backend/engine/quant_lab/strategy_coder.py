"""
Quant Coder for ShadowTrader Quant Lab.
Compiles hypotheses into deterministic, sandboxed Python strategy evaluators
with AST safety verification.
"""
from __future__ import annotations

import ast
import hashlib
import logging
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Strict AST safety blacklist
FORBIDDEN_CALLS = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "getattr", "setattr", "delattr",
    "subprocess", "os", "sys", "socket", "urllib", "requests"
}


class StrategySecurityError(Exception):
    pass


def verify_code_safety(code_str: str) -> None:
    """Verifies that generated code contains zero malicious or un-sandboxed operations."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        raise StrategySecurityError(f"Syntax error in strategy code: {e}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise StrategySecurityError("Explicit imports are disallowed in sandboxed strategy code.")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                raise StrategySecurityError(f"Prohibited function call: {node.func.id}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALLS:
                raise StrategySecurityError(f"Prohibited attribute call: {node.func.attr}")


class StrategyCoder:
    """Translates hypothesis definitions into sandboxed Python strategy code."""

    @staticmethod
    def generate_code(hypothesis: Dict[str, Any]) -> Tuple[str, str]:
        """
        Returns (code_string, code_hash).
        """
        name = hypothesis.get("name", "Unnamed Strategy")
        target_side = hypothesis.get("target_side", "YES").upper()
        conditions = hypothesis.get("entry_conditions", [])
        sl = float(hypothesis.get("stop_loss_pct", 25.0))
        tp = float(hypothesis.get("take_profit_pct", 35.0))
        max_p = float(hypothesis.get("max_entry_price", 0.75))
        min_p = float(hypothesis.get("min_entry_price", 0.25))

        # Feature names that can be referenced on the right-hand side of a condition
        FEATURE_NAMES = {
            "ema_slow", "ema_trend", "ema_fast", "ema_9", "ema_21", "ema_50", "ema_200",
            "bb_upper", "bb_lower", "bb_middle", "open", "close", "high", "low", "vwap"
        }

        # Build condition clauses safely
        clauses = []
        for c in conditions:
            ind = c.get("indicator")
            op = c.get("operator")
            thresh_raw = c.get("threshold", 0.0)
            if op not in ("<", "<=", ">", ">=", "==", "!="):
                op = ">"

            # 1. Bollinger Band intelligent translation (handle 0.0 threshold or %b threshold)
            if ind == "bb_lower":
                try:
                    f_val = float(thresh_raw)
                except Exception:
                    f_val = 0.0
                if f_val <= 10.0:
                    # Low threshold indicates intent for price touching or penetrating lower band
                    pct_b_lim = max(0.05, min(0.35, f_val if 0.0 < f_val <= 1.0 else 0.15))
                    clauses.append(f'((features.get("close", 0.0) <= features.get("bb_lower", 0.0)) or (features.get("bb_percent_b", 0.5) <= {pct_b_lim}))')
                    continue
            elif ind == "bb_upper":
                try:
                    f_val = float(thresh_raw)
                except Exception:
                    f_val = 0.0
                if f_val <= 10.0:
                    # Low threshold indicates intent for price touching or penetrating upper band
                    pct_b_lim = max(0.65, min(0.95, f_val if 0.0 < f_val <= 1.0 else 0.85))
                    clauses.append(f'((features.get("close", 0.0) >= features.get("bb_upper", 0.0)) or (features.get("bb_percent_b", 0.5) >= {pct_b_lim}))')
                    continue

            # 2. EMA comparison against another indicator
            if isinstance(thresh_raw, str) and not thresh_raw.replace(".", "", 1).replace("-", "", 1).isdigit():
                if thresh_raw.lower() in FEATURE_NAMES:
                    # Comparison against another feature (e.g. features.get("ema_slow", 0.0))
                    clauses.append(f'(features.get("{ind}", 0.0) {op} features.get("{thresh_raw}", 0.0))')
                else:
                    # String literal comparison (e.g. regime matches)
                    clauses.append(f'(str(features.get("{ind}", "")).upper() {op} "{thresh_raw.upper()}")')
            else:
                try:
                    thresh = float(thresh_raw)
                except Exception:
                    thresh = 0.0
                clauses.append(f'(features.get("{ind}", 0.0) {op} {thresh})')

        full_condition = " and ".join(clauses) if clauses else "False"

        # Extract target regimes and baseline edge
        target_regimes = hypothesis.get("target_regimes")
        if not target_regimes:
            single_reg = hypothesis.get("target_regime") or hypothesis.get("conditioned_regime")
            target_regimes = [single_reg] if single_reg else []
        target_regimes_repr = repr([str(r).upper() for r in target_regimes])
        base_edge = float(hypothesis.get("base_edge", 0.06))

        code = f'''# Strategy: {name}
# Target Side: {target_side}

def evaluate_signal(snapshot):
    """
    Evaluates market snapshot features and returns signal action.
    Returns: dict(action="BUY"|"PASS", side="YES"|"NO", confidence=float,
                  calibrated_win_prob=float, f_star=float, kelly_fraction=float, ...)
    """
    if not isinstance(snapshot, dict):
        return {{"action": "PASS", "reason": "invalid_snapshot"}}

    features = snapshot.get("raw_features") or snapshot.get("indicators") or snapshot
    cur_price = float(snapshot.get("cur_price") or snapshot.get("yes_bid") or snapshot.get("entry_price") or 0.50)
    cur_price = max(0.01, min(0.99, cur_price))

    # Price corridor check
    if cur_price < {min_p} or cur_price > {max_p}:
        return {{"action": "PASS", "reason": "price_outside_corridor", "cur_price": cur_price}}

    # Regime conditioning check (gracefully passes if snapshot has no regime or strategy targets any)
    target_regs = {target_regimes_repr}
    snap_regime = str(
        snapshot.get("market_regime") or snapshot.get("regime") or snapshot.get("regime_slug") or
        features.get("market_regime") or features.get("regime") or features.get("regime_slug") or ""
    ).upper()
    if target_regs and snap_regime:
        norm_snap = snap_regime.replace("/", "_").replace("-", "_").replace(" ", "_")
        matched_reg = False
        for r in target_regs:
            norm_r = r.replace("/", "_").replace("-", "_").replace(" ", "_")
            if norm_r in norm_snap or norm_snap in norm_r:
                matched_reg = True
                break
        if not matched_reg:
            return {{"action": "PASS", "reason": "regime_mismatch", "detected_regime": snap_regime}}

    # Rule evaluation
    matched = {full_condition}
    if not matched:
        return {{"action": "PASS", "reason": "conditions_not_met"}}

    # Target side executable cost basis
    target_side = "{target_side}"
    side_cost = cur_price if target_side == "YES" else (1.0 - cur_price)
    side_cost = max(0.02, min(0.98, side_cost))

    # Dynamic Calibrated Win Probability
    # 1. Determine Model / Signal Probability
    p_raw = None
    if "ai_win_prob" in features:
        raw_prob = float(features.get("ai_win_prob", 50.0))
        prob_norm = (raw_prob / 100.0) if raw_prob > 1.0 else raw_prob
        p_raw = prob_norm if target_side == "YES" else (1.0 - prob_norm)
    elif "p_ensemble" in features or "ml_prob" in features:
        raw_prob = float(features.get("p_ensemble") or features.get("ml_prob") or 0.50)
        p_raw = raw_prob if target_side == "YES" else (1.0 - raw_prob)

    if p_raw is None:
        # Technical Indicator Dynamic Edge Adjustment
        sig_boost = 0.0
        if "rsi" in features:
            rsi_val = float(features.get("rsi", 50.0))
            sig_boost = sig_boost + min(0.06, abs(rsi_val - 50.0) / 200.0)
        if "price_drift" in features:
            drift_val = float(features.get("price_drift", 0.0))
            sig_boost = sig_boost + min(0.05, abs(drift_val) * 1.2)
        p_raw = side_cost + {base_edge} + sig_boost

    p_raw = max(0.05, min(0.95, p_raw))

    # 2. Bayesian Shrinkage / Calibration towards market prior
    alpha_cal = 0.65
    if "WHIPSAW" in snap_regime or "EVENT" in snap_regime:
        alpha_cal = 0.45
    elif "EXPANSION" in snap_regime or "MOMENTUM" in snap_regime:
        alpha_cal = 0.70

    calibrated_prob = (alpha_cal * p_raw) + ((1.0 - alpha_cal) * side_cost)
    calibrated_prob = max(0.05, min(0.95, calibrated_prob))

    # Dynamic Kelly Criterion Sizing Fraction
    # Dynamic Kalshi taker fee: ceil(0.07 * P * (1-P) * 100) / 100
    fee = int(0.07 * side_cost * (1.0 - side_cost) * 100.0 + 0.9999) / 100.0
    c_eff = min(0.98, side_cost + fee)
    edge = calibrated_prob - c_eff

    if edge > 0.0 and c_eff < 1.0:
        f_star = (calibrated_prob - c_eff) / (1.0 - c_eff)
        # Fractional Kelly sizing (quarter-Kelly default, scaled down in whipsaw)
        lambda_val = 0.15 if ("WHIPSAW" in snap_regime or "EVENT" in snap_regime) else 0.25
        kelly_fraction = min(0.20, f_star * lambda_val)
    else:
        f_star = 0.0
        kelly_fraction = 0.0

    conf_pct = round(calibrated_prob * 100.0, 2)

    return {{
        "action": "BUY",
        "side": target_side,
        "confidence": conf_pct,
        "win_probability": round(calibrated_prob, 4),
        "calibrated_win_prob": round(calibrated_prob, 4),
        "win_prob": round(calibrated_prob, 4),
        "expected_edge": round(edge, 4),
        "projected_edge": round(edge, 4),
        "f_star": round(f_star, 4),
        "kelly_fraction": round(kelly_fraction, 4),
        "kelly_sizing_fraction": round(kelly_fraction, 4),
        "stop_loss_pct": {sl},
        "take_profit_pct": {tp},
        "reason": "{name} rule matched",
        "market_regime": snap_regime or "UNKNOWN",
        "regime": snap_regime or "UNKNOWN"
    }}
'''
        # Verify AST safety
        verify_code_safety(code)

        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        return code, code_hash

    @staticmethod
    def compile_strategy(code_str: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        """Compiles sandboxed strategy code into an executable Python callable."""
        verify_code_safety(code_str)
        safe_globals: Dict[str, Any] = {
            "__builtins__": {
                "abs": abs, "min": min, "max": max, "round": round,
                "float": float, "int": int, "str": str, "bool": bool,
                "isinstance": isinstance, "dict": dict, "len": len,
                "any": any, "all": all
            }
        }
        local_scope: Dict[str, Any] = {}
        exec(code_str, safe_globals, local_scope)

        if "evaluate_signal" not in local_scope:
            raise StrategySecurityError("Compiled code does not define evaluate_signal(snapshot).")

        return local_scope["evaluate_signal"]
