# Project: ShadowTrader AI Trading Engine Upgrade (PPO Transformer + Voting Ensemble)

## Architecture
- **Reinforcement Learning Engine (`backend/btc/rl_agent.py`)**:
  - Upgraded from Dueling Double DQN / LSTM to Proximal Policy Optimization (PPO) Actor-Critic.
  - Backbone: 2-layer Pre-LN PyTorch `nn.TransformerEncoder` ($d_{\text{model}}=64$, $n_{\text{head}}=4$, SiLU) with time-series positional encoding on 25 sequence features (5 lags $\times$ 5 indicators) fused with 41 static features.
  - Continuous Action Space ($\mathbb{R}^3$): Directional conviction ($a_{\text{dir}} \in [-1, 1]$), dynamic order sizing ($a_{\text{size}} \in [0, 1] \implies N_{\text{contracts}}$), and target limit price ($a_{\text{price}} \in [0.01, 0.99]$).
  - Critic Head: State value estimator $V(s) \in \mathbb{R}$.
  - Loss Function: PPO clipped surrogate objective ($L^{\text{CLIP}}$), critic MSE loss ($L^{\text{VF}}$), entropy bonus ($S[\pi]$), and GAE-$\lambda$ advantage estimation.
  - Backward Compatibility: Adapters for `select_action(state)` $\rightarrow \{0, 1, 2\}$, `q_values(state)` pseudo-Q values, `policy_net`, `target_net`, `epsilon`, `memory`, and safe checkpoint loading migration.

- **Classical ML Engine (`backend/btc/ml_ensemble.py`, `ml_engine.py`)**:
  - Upgraded to a unified `VotingEnsemble` simultaneously training and evaluating `XGBoost`, `LightGBM`, and `CatBoost` models (with fallback shims for environment resilience).
  - Consensus Engine: Evaluates directional agreement ratio (unanimous 3/3 = 1.0 vs majority 2/3 = 0.67) and dispersion spread across all 3 models.
  - Kelly Criterion Position Sizing: Closed-form binary contract formula $f^* = \frac{p - C}{1.0 - C}$ where $C = P_{\text{eff}} + \text{TakerFee}$.
  - Consensus Amplification: Unanimous agreement triggers Half-Kelly ($\lambda = 0.50$, doubling allocation vs majority at $\lambda = 0.25$), bounded by a 15% single-trade bankroll cap and daily risk limits.
  - Backward Compatibility: `GodTierEnsemble = VotingEnsemble` alias and backward-compatible prediction methods.

- **Execution & Integration Engine (`backend/worker.py`, `saas_broadcaster.py`, `executor.py`, `contract_eval.py`)**:
  - Live and paper trading execution loops consume PPO continuous action outputs (`target_limit_price`, `dynamic_contracts`) and ML consensus Kelly sizing.
  - 1D 66-feature tensor dimension safety across all callers (`shadow_executor.py`, `contract_eval.py`).
  - Zero regressions to existing trading styles (SNIPER, CAPITAL_GUARD, AUTO, etc.), user configs, and manual trading routes.

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | PPO Actor-Critic Transformer Architecture | Replace LSTM with `nn.TransformerEncoder` ($d_{\text{model}}=64$, $n_{\text{head}}=4$, positional encodings) on sequence features fused with static features | M1 | Explorer 1 |
| 2 | Continuous Action Space Heads | Actor heads for directional conviction ($a_{\text{dir}}$), dynamic order sizing ($a_{\text{size}}$), and target limit price ($a_{\text{price}}$) | M1 | Explorer 1 |
| 3 | PPO Loss & GAE Rollout Buffer | Clipped surrogate policy loss, value MSE loss, entropy bonus, and Generalized Advantage Estimation (GAE) | M1 | Explorer 1 |
| 4 | RL Backward Compatibility Layer | Adapters for `select_action`, `q_values`, `evaluate_contract`, `policy_net`, `epsilon`, `memory`, and safe checkpoint migration | M1 | Explorer 1 |
| 5 | Environment Dependencies & Shims | Update `requirements.txt` with `lightgbm` and `catboost`, install libraries, and provide graceful import fallback shims | M2 | Explorer 2 |
| 6 | Unified Voting Classifier Ensemble | `VotingEnsemble` training and predicting simultaneously across XGBoost, LightGBM, and CatBoost | M2 | Explorer 2 |
| 7 | Multi-Model Consensus Engine | Calculate prediction consensus, directional agreement ratio (3/3 vs 2/3), and probability dispersion | M2 | Explorer 2 |
| 8 | Kelly Criterion Consensus Sizing | Binary contract formula $f^* = (p - C) / (1 - C)$ with consensus amplification ($\lambda = 0.50$ on unanimity vs $\lambda = 0.25$ on majority) | M2 | Explorer 2 |
| 9 | ML Backward Compatibility Layer | Maintain `GodTierEnsemble` alias, SHAP reasoning compatibility, and seamless integration with `MLEngine` & `DualMLEngine` | M2 | Explorer 2 |
| 10 | Contract Evaluator Integration | Wire PPO continuous outputs and ML consensus Kelly sizing into `contract_eval.py` with 66-dim tensor shape safety | M3 | Explorer 3 |
| 11 | Execution Paths (Live & Paper) Integration | Connect dynamic contract sizing and target limit pricing into `saas_broadcaster.py`, `executor.py`, and `shadow_executor.py` | M3 | Explorer 3 |
| 12 | Zero-Regression & Config Safety | Ensure SQLite user configs, trading styles (AUTO, SNIPER, etc.), and manual 1-click execution remain completely unaffected | M3 | Explorer 3 |
| 13 | E2E Opaque-Box Test Suite | Comprehensive test suite covering Tiers 1-4 (PPO Transformer, Voting Ensemble, Kelly sizing, and Paper Trading cycles) | E2E Track | Explorer 3 |
| 14 | Adversarial Hardening & Forensic Audit | Stress testing, edge cases, zero-latency book walking, and forensic integrity verification | Final Milestone | All |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | PPO Transformer RL Architecture (R1) | Features 1-4: `backend/btc/rl_agent.py`, `train_rl_full.py`, `calibrate_rl.py` | None | DONE |
| M2 | ML Voting Classifier Ensemble & Kelly Sizing (R2) | Features 5-9: `requirements.txt`, `backend/btc/ml_ensemble.py`, `ml_engine.py`, `fees.py` | None | DONE |
| M3 | Execution Paths Integration & Regression Hardening (R3) | Features 10-12: `contract_eval.py`, `shadow_executor.py`, `saas_broadcaster.py`, `executor.py` | M1, M2 | DONE |
| E2E | E2E Testing Suite Track | Feature 13: Test harness, Tiers 1-4 opaque-box tests, `TEST_READY.md` | Independent | DONE |
| M4 | Final Milestone: 100% Test Pass & Adversarial Hardening | Feature 14: Tier 5 adversarial verification, forensic integrity audit | M1, M2, M3, E2E | DONE |

