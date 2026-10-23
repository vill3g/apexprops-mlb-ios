# TEST_INFRA.md: Comprehensive Test Architecture & Verification Matrix (Tiers 1–4)

**Project:** ShadowTrader AI / Kalshi AI Trader (`kalshi-ai-trader`)  
**Specification Reference:** `PROJECT.md`, `ORIGINAL_REQUEST.md` (2026-10-07T20:53:32Z), `DISPATCH.md`  
**Test Runner:** `pytest` (via `.venv\Scripts\python.exe -m pytest`)  
**Target Coverage:** Requirements R1 (PPO Transformer RL Agent), R2 (Voting Classifier Ensemble & Kelly Sizing), and R3 (Execution Paths Integration & Regression Hardening)

---

## 1. Test Architecture Overview

The test architecture provides rigorous, opaque-box and behavioral verification across four tiers, structured to prevent regressions and certify high-conviction algorithmic trading logic:

```
                            TEST HARNESS ARCHITECTURE
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                         Tier 4: Real-World Scenarios                        │
 │   - Simulated 15m paper trading cycle (Worker & SaaS Broadcaster)           │
 │   - End-to-end shadow trade generation, execution, and persistence         │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │                     Tier 3: Cross-Feature Combinations                      │
 │   - RL continuous action integration with contract_eval and shadow executor │
 │   - ML Voting consensus interaction with user risk caps and fee structures   │
 │   - Backward compatibility preservation (DQN adapters, GodTierEnsemble)     │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │                      Tier 2: Boundary & Corner Cases                        │
 │   - Edge probabilities: p=0.50 (deadband), p=1.0, p=0.0                    │
 │   - Ask price bounds: 0.01 and 0.99 extremes                                │
 │   - Negative Kelly edge handling & zero bankroll safeguards                 │
 │   - Shape flexibility: 1D list (66,), 1D array (66,), 2D tensor (B, 66)    │
 ├─────────────────────────────────────────────────────────────────────────────┤
 │                          Tier 1: Feature Coverage                           │
 │   - PyTorch nn.TransformerEncoder & positional encodings (d_model=64, n=4)  │
 │   - 3D Continuous action heads: direction, dynamic sizing, target price     │
 │   - Critic value function head V(s) and PPO clipped surrogate loss / GAE    │
 │   - VotingEnsemble training & soft-voting across XGBoost, LightGBM, CatBoost│
 │   - Closed-form Kelly Criterion math: f* = (p - C) / (1 - C)                │
 │   - Consensus amplification: Half-Kelly (lambda=0.50) on 3/3 unanimity      │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Test Suites & Module Ownership

The test suite is organized into three dedicated test files in `tests/`:

| Test Suite | Target Modules | Primary Scope | Tiers |
| :--- | :--- | :--- | :--- |
| `tests/test_ppo_transformer.py` | `backend/btc/rl_agent.py` | PPO Transformer architecture, positional encoding, continuous heads, critic head, PPO loss/GAE, and backward compatibility hooks. | Tiers 1, 2 |
| `tests/test_voting_ensemble_kelly.py` | `backend/btc/ml_ensemble.py`, `backend/btc/fees.py`, `backend/btc/ml_engine.py` | Unified Voting Classifier (XGBoost + LightGBM + CatBoost), consensus detection, closed-form Kelly Criterion math, consensus amplification, and edge cases. | Tiers 1, 2 |
| `tests/test_m3_m4_model_integration.py` | `backend/btc/analyzer/contract_eval.py`, `backend/btc/shadow_executor.py`, `backend/btc/auto_executor/saas_broadcaster.py`, `backend/btc/auto_executor/executor.py` | Cross-feature integration, 66-dim tensor dimension safety across callers, simulated paper-trading execution loops, and zero regression checks. | Tiers 3, 4 |

---

## 3. Detailed Verification Matrix (Tiers 1–4)

### Tier 1: Feature Coverage

| ID | Test Function | Target Feature | Authoritative Specification | Expected Outcome / Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **T1.RL.1** | `test_transformer_encoder_architecture` | PyTorch `nn.TransformerEncoder` backbone | `PROJECT.md` § Architecture (RL Engine), `survey_rl_report.md` | Network contains `nn.TransformerEncoder` with `d_model=64`, `nhead=4`, 2 layers, and positional encoding on 25 sequence features (5 lags $\times$ 5 indicators). |
| **T1.RL.2** | `test_continuous_action_heads` | 3D Continuous Action Space | `PROJECT.md` § Architecture (RL Engine) | Policy outputs bounded continuous actions: $a_{\text{dir}} \in [-1, 1]$, $a_{\text{size}} \in [0, 1]$, and $a_{\text{price}} \in [0.01, 0.99]$. |
| **T1.RL.3** | `test_critic_value_head` | Critic Value Head $V(s)$ | `PROJECT.md` § Architecture (RL Engine) | Critic head outputs a scalar state value $V(s) \in \mathbb{R}$ for state evaluation. |
| **T1.RL.4** | `test_ppo_clipped_loss_and_buffer` | PPO Clipped Loss & Buffer | `PROJECT.md` § Architecture (RL Engine), `survey_rl_report.md` | Rollout buffer stores transitions and `train_step()` computes clipped surrogate objective $L^{\text{CLIP}}$, value loss $L^{\text{VF}}$, and entropy bonus. |
| **T1.RL.5** | `test_rl_backward_compatibility_adapters` | RL Backward Compatibility | `PROJECT.md` § Interface Contracts (`select_action`, `q_values`, `epsilon`, `memory`) | `select_action(s)` returns discrete $\{0, 1, 2\}$, `q_values(s)` returns length-3 array preserving directional slope, attributes `epsilon` and `memory` exist. |
| **T1.ML.1** | `test_voting_ensemble_simultaneous_fit` | Multi-Model Fitting | `PROJECT.md` § Architecture (ML Engine), `survey_ml_report.md` | `VotingEnsemble` simultaneously fits XGBoost, LightGBM, and CatBoost (or graceful shims). |
| **T1.ML.2** | `test_voting_ensemble_soft_voting_predict` | Soft Voting Inference | `PROJECT.md` § Architecture (ML Engine) | `predict_proba` returns soft-voting probabilities averaging member model probabilities. |
| **T1.ML.3** | `test_consensus_detection_logic` | Model Consensus & Unanimity | `PROJECT.md` § Architecture & Interface Contracts | Evaluates agreement ratio: 3/3 unanimous ($1.0$, `is_unanimous=True`), 2/3 majority ($0.67$, `is_unanimous=False`), and probability dispersion spread. |
| **T1.ML.4** | `test_closed_form_kelly_math` | Closed-Form Binary Kelly | `PROJECT.md` § Interface Contracts: $f^* = \frac{p - C}{1.0 - C}$ | Given $p$, ask price, and taker fees $C = P_{\text{eff}} + \text{Fee}$, computes exact theoretical Kelly fraction. |
| **T1.ML.5** | `test_consensus_kelly_amplification` | Kelly Consensus Amplification | `PROJECT.md` § Architecture: Half-Kelly on Unanimity | Unanimous agreement applies Half-Kelly ($\lambda=0.50$, doubling allocation vs majority at $\lambda=0.25$). |
| **T1.ML.6** | `test_ml_backward_compatibility_alias` | `GodTierEnsemble` Alias | `PROJECT.md` § Feature Inventory #9 | `from backend.btc.ml_ensemble import GodTierEnsemble` succeeds and functions as `VotingEnsemble`. |

---

### Tier 2: Boundary & Corner Cases

| ID | Test Function | Target Scenario | Authoritative Specification | Expected Outcome / Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **T2.RL.1** | `test_tensor_dimension_safety_1d_vs_2d` | Tensor Shape Flexibility | `survey_integration_report.md` § 6.1 | Model accepts flat 66-float list, 1D numpy array `(66,)`, and batched 2D tensor `(B, 66)` without throwing dimensionality exceptions. |
| **T2.RL.2** | `test_action_head_boundary_clamping` | Extreme Logit Inputs | Mathematical bounds of tanh/sigmoid | Direction strictly in $[-1, 1]$, sizing strictly in $[0, 1]$, price strictly in $[0.01, 0.99]$ even under extreme saturation. |
| **T2.RL.3** | `test_contract_eval_price_extremes` | Kalshi Price Bounds | Kalshi contract boundaries | Handles extreme ask prices ($0.01$ and $0.99$) safely in `evaluate_contract` without division by zero or NaN. |
| **T2.ML.1** | `test_kelly_negative_or_zero_edge` | Negative / Zero Edge Gate | `survey_ml_report.md` § 6.3 | When win probability $p \le C$ (or edge $< 0.01$), recommended contracts and allocation are strictly $0$. |
| **T2.ML.2** | `test_kelly_extreme_probabilities` | Probability Extremes | Probability theory boundaries | At $p=0.50$ (no edge), returns 0 contracts. At $p=1.0$, returns positive fraction bounded by risk caps. |
| **T2.ML.3** | `test_kelly_bankroll_and_risk_caps` | 15% Bankroll & Dollar Caps | `PROJECT.md` § Architecture, `fees.py` | Position size never exceeds 15% of available bankroll or user maximum dollar cap. |
| **T2.ML.4** | `test_graceful_fallback_missing_libraries` | Resilient Dependency Shim | `PROJECT.md` § Feature Inventory #5 | When `lightgbm` or `catboost` are uninstalled or mocked as unavailable, ensemble falls back gracefully without unhandled exceptions. |

---

### Tier 3: Cross-Feature Combinations

| ID | Test Function | Target Modules | Authoritative Specification | Expected Outcome / Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **T3.INT.1** | `test_rl_continuous_output_contract_eval` | `contract_eval.py` + `rl_agent.py` | `PROJECT.md` § Interface Contracts | `evaluate_next_15m_contract` produces augmented forecast containing `p_model`, `action`, `target_limit_price`, `dynamic_sizing_factor`, and `suggested_contracts`. |
| **T3.INT.2** | `test_rl_continuous_shadow_executor` | `shadow_executor.py` + `rl_agent.py` | `PROJECT.md` § Interface Contracts | `execute_shadow_trade` consumes dynamic contract count and target limit price from RL evaluation dictionary. |
| **T3.INT.3** | `test_ml_consensus_saas_broadcaster_sizing` | `saas_broadcaster.py` + `ml_ensemble.py` | `PROJECT.md` § Milestones M3 & M2 | Multi-tenant user trade execution consumes ensemble consensus and adjusts contract size via amplified Kelly. |
| **T3.INT.4** | `test_zero_regression_existing_trading_styles` | `contract_eval.py` (SNIPER, CAPITAL_GUARD, AUTO) | `PROJECT.md` Feature #12 | Existing trading style rules, chart-only isolation, and heuristic vetoes remain fully functional. |

---

### Tier 4: Real-World Application Scenarios

| ID | Test Function | Target Workflow | Authoritative Specification | Expected Outcome / Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **T4.E2E.1** | `test_simulated_paper_trading_cycle_rl` | Paper Trading Cycle (RL Agent) | `ORIGINAL_REQUEST.md` (2026-10-07T20:53:32Z) Acceptance Criteria | Executes end-to-end paper trading evaluation cycle with synthetic 15m candle indicators, confirms valid paper trade submission with zero runtime exceptions or dimensionality errors. |
| **T4.E2E.2** | `test_simulated_paper_trading_cycle_ml` | Paper Trading Cycle (ML Voting Ensemble) | `ORIGINAL_REQUEST.md` Acceptance Criteria | Executes end-to-end paper trading evaluation cycle using Voting Classifier ensemble, confirms consensus calculation and paper trade submission with zero errors. |
| **T4.E2E.3** | `test_shadow_trade_logging_and_replay_cycle` | Shadow Trade Cycle | `shadow_executor.py` + `rl_agent.py` | Generates shadow trade, verifies persistence in shadow log, and completes simulated settlement update via `agent.train_step()` without crashing. |

---

## 4. Execution Protocol & Verification Commands

Tests are executed within the project virtual environment:

```powershell
# 1. Run RL PPO Transformer Suite (Tiers 1 & 2)
.venv\Scripts\python.exe -m pytest tests/test_ppo_transformer.py -v

