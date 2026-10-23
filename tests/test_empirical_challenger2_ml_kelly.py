"""
Empirical Stress Test Suite: ML Voting Classifier Ensemble & Kelly Sizing
Author: Challenger 2 (teamwork_preview_challenger_r6_2)
Project Root: C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader

Stress-tests the 6 mission dimensions:
1. Simultaneous training and prediction of XGBoost, LightGBM, and CatBoost.
2. Consensus calculation under boundary conditions (unanimous, 2/3 split, 1/3 split, tight vs wide spread).
3. Kelly Criterion formula verification across wide probability/ask grids.
4. 2.0x consensus amplification verification (lambda=0.50 vs lambda=0.25).
5. 15% bankroll cap enforcement across large bankrolls.
6. Negative / sub-threshold EV gating (< $0.01 EV strictly returns 0 contracts).
7. Interface contract robustness & keyword argument safety on VotingEnsemble.calculate_kelly_wager.
"""

import math
import pytest
import numpy as np
from sklearn.datasets import make_classification

from backend.btc.ml_ensemble import VotingEnsemble, GodTierEnsemble, HAS_XGBOOST, HAS_LIGHTGBM, HAS_CATBOOST
from backend.btc.fees import calculate_binary_kelly_position, calculate_kelly_wager as fees_calculate_kelly_wager


# =====================================================================
# 1. SIMULTANEOUS TRAINING AND PREDICTION ACROSS 3 BOOSTING ENGINES
# =====================================================================

class TestSimultaneousTrainingAndPrediction:
    """Stress tests simultaneous fitting and prediction across XGBoost, LightGBM, and CatBoost."""

    def test_native_estimators_instantiated_without_fallback_shims(self):
        """Verify that real native libraries are instantiated when packages are installed."""
        assert HAS_XGBOOST, "XGBoost should be installed and detected"
        assert HAS_LIGHTGBM, "LightGBM should be installed and detected"
        assert HAS_CATBOOST, "CatBoost should be installed and detected"

        ensemble = VotingEnsemble(n_estimators=10, max_depth=3)
        import xgboost
        import lightgbm
        import catboost

        assert isinstance(ensemble.xgb, xgboost.sklearn.XGBClassifier), f"Expected XGBClassifier, got {type(ensemble.xgb)}"
        assert isinstance(ensemble.lgb, lightgbm.sklearn.LGBMClassifier), f"Expected LGBMClassifier, got {type(ensemble.lgb)}"
        assert isinstance(ensemble.cb, catboost.core.CatBoostClassifier), f"Expected CatBoostClassifier, got {type(ensemble.cb)}"

    def test_simultaneous_fit_on_synthetic_66_feature_dataset(self):
        """Test simultaneous training on 66 features (Kalshi feature vector shape)."""
        n_samples = 300
        n_features = 66
        X, y = make_classification(
            n_samples=n_samples,
            n_features=n_features,
            n_informative=25,
            n_classes=2,
            random_state=42
        )

        ensemble = VotingEnsemble(n_estimators=15, max_depth=3, learning_rate=0.08)
        ensemble.fit(X, y)

        assert ensemble.is_trained is True

        # Test predict_proba outputs
        proba = ensemble.predict_proba(X)
        assert proba.shape == (n_samples, 2)
        # Bounded in [0, 1]
        assert np.all(proba >= 0.0) and np.all(proba <= 1.0)
        # Rows sum to 1.0
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)

        # Verify underlying individual models all made predictions
        p_xgb = ensemble.xgb.predict_proba(X)[:, 1]
        p_lgb = ensemble.lgb.predict_proba(X)[:, 1]
        p_cb = ensemble.cb.predict_proba(X)[:, 1]
        assert len(p_xgb) == n_samples
        assert len(p_lgb) == n_samples
        assert len(p_cb) == n_samples

        # Verify weighted soft-voting average is exact
        expected_p_ens = (p_xgb + p_lgb + p_cb) / 3.0
        assert np.allclose(proba[:, 1], expected_p_ens, atol=1e-5)

    def test_training_edge_cases_nan_inf_imbalance_and_degeneration(self):
        """Adversarial stress testing of fit() against corrupt inputs."""
        ensemble = VotingEnsemble(n_estimators=10)

        # Degenerate: single class (all 1s)
        X_single = np.random.randn(50, 10)
        y_single = np.ones(50, dtype=int)
        ensemble.fit(X_single, y_single)
        # Should exit gracefully without training
        assert ensemble.is_trained is False

        # Degenerate: fewer than 10 samples
        X_tiny = np.random.randn(8, 10)
        y_tiny = np.array([0, 1, 0, 1, 0, 1, 0, 1])
        ensemble.fit(X_tiny, y_tiny)
        assert ensemble.is_trained is False

        # Corrupt: NaNs and Infs present in training data
        X_corrupt, y_corrupt = make_classification(n_samples=50, n_features=10, random_state=7)
        X_corrupt[0, 0] = np.nan
        X_corrupt[1, 1] = np.inf
        X_corrupt[2, 2] = -np.inf
        ensemble.fit(X_corrupt, y_corrupt)
        assert ensemble.is_trained is True

        # Inference on NaN/Inf inputs
        X_test_corrupt = np.array([[np.nan] * 10, [np.inf] * 10])
        p_out = ensemble.predict_proba(X_test_corrupt)
        assert p_out.shape == (2, 2)
        assert not np.isnan(p_out).any()