---

## Interface Contracts

### RL Agent Contract (`backend/btc/rl_agent.py`)
- `evaluate_contract(state, kalshi_market)`:
  - Input: `state` (66-dim list/1D tensor), `kalshi_market` (dict).
  - Output: `dict` containing `p_model` (float), `action` (int: 0, 1, 2), `action_name` (str), `target_limit_price` (float $\in [0.01, 0.99]$), `dynamic_sizing_factor` (float $\in [0.0, 1.0]$), `dynamic_contracts` (int $\ge 1$), `v_state` (float).
- `select_action(state)`: Returns `int` in `{0, 1, 2}`.
- `q_values(state)`: Returns `np.ndarray` of shape `(3,)` preserving directional calibration slope.

### ML Ensemble Contract (`backend/btc/ml_ensemble.py`)
- `predict_consensus(X)`:
  - Input: feature vector or array of shape `(n_samples, n_features)` or `(n_features,)`.
  - Output: `dict` containing:
    - `p_ensemble`: float $\in [0, 1]$
    - `individual_probs`: `{"xgb": float, "lgb": float, "cb": float}`
    - `agreement_ratio`: float $\in [0.0, 1.0]$ (1.0 = unanimous 3/3, 0.67 = majority 2/3)
    - `is_unanimous`: bool
    - `consensus_direction`: str (`"YES"`, `"NO"`, or `"NEUTRAL"`)
- `calculate_kelly_wager(p_win, ask_price, bankroll, is_unanimous)`:
  - Input: `p_win` (float), `ask_price` (float), `bankroll` (float), `is_unanimous` (bool).
  - Output: `dict` with `f_star` (float), `kelly_fraction` (float: 0.50 on unanimity, 0.25 on majority), `allocated_dollars` (float), `recommended_contracts` (int).

---

## Code Layout
- RL Architecture: `backend/btc/rl_agent.py`, `backend/btc/train_rl_full.py`, `backend/scripts/calibrate_rl.py`
- ML Ensemble: `backend/btc/ml_ensemble.py`, `backend/btc/ml_engine.py`, `backend/btc/fees.py`, `requirements.txt`
- Execution & Integration:
  - `backend/btc/analyzer/contract_eval.py`: Forecast evaluation router
  - `backend/btc/shadow_executor.py`: RL shadow trading sandbox
  - `backend/btc/auto_executor/saas_broadcaster.py`: Multi-tenant live/paper execution engine
  - `backend/btc/auto_executor/executor.py`: Primary auto-executor loop
  - `backend/worker.py`: Background worker daemon
- Testing:
  - `tests/test_ppo_transformer.py`: RL PPO Transformer tests (Tier 1-2)
  - `tests/test_voting_ensemble_kelly.py`: ML Voting Classifier & Kelly tests (Tier 1-2)
  - `tests/test_m3_m4_model_integration.py`: End-to-end integration & paper trading tests (Tier 3-4)
