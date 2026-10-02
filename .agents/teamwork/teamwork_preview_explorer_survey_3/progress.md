# Progress — Explorer Survey 3

Last visited: 2026-09-30T19:12:00Z
Status: Investigation complete. Compiling analysis.md and handoff.md.

Completed Steps:
- Explored risk management architecture across `risk_manager.py`, `executor.py`, `stop_manager.py`, and `fees.py`.
- Explored capital allocation, position sizing, Half-Kelly criterion, and affordability checks.
- Explored execution assumptions, slippage buffer ($0.04), latency tax ($0.01), and simulated book depth.
- Identified and empirically ran existing backtesting tools (`backtest.py`, `evaluate_previous_trades.py`, `backtest_rl.py`, and `backtester_sim.py`).
- Located all historical datasets (`kalshi_btc15m_history.jsonl`, `coinbase_btc15m_history.csv`, `historical_candles_btc_15m.csv`, `backtest_candles_cache.json`, `trades.db`, `trades_history.json`).
- Discovered critical defects and divergences:
  1. `backend/btc/auto_executor/saas_broadcaster.py`: line 228-236 IndentationError blocks importing AutoExecutor and breaks `test_risk_budget.py`.
  2. `backend/btc/ml_engine.py`: lines 220-223 vs 445-510 missing `ndq_roc`, `dxy_roc`, `vsa_absorption`, `sfp_score` in `build_feature_row`, breaking `test_build_feature_row_returns_all_keys`.
  3. `backend/btc/kalshi_trader.py`: line 1079 paper fills bypass simulated depth and slippage buffer, causing 4 failures in `test_paper_trading_realism.py`.
  4. `backend/btc/backtester_sim.py`: hardcoded static HTML metrics (71.4% WR, 2.14 PF, -11.2% Max DD).
  5. In-sample trade evaluation (`evaluate_previous_trades.py`) claims 72.66% win rate by ignoring Kalshi taker fees (7%) and spread, while actual historical trades achieved only 48.3% - 49.13% win rate and negative PnL.
  6. Strict walk-forward out-of-sample backtests reveal 47.3% - 50.8% accuracy (worse than or equal to a coin toss) and Profit Factor 0.89.

Next Steps:
- Write comprehensive `analysis.md`.
- Update `BRIEFING.md`.
- Write 5-component `handoff.md`.
- Send completion message to orchestrator_1.