# =====================================================================
# 2. CONSENSUS CALCULATION UNDER BOUNDARY CONDITIONS
# =====================================================================

class TestConsensusBoundaryConditions:
    """Stress tests consensus calculation across unanimous, 2/3, 1/3, neutral, and spread conditions."""

    class MockModel:
        def __init__(self, prob):
            self.prob = prob
        def predict_proba(self, X):
            n = len(X)
            return np.array([[1.0 - self.prob, self.prob]] * n)

    def test_unanimous_agreement_bullish_and_bearish(self):
        """Verify unanimous 3/3 agreement produces agreement_ratio=1.0 and is_unanimous=True."""
        ensemble = VotingEnsemble(n_estimators=10)
        dummy_X = np.zeros((1, 10))

        # 1. Unanimous Bullish (all > 0.50)
        ensemble.xgb = self.MockModel(0.85)
        ensemble.lgb = self.MockModel(0.78)
        ensemble.cb = self.MockModel(0.80)
        ensemble.is_trained = True

        res_bull = ensemble.predict_consensus(dummy_X)
        assert res_bull["is_unanimous"] is True
        assert res_bull["agreement_ratio"] == 1.0
        assert res_bull["agreement_count"] == 3
        assert res_bull["consensus_direction"] == "YES"
        assert res_bull["ensemble_prob"] == pytest.approx((0.85 + 0.78 + 0.80) / 3.0, abs=1e-4)

        # 2. Unanimous Bearish (all < 0.50)
        ensemble.xgb = self.MockModel(0.15)
        ensemble.lgb = self.MockModel(0.22)
        ensemble.cb = self.MockModel(0.18)

        res_bear = ensemble.predict_consensus(dummy_X)
        assert res_bear["is_unanimous"] is True
        assert res_bear["agreement_ratio"] == 1.0
        assert res_bear["agreement_count"] == 3
        assert res_bear["consensus_direction"] == "NO"

    def test_majority_2_3_split(self):
        """Verify 2/3 split produces agreement_ratio=0.67, is_unanimous=False."""
        ensemble = VotingEnsemble(n_estimators=10)
        dummy_X = np.zeros((1, 10))

        # 2 Bullish, 1 Bearish
        ensemble.xgb = self.MockModel(0.72)
        ensemble.lgb = self.MockModel(0.65)
        ensemble.cb = self.MockModel(0.35)  # dissenter
        ensemble.is_trained = True

        res = ensemble.predict_consensus(dummy_X)
        assert res["is_unanimous"] is False
        assert pytest.approx(res["agreement_ratio"], abs=0.01) == 0.67
        assert res["agreement_count"] == 2
        assert res["consensus_direction"] == "YES"

        # 2 Bearish, 1 Bullish
        ensemble.xgb = self.MockModel(0.25)
        ensemble.lgb = self.MockModel(0.30)
        ensemble.cb = self.MockModel(0.70)  # dissenter

        res_bear = ensemble.predict_consensus(dummy_X)
        assert res_bear["is_unanimous"] is False
        assert pytest.approx(res_bear["agreement_ratio"], abs=0.01) == 0.67
        assert res_bear["agreement_count"] == 2
        assert res_bear["consensus_direction"] == "NO"

    def test_sub_majority_and_neutral_split(self):
        """Verify 1/3 split or neutral models return agreement_ratio <= 0.33, consensus_direction='NEUTRAL'."""
        ensemble = VotingEnsemble(n_estimators=10)
        dummy_X = np.zeros((1, 10))

        # 1 Bullish, 1 Bearish, 1 exactly Neutral (0.50)
        ensemble.xgb = self.MockModel(0.65)
        ensemble.lgb = self.MockModel(0.35)
        ensemble.cb = self.MockModel(0.50)
        ensemble.is_trained = True

        res = ensemble.predict_consensus(dummy_X)
        assert res["is_unanimous"] is False
        assert res["agreement_ratio"] <= 0.34
        assert res["agreement_count"] == 1
        assert res["consensus_direction"] == "NEUTRAL"

        # All 3 exactly Neutral (0.50)
        ensemble.xgb = self.MockModel(0.50)
        ensemble.lgb = self.MockModel(0.50)
        ensemble.cb = self.MockModel(0.50)

        res_zero = ensemble.predict_consensus(dummy_X)
        assert res_zero["is_unanimous"] is False
        assert res_zero["agreement_ratio"] == 0.0
        assert res_zero["consensus_direction"] == "NEUTRAL"

    def test_dispersion_spread_and_variance(self):
        """Test dispersion metrics under tight spread vs wide spread."""
        ensemble = VotingEnsemble(n_estimators=10)
        dummy_X = np.zeros((1, 10))

        # Tight spread: [0.70, 0.71, 0.72]
        ensemble.xgb = self.MockModel(0.70)
        ensemble.lgb = self.MockModel(0.71)
        ensemble.cb = self.MockModel(0.72)
        ensemble.is_trained = True

        res_tight = ensemble.predict_consensus(dummy_X)
        assert pytest.approx(res_tight["spread"], abs=1e-4) == 0.02
        expected_var = float(np.var([0.70, 0.71, 0.72]))
        assert pytest.approx(res_tight["variance"], abs=1e-5) == round(expected_var, 6)

        # Wide spread: [0.51, 0.99, 0.52]
        ensemble.xgb = self.MockModel(0.51)
        ensemble.lgb = self.MockModel(0.99)
        ensemble.cb = self.MockModel(0.52)

        res_wide = ensemble.predict_consensus(dummy_X)
        assert pytest.approx(res_wide["spread"], abs=1e-4) == 0.48
        expected_var_wide = float(np.var([0.51, 0.99, 0.52]))
        assert pytest.approx(res_wide["variance"], abs=1e-5) == round(expected_var_wide, 6)


