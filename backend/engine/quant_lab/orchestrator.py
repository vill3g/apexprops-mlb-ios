"""
Quant Lab Orchestrator for ShadowTrader AI.
Coordinates the end-to-end Reflexion Loop:
Hypothesis Generation -> Code Compilation -> Backtest Validation -> Incubation or Graveyard.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.engine.quant_lab.alpha_ideator import AlphaIdeator
from backend.engine.quant_lab.auditor import PostMortemAuditor
from backend.engine.quant_lab.graveyard import StrategyGraveyard, StrategyRegistry
from backend.engine.quant_lab.incubator import PaperIncubator
from backend.engine.quant_lab.strategy_coder import StrategyCoder
from backend.engine.quant_lab.validator import StrategyValidator

logger = logging.getLogger(__name__)


class QuantLabOrchestrator:
    """Orchestrates multi-agent algorithmic research cycles."""

    def __init__(self):
        self.ideator = AlphaIdeator()
        self.incubator = PaperIncubator()

    def run_research_cycle(
        self,
        asset: str = "BTC",
        target_interval: str = "15m",
        market_regime: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a complete quant research cycle:
        1. Query Graveyard for failure memory
        2. Generate new hypothesis
        3. Compile code
        4. Validate against walk-forward historical data
        5. Route to Incubator (if pass) or Graveyard (if fail)
        """
        asset_norm = str(asset or "BTC").upper().strip()
        logger.info(f"[QuantLab] Starting research cycle for {asset_norm} ({target_interval})...")

        # Auto-detect market regime from recent snapshot if not explicitly provided
        if market_regime is None:
            try:
                from backend.engine.quant_lab.regime_classifier import MarketRegimeClassifier
                recent_snaps = StrategyValidator.load_historical_evaluation_snapshots(asset=asset_norm, limit=5)
                if recent_snaps:
                    last_snap = recent_snaps[-1]
                    raw_feats = last_snap.get("raw_features") or last_snap.get("indicators") or last_snap
                    market_regime = MarketRegimeClassifier.classify_market_state(raw_feats, asset=asset_norm)
            except Exception as e:
                logger.debug(f"[QuantLab] Auto regime detection error: {e}")

        # Step 1 & 2: Generate hypothesis conditioned on past mistakes and detected regime
        # Cosmic Genetic Meta-Learning: If high-performing incubator parents exist, breed an evolved offspring
        hypothesis = None
        try:
            from backend.engine.quant_lab.genetic_breeder import GeneticAlphaBreeder
            active_parents = self.incubator.get_active_incubating_strategies(asset=asset_norm)
            if active_parents and len(active_parents) >= 1 and random.random() < 0.40:
                offspring = GeneticAlphaBreeder.evolve_next_generation(active_parents, target_asset=asset_norm, generation_size=1)
                if offspring:
                    hypothesis = offspring[0]
                    logger.info(f"[QuantLab] Cosmic Genetic Breeding selected: Evolving '{hypothesis.get('name')}' from live parents.")
        except Exception as _e_breed:
            logger.debug(f"[QuantLab] Genetic breeding bypassed: {_e_breed}")

        if not hypothesis:
            hypothesis = self.ideator.generate_hypothesis(
                asset=asset_norm,
                target_interval=target_interval,
                market_regime=market_regime
            )
        strategy_id = hypothesis.get("strategy_id", "strat_unknown")
        name = hypothesis.get("name", "Unnamed Strategy")
        hypo_desc = hypothesis.get("hypothesis", "")

        # Step 3: Compile code
        try:
            code, code_hash = StrategyCoder.generate_code(hypothesis)
            strategy_fn = StrategyCoder.compile_strategy(code)
        except Exception as e:
            logger.error(f"[QuantLab] Compilation failure for {name}: {e}")
            return {
                "success": False,
                "stage": "COMPILATION_ERROR",
                "error": str(e),
                "hypothesis": hypothesis
            }

        # Register in strategy registry
        StrategyRegistry.register(
            strategy_id=strategy_id,
            name=name,
            hypothesis=hypo_desc,
            asset=asset_norm,
            code=code,
            target_interval=target_interval,
            status="PROPOSED"
        )

        # Step 4: Validate against historical data
        validation = StrategyValidator.validate(strategy_fn, asset=asset_norm)
        metrics = validation.get("metrics", {})
        passed = validation.get("passed", False)

        # Step 5: Route based on validation
        if passed:
            # Promote to Incubator
            self.incubator.incubate_strategy(
                strategy_id=strategy_id,
                name=name,
                asset=asset_norm,
                code=code
            )
            StrategyRegistry.update_status(strategy_id, "INCUBATING", backtest_metrics=metrics)
            cycle_result = "PROMOTED_TO_INCUBATOR"
            graveyard_id = None
        else:
            # Audit failure and store in Graveyard
            graveyard_id = PostMortemAuditor.audit_backtest_failure(
                strategy_id=strategy_id,
                name=name,
                hypothesis=hypo_desc,
                asset=asset_norm,
                validation_result=validation,
                code_hash=code_hash
            )
            StrategyRegistry.update_status(strategy_id, "GRAVEYARD", backtest_metrics=metrics)
            cycle_result = "COMMITTED_TO_GRAVEYARD"

        logger.info(
            f"[QuantLab] Cycle complete for '{name}'. Result: {cycle_result} "
            f"(WinRate: {metrics.get('win_rate', 0)*100:.1f}%, Sharpe: {metrics.get('sharpe', 0):.2f})"
        )

        return {
            "success": True,
            "result": cycle_result,
            "strategy_id": strategy_id,
            "name": name,
            "asset": asset_norm,
            "hypothesis": hypothesis,
            "code": code,
            "code_hash": code_hash,
            "validation": validation,
            "graveyard_id": graveyard_id
        }
