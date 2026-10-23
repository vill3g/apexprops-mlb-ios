"""
FastAPI Routes for ShadowTrader Quant Lab & Strategy Graveyard.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.engine.quant_lab.graveyard import StrategyGraveyard, StrategyRegistry
from backend.engine.quant_lab.incubator import PaperIncubator
from backend.engine.quant_lab.orchestrator import QuantLabOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quant-lab", tags=["Quant Lab"])
_orchestrator = QuantLabOrchestrator()
_incubator = PaperIncubator()


class CycleRunRequest(BaseModel):
    asset: str = "BTC"
    target_interval: str = "15m"
    market_regime: Optional[Dict[str, Any]] = None


@router.get("/overview")
def get_quant_lab_overview() -> Dict[str, Any]:
    """Summary overview for the Quant Lab dashboard panel."""
    try:
        stats = StrategyGraveyard.get_stats()
        recent_graveyard = StrategyGraveyard.get_entries(limit=10)
        incubating = _incubator.get_active_incubating()
        graduated = StrategyRegistry.list_strategies(status="GRADUATED", limit=10)
        all_strategies = StrategyRegistry.list_strategies(limit=20)

        trades = _incubator.get_incubation_trades(limit=100)
        # Attach recent trades directly to their strategy object
        trades_by_strat = {}
        for t in trades:
            sid = t.get("strategy_id")
            if sid:
                trades_by_strat.setdefault(sid, []).append(t)

        for s in incubating:
            s["trades"] = trades_by_strat.get(s["strategy_id"], [])

        return {
            "success": True,
            "stats": stats,
            "incubating_count": len(incubating),
            "graduated_count": len(graduated),
            "recent_graveyard": recent_graveyard,
            "incubating": incubating,
            "recent_forward_trades": trades,
            "graduated": graduated,
            "recent_strategies": all_strategies
        }
    except Exception as e:
        logger.error(f"[QuantLabRoute] Overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graveyard")
def get_graveyard_entries(
    asset: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
) -> Dict[str, Any]:
    """Fetch persistent graveyard entries and failure post-mortems."""
    try:
        entries = StrategyGraveyard.get_entries(limit=limit, asset=asset)
        stats = StrategyGraveyard.get_stats()
        return {
            "success": True,
            "total": len(entries),
            "stats": stats,
            "entries": entries
        }
    except Exception as e:
        logger.error(f"[QuantLabRoute] Graveyard query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/incubator")
def get_incubator_strategies(asset: Optional[str] = None) -> Dict[str, Any]:
    """Fetch currently active incubating paper strategies."""
    try:
        active = _incubator.get_active_incubating(asset=asset)
        trades = _incubator.get_incubation_trades(limit=50)
        return {
            "success": True,
            "count": len(active),
            "strategies": active,
            "recent_forward_trades": trades
        }
    except Exception as e:
        logger.error(f"[QuantLabRoute] Incubator query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cycle/run")
def run_research_cycle(req: CycleRunRequest) -> Dict[str, Any]:
    """
    Triggers an on-demand multi-agent research cycle.
    Idea -> Code -> Backtest -> Incubator / Graveyard.
    """
    try:
        report = _orchestrator.run_research_cycle(
            asset=req.asset,
            target_interval=req.target_interval,
            market_regime=req.market_regime
        )
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        logger.error(f"[QuantLabRoute] Cycle execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy/{strategy_id}/promote")
def promote_strategy(strategy_id: str) -> Dict[str, Any]:
    """Promotes an incubating or graduated strategy to production status."""
    try:
        strat = StrategyRegistry.get_by_id(strategy_id)
        if not strat:
            raise HTTPException(status_code=404, detail="Strategy not found")

        StrategyRegistry.update_status(strategy_id, "PRODUCTION_ACTIVE")
        return {
            "success": True,
            "message": f"Strategy '{strat['name']}' promoted to active production trading.",
            "strategy": strat
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[QuantLabRoute] Promotion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