# =====================================================================
# 3. KELLY FORMULA CORRECTNESS ACROSS PROBABILITY / ASK GRIDS
# =====================================================================

class TestKellyFormulaGridVerification:
    """Stress tests the closed-form binary Kelly formula f* = (p - C) / (1 - C) across dense grids."""

    def test_dense_prob_and_ask_grid_no_crashes_and_correct_math(self):
        """Evaluate a 50x50 grid across p in [0.01, 0.99] and ask in [0.01, 0.99]."""
        probs = np.linspace(0.01, 0.99, 50)
        asks = np.linspace(0.01, 0.99, 50)
        bankroll = 10000.0

        for p in probs:
            for ask in asks:
                res = calculate_binary_kelly_position(
                    win_prob=float(p),
                    ask_price=float(ask),
                    available_capital=bankroll,
                    max_position_cap=bankroll
                )

                assert isinstance(res, dict)
                assert "contracts" in res
                contracts = res["contracts"]
                assert contracts >= 0

                # Ask bounds guardrails
                if ask <= 0.01 or ask >= 0.99 or p <= 0.0 or p >= 1.0:
                    assert contracts == 0
                    assert res["reason"] == "INVALID_PRICE_OR_PROB"
                    continue

                eff_entry = min(0.98, ask + 0.04)
                fee = math.ceil(0.07 * eff_entry * (1.0 - eff_entry) * 100.0) / 100.0
                C = eff_entry + fee
                ev = (p * (1.0 - C)) - ((1.0 - p) * C)

                if ev < 0.01 or C >= 1.0 or p <= C:
                    # Must be zero contracts
                    assert contracts == 0, f"Expected 0 contracts for p={p:.2f}, ask={ask:.2f}, ev={ev:.4f}"
                else:
                    # Expected positive f*
                    expected_f_star = (p - C) / (1.0 - C)
                    assert res["f_star"] > 0
                    assert pytest.approx(res["f_star"], abs=0.001) == round(expected_f_star, 4)
                    assert res["allocated_dollars"] > 0
                    assert contracts >= 1

    def test_kelly_monotonicity_properties(self):
        """Verify theoretical monotonicity: f* increases with p, decreases with ask."""
        bankroll = 10000.0
        ask = 0.50

        # Monotonically increasing in p
        p_values = [0.65, 0.70, 0.75, 0.80, 0.85]
        f_stars = []
        for p in p_values:
            res = calculate_binary_kelly_position(win_prob=p, ask_price=ask, available_capital=bankroll, max_position_cap=bankroll)
            f_stars.append(res["f_star"])

        for i in range(len(f_stars) - 1):
            assert f_stars[i] < f_stars[i + 1], f"f* must strictly increase with p: {f_stars}"

        # Monotonically decreasing in ask price for fixed p
        fixed_p = 0.80
        ask_values = [0.30, 0.40, 0.50, 0.60, 0.70]
        f_stars_ask = []
        for a in ask_values:
            res = calculate_binary_kelly_position(win_prob=fixed_p, ask_price=a, available_capital=bankroll, max_position_cap=bankroll)
            f_stars_ask.append(res["f_star"])

        for i in range(len(f_stars_ask) - 1):
            assert f_stars_ask[i] > f_stars_ask[i + 1], f"f* must strictly decrease with ask price: {f_stars_ask}"