# 2. Run ML Voting Ensemble & Kelly Suite (Tiers 1 & 2)
.venv\Scripts\python.exe -m pytest tests/test_voting_ensemble_kelly.py -v

# 3. Run End-to-End Model Integration & Paper Trading Suite (Tiers 3 & 4)
.venv\Scripts\python.exe -m pytest tests/test_m3_m4_model_integration.py -v

# 4. Run Complete Test Suite
.venv\Scripts\python.exe -m pytest tests/test_ppo_transformer.py tests/test_voting_ensemble_kelly.py tests/test_m3_m4_model_integration.py -v
```

---

## 5. Pass / Fail Criteria for Certification (`TEST_READY.md`)

The test suite achieves **TEST_READY** certification only when:
1. **100% Pass Rate**: Every test in `tests/test_ppo_transformer.py`, `tests/test_voting_ensemble_kelly.py`, and `tests/test_m3_m4_model_integration.py` exits with status `PASSED`.
2. **Zero Facade Tests**: All tests execute real mathematical operations, neural network forward/backward passes, or live trading pipeline workflows.
3. **Dimensionality Safety Verified**: Tested explicitly with 66-dim 1D inputs and batched inputs.
4. **No Regression**: Existing test suites (`tests/test_analyzer_blend.py`, etc.) continue to pass cleanly.