# =====================================================================
# 4. 2.0X CONSENSUS AMPLIFICATION VERIFICATION
# =====================================================================

class TestConsensusAmplification2x:
    """Verify that unanimous 3/3 consensus strictly doubles allocation compared to 2/3 majority."""

    def test_unanimous_doubles_majority_allocation_below_bankroll_cap(self):
        """
        When f_star * lambda < 0.15 (uncapped), lambda=0.50 produces strictly
        2.0x the allocated budget compared to lambda=0.25.
        """
        bankroll = 10000.0
        # Choose trade parameters where f* is around 0.20
        # p=0.65, ask=0.50 => eff_entry=0.54, fee=0.02, C=0.56
        # f* = (0.65 - 0.56) / (1.0 - 0.56) = 0.09 / 0.44 = 0.2045
        # Majority: f_allocated = 0.2045 * 0.25 = 0.0511 (< 0.15)
        # Unanimous: f_allocated = 0.2045 * 0.50 = 0.1023 (< 0.15)
        res_maj = calculate_binary_kelly_position(
            win_prob=0.65,
            ask_price=0.50,
            available_capital=bankroll,
            max_position_cap=bankroll,
            is_unanimous=False,
            agreement_ratio=0.67
        )

        res_unan = calculate_binary_kelly_position(
            win_prob=0.65,
            ask_price=0.50,
            available_capital=bankroll,
            max_position_cap=bankroll,
            is_unanimous=True,
            agreement_ratio=1.0
        )

        assert res_maj["contracts"] > 0
        assert res_unan["contracts"] > 0

        assert res_maj["kelly_fraction"] == 0.25
        assert res_unan["kelly_fraction"] == 0.50

        # Exact 2.0x budget ratio
        budget_ratio = res_unan["allocated_dollars"] / res_maj["allocated_dollars"]
        assert pytest.approx(budget_ratio, abs=0.001) == 2.0, f"Expected exactly 2.0x allocation, got {budget_ratio}"

        # Contracts ratio approximately 2.0x (discrete integer units)
        contracts_ratio = res_unan["contracts"] / res_maj["contracts"]
        assert pytest.approx(contracts_ratio, abs=0.02) == 2.0, f"Expected ~2.0x contracts, got {contracts_ratio}"

    def test_low_consensus_zero_allocation(self):
        """When consensus is below majority threshold (e.g. agreement_ratio=0.33), allocation must be zero."""
        res_low = calculate_binary_kelly_position(
            win_prob=0.75,
            ask_price=0.50,
            available_capital=10000.0,
            max_position_cap=10000.0,
            agreement_ratio=0.33
        )
        assert res_low["contracts"] == 0
        assert res_low["allocated_dollars"] == 0.0
        assert res_low["reason"] == "LOW_CONSENSUS"


# =====================================================================
# 5. 15% BANKROLL CAP ENFORCEMENT
# =====================================================================

class TestBankrollCapEnforcement:
    """Stress tests single-trade bankroll cap across large bankrolls and massive theoretical edge."""

    @pytest.mark.parametrize("bankroll", [1000.0, 10000.0, 100000.0, 1000000.0, 10000000.0])
    def test_massive_edge_cannot_exceed_15_percent_cap(self, bankroll):
        """Even with p=0.98 and unanimous 0.50 multiplier, allocation must not exceed 15%."""
        res = calculate_binary_kelly_position(
            win_prob=0.98,
            ask_price=0.30,
            available_capital=bankroll,
            max_position_cap=bankroll,
            is_unanimous=True,
            agreement_ratio=1.0
        )

        max_allowed_dollars = bankroll * 0.15
        assert res["f_allocated"] <= 0.1500
        assert res["allocated_dollars"] <= max_allowed_dollars + 0.01, (
            f"Allocated ${res['allocated_dollars']} exceeds 15% limit (${max_allowed_dollars}) on bankroll ${bankroll}"
        )

        unit_cost = res["unit_cost"]
        total_contract_cost = res["contracts"] * unit_cost
        assert total_contract_cost <= max_allowed_dollars + unit_cost

    def test_custom_max_position_cap_respected(self):
        """If user sets max_position_cap lower than 15%, max_position_cap is enforced."""
        bankroll = 10000.0
        res = calculate_binary_kelly_position(
            win_prob=0.85,
            ask_price=0.40,
            available_capital=bankroll,
            max_position_cap=250.0,  # 2.5% of bankroll
            is_unanimous=True
        )
        assert res["allocated_dollars"] <= 250.0 + 0.01

    def test_zero_and_negative_bankroll_handled_safely(self):
        """Available capital <= 0 returns 0 contracts without throwing exceptions."""
        res_zero = calculate_binary_kelly_position(win_prob=0.80, ask_price=0.50, available_capital=0.0, max_position_cap=100.0)
        assert res_zero["contracts"] == 0
        assert res_zero["allocated_dollars"] == 0.0

        res_neg = calculate_binary_kelly_position(win_prob=0.80, ask_price=0.50, available_capital=-500.0, max_position_cap=100.0)
        assert res_neg["contracts"] == 0


# =====================================================================
# 6. NEGATIVE EV GATING
# =====================================================================

class TestNegativeEVGating:
    """Stress tests negative and sub-threshold EV rejection."""

    def test_fair_coin_flip_at_market_ask_is_negative_ev_and_gated(self):
        """A 50% probability at $0.50 ask yields negative EV after taker fee and slippage."""
        res = calculate_binary_kelly_position(win_prob=0.50, ask_price=0.50, available_capital=5000.0, max_position_cap=1000.0)
        assert res["contracts"] == 0
        assert res["ev"] < 0.0
        assert res["reason"] == "NEGATIVE_OR_NEGLIGIBLE_EV"

    def test_marginal_ev_below_one_cent_gated(self):
        """EV in (0.00, 0.0099) must be gated (< +$0.0100 min threshold)."""
        # Let's find p that gives EV between 0.0001 and 0.0099
        # ask=0.50, eff_entry=0.54, fee=0.02, C=0.56
        # ev = p * 0.44 - (1-p) * 0.56 = p - 0.56
        # If p = 0.565: ev = 0.565 - 0.56 = 0.005 ($0.005/contract < $0.0100)
        res = calculate_binary_kelly_position(win_prob=0.565, ask_price=0.50, available_capital=5000.0, max_position_cap=1000.0)
        assert res["contracts"] == 0
        assert res["ev"] < 0.01
        assert res["reason"] == "NEGATIVE_OR_NEGLIGIBLE_EV"

    def test_strongly_negative_edge_gated(self):
        """p < C results in zero allocation."""
        res = calculate_binary_kelly_position(win_prob=0.30, ask_price=0.60, available_capital=5000.0, max_position_cap=1000.0)
        assert res["contracts"] == 0
        assert res["ev"] < 0.0


# =====================================================================
# 7. INTERFACE CONTRACT & ARGUMENT ROBUSTNESS AUDIT
# =====================================================================

class TestInterfaceContractAndKeywordArgumentSafety:
    """Audits interface contracts across fees.py and ml_ensemble.py."""

    def test_fees_calculate_kelly_wager_keyword_p_win(self):
        """fees.py calculate_kelly_wager properly accepts p_win keyword."""
        res = fees_calculate_kelly_wager(p_win=0.70, ask_price=0.50, bankroll=1000.0, is_unanimous=True)
        assert res["contracts"] > 0
        assert res["ev"] > 0.01

    def test_ensemble_calculate_kelly_wager_positional_vs_keyword_p_win(self):
        """
        FORENSIC AUDIT:
        Tests whether VotingEnsemble.calculate_kelly_wager accepts p_win as keyword.
        In backend/btc/ml_ensemble.py, the parameter is declared as p_win_or_X=None.
        If called as calculate_kelly_wager(p_win=0.70), p_win_or_X defaults to None,
        and line 608 sets p_win = 0.50, collapsing the calculation!
        """
        ens = VotingEnsemble(n_estimators=10)

        # Positional call works
        res_pos = ens.calculate_kelly_wager(0.70, ask_price=0.50, bankroll=1000.0)
        assert res_pos["contracts"] > 0
        assert res_pos["ev"] > 0.01

        # Check keyword call
        res_kw = ens.calculate_kelly_wager(p_win=0.70, ask_price=0.50, bankroll=1000.0)
        # Record finding: If this fails or returns contracts=0 with p_win reset to 0.50,
        # we have empirically isolated the keyword signature bug!
        if res_kw["contracts"] == 0 and res_kw["ev"] < 0.0:
            pytest.fail(
                "DEFECT FOUND in VotingEnsemble.calculate_kelly_wager: "
                "Passing 'p_win=0.70' as keyword argument is ignored because parameter is named 'p_win_or_X'. "
                "The method silently defaults to p_win=0.50 and blocks the order with NEGATIVE_OR_NEGLIGIBLE_EV!"
            )
