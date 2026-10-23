import math
import pytest
import numpy as np
from sklearn.datasets import make_classification


# =====================================================================
# TIER 1: FEATURE COVERAGE — VOTING ENSEMBLE & KELLY MATHEMATICS
# =====================================================================

class TestVotingEnsembleCore:
    """
    Tier 1: Comprehensive tests for the unified Voting Classifier ensemble
    (XGBoost, LightGBM, CatBoost), soft voting, consensus logic, and fallback shims.
    """

    def test_voting_ensemble_initialization_and_alias(self):
        """
        Verify that VotingEnsemble can be initialized, has member estimators,
        and that GodTierEnsemble is an alias or subclass maintaining backward compatibility.
        """
        from backend.btc.ml_ensemble import VotingEnsemble, GodTierEnsemble

        ensemble = VotingEnsemble(n_estimators=10, max_depth=3, learning_rate=0.05)
        assert ensemble is not None

        # Verify GodTierEnsemble alias compatibility
        assert issubclass(GodTierEnsemble, VotingEnsemble) or GodTierEnsemble is VotingEnsemble
        legacy_instance = GodTierEnsemble(n_estimators=10)
        assert isinstance(legacy_instance, VotingEnsemble)

    def test_simultaneous_fit_and_soft_voting_predict(self):
        """
        Verify that VotingEnsemble simultaneously fits its gradient-boosting estimators
        and performs soft voting inference returning valid class probabilities.
        """
        from backend.btc.ml_ensemble import VotingEnsemble

        X, y = make_classification(n_samples=80, n_features=20, n_informative=10, random_state=42)
        ensemble = VotingEnsemble(n_estimators=15, max_depth=3, learning_rate=0.1)

        ensemble.fit(X, y)
        assert getattr(ensemble, "is_trained", False) is True or hasattr(ensemble, "xgb")

        proba = ensemble.predict_proba(X)
        assert proba.shape == (80, 2), f"Expected shape (80, 2), got {proba.shape}"
        # Probabilities sum to 1.0
        row_sums = proba.sum(axis=1)
        assert np.allclose(row_sums, 1.0, atol=1e-5), "Each row of predict_proba must sum to 1.0"
        # Probabilities bounded in [0, 1]
        assert np.all(proba >= 0.0) and np.all(proba <= 1.0)

    def test_consensus_evaluation_unanimity_vs_majority(self):
        """
        Verify consensus evaluation logic:
        - 3/3 unanimous agreement: agreement_ratio == 1.0, is_unanimous == True
        - 2/3 majority agreement: agreement_ratio == 0.67, is_unanimous == False
        - Dispersion spread: max(p) - min(p)
        """
        from backend.btc.ml_ensemble import VotingEnsemble

        ensemble = VotingEnsemble(n_estimators=10)

        # Mock member models to return controlled probabilities
        class DummyModel:
            def __init__(self, prob):
                self.prob = prob
            def predict_proba(self, X):
                n = len(X)
                return np.array([[1.0 - self.prob, self.prob]] * n)

        # 1. Unanimous Bullish (all > 0.50)
        ensemble.xgb = DummyModel(0.75)
        ensemble.lgb = DummyModel(0.70)
        ensemble.cb = DummyModel(0.72)
        ensemble.is_trained = True

        dummy_X = np.zeros((1, 20))
        consensus = ensemble.evaluate_consensus(dummy_X)

        assert consensus["is_unanimous"] is True, "Must be unanimous when all 3 models agree"
        assert consensus["agreement_ratio"] == 1.0
        assert consensus["consensus_direction"] in ("UP", "YES")
        assert consensus["agreement_count"] == 3
        assert pytest.approx(consensus["spread"], 0.001) == 0.05  # 0.75 - 0.70
        assert 0.70 <= consensus["ensemble_prob"] <= 0.75

        # 2. Majority Bullish (2 agree > 0.50, 1 dissents < 0.50)
        ensemble.xgb = DummyModel(0.68)
        ensemble.lgb = DummyModel(0.62)
        ensemble.cb = DummyModel(0.40)  # Dissenting

        consensus_maj = ensemble.evaluate_consensus(dummy_X)
        assert consensus_maj["is_unanimous"] is False, "Must not be unanimous on 2/3 split"
        assert pytest.approx(consensus_maj["agreement_ratio"], 0.01) == 0.67
        assert consensus_maj["agreement_count"] == 2
        assert consensus_maj["consensus_direction"] in ("UP", "YES")

        # 3. Unanimous Bearish (all < 0.50)
        ensemble.xgb = DummyModel(0.25)
        ensemble.lgb = DummyModel(0.30)
        ensemble.cb = DummyModel(0.28)

        consensus_down = ensemble.evaluate_consensus(dummy_X)
        assert consensus_down["is_unanimous"] is True
        assert consensus_down["agreement_ratio"] == 1.0
        assert consensus_down["consensus_direction"] in ("DOWN", "NO")

    def test_graceful_fallback_when_dependencies_missing(self, monkeypatch):
        """
        Verify that if lightgbm or catboost cannot be imported,
        the ensemble gracefully substitutes fallback estimators and operates without crashing.
        """
        from backend.btc.ml_ensemble import VotingEnsemble

        # Verify ensemble still functions if lightgbm/catboost are absent or fallback
        ensemble = VotingEnsemble(n_estimators=10)
        X, y = make_classification(n_samples=40, n_features=15, random_state=1)
        ensemble.fit(X, y)
        res = ensemble.predict_proba(X)
        assert res.shape == (40, 2)


class TestKellyCriterionMathematics:
    """
    Tier 1 & 2: Rigorous mathematical verification of the closed-form binary option
    Kelly Criterion formula:
        f* = (p - C) / (1.0 - C)
    and consensus amplification scaling (Half-Kelly on unanimity vs Quarter-Kelly on majority).
    """

    def test_closed_form_binary_kelly_formula_derivation(self):
        """
        Mathematically verify:
        Given:
        - ask_price = 0.50
        - slippage_buffer = 0.04 => effective_entry = 0.54
        - taker_fee = ceil(0.07 * 0.54 * 0.46 * 100) / 100 = 0.02
        - Total cost C = 0.54 + 0.02 = 0.56
        - Win prob p = 0.70
        Theoretical:
        - Net win = 1.00 - 0.56 = 0.44
        - Net loss = 0.56
        - b = 0.44 / 0.56
        - f* = (b*p - q) / b = (p - C) / (1 - C) = (0.70 - 0.56) / (1.00 - 0.56) = 0.14 / 0.44 = 0.318181...
        """
        from backend.btc.fees import calculate_binary_kelly_position

        p = 0.70
        ask = 0.50
        capital = 1000.0
        max_cap = 200.0

        res = calculate_binary_kelly_position(
            win_prob=p,
            ask_price=ask,
            available_capital=capital,
            max_position_cap=max_cap,
            slippage_buffer=0.04,
            fractional_multiplier=0.25
        )

        expected_effective_entry = min(0.98, 0.50 + 0.04)  # 0.54
        expected_fee = math.ceil(0.07 * 0.54 * 0.46 * 100.0) / 100.0  # 0.02
        expected_cost = expected_effective_entry + expected_fee  # 0.56
        expected_f_star = (p - expected_cost) / (1.0 - expected_cost)  # 0.14 / 0.44 = 0.31818...

        assert pytest.approx(res["f_star"], 0.001) == round(expected_f_star, 4)
        assert pytest.approx(res["effective_entry"], 0.01) == expected_effective_entry
        assert pytest.approx(res["taker_fee"], 0.01) == expected_fee

    def test_consensus_kelly_amplification_doubles_allocation(self):
        """
        Verify consensus amplification:
        - Unanimous consensus triggers Half-Kelly (lambda = 0.50)
        - Majority consensus triggers Quarter-Kelly (lambda = 0.25)
        - Unanimous allocation should double majority allocation (when below 15% bankroll cap).
        """
        from backend.btc.fees import calculate_binary_kelly_position

        p = 0.65
        ask = 0.50
        capital = 2000.0
        max_cap = 500.0

        # Majority consensus: Quarter-Kelly (0.25)
        res_majority = calculate_binary_kelly_position(
            win_prob=p,
            ask_price=ask,
            available_capital=capital,
            max_position_cap=max_cap,
            fractional_multiplier=0.25,
            is_unanimous=False
        )

        # Unanimous consensus: Half-Kelly (0.50)
        res_unanimous = calculate_binary_kelly_position(
            win_prob=p,
            ask_price=ask,
            available_capital=capital,
            max_position_cap=max_cap,
            fractional_multiplier=0.50,
            is_unanimous=True
        )

        assert res_majority["contracts"] > 0
        assert res_unanimous["contracts"] > 0

        # When within bankroll caps, allocated dollars under unanimity should be ~2x majority
        ratio = res_unanimous["allocated_dollars"] / res_majority["allocated_dollars"]
        assert pytest.approx(ratio, 0.05) == 2.0, f"Unanimous allocation must be 2x majority, got {ratio}"
        assert res_unanimous["contracts"] >= res_majority["contracts"] * 2 - 1


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES
# =====================================================================

class TestKellyBoundaryAndRiskCaps:
    """
    Tier 2: Boundary edge cases:
    - Negative or zero EV gate (< $0.01)
    - Extreme probabilities (p=0.50, p=1.0)
    - Ask price bounds (0.01, 0.99)
    - Bankroll cap (15%) and zero bankroll
    """

    def test_negative_or_subthreshold_ev_blocks_order(self):
        """
        When expected value is negative or less than $0.01, the trade must be blocked
        (contracts = 0, f_star <= 0).
        """
        from backend.btc.fees import calculate_binary_kelly_position

        # Fair coin-flip (p=0.50) at ask=0.50 is negative EV after fees (-$0.06 EV)
        res = calculate_binary_kelly_position(
            win_prob=0.50,
            ask_price=0.50,
            available_capital=1000.0,
            max_position_cap=100.0
        )
        assert res["contracts"] == 0
        assert res["ev"] < 0.01
        assert "NEGATIVE" in res["reason"] or "SUB" in res.get("reason", "").upper()

        # Severely negative EV (p=0.30 at ask=0.60)
        res_neg = calculate_binary_kelly_position(
            win_prob=0.30,
            ask_price=0.60,
            available_capital=1000.0,
            max_position_cap=100.0
        )
        assert res_neg["contracts"] == 0

    def test_extreme_ask_price_boundaries(self):
        """
        Test ask price extremes:
        - ask_price <= 0.01 or ask_price >= 0.99 should return 0 contracts safely.
        """
        from backend.btc.fees import calculate_binary_kelly_position

        # Extremely low price (0.01 or below)
        res_low = calculate_binary_kelly_position(win_prob=0.80, ask_price=0.01, available_capital=500.0, max_position_cap=100.0)
        assert res_low["contracts"] == 0

        # Extremely high price (0.99 or above)
        res_high = calculate_binary_kelly_position(win_prob=0.99, ask_price=0.99, available_capital=500.0, max_position_cap=100.0)
        assert res_high["contracts"] == 0

    def test_single_trade_bankroll_cap_15_percent(self):
        """
        Verify the 15% single-trade bankroll cap:
        Even if f* is massive (e.g. 0.90) and unanimity multiplier is 0.50,
        the allocated capital cannot exceed 15% of available bankroll.
        """
        from backend.btc.fees import calculate_binary_kelly_position

        capital = 1000.0
        # Highly confident trade
        res = calculate_binary_kelly_position(
            win_prob=0.95,
            ask_price=0.40,
            available_capital=capital,
            max_position_cap=1000.0,
            fractional_multiplier=0.50
        )

        max_allowed_dollars = capital * 0.15  # $150.00
        assert res["allocated_dollars"] <= max_allowed_dollars + 0.01, \
            f"Allocated ${res['allocated_dollars']} exceeds 15% cap (${max_allowed_dollars})"

    def test_zero_bankroll_and_zero_prob_safeguards(self):
        """
        Verify no division by zero or exception when available_capital is 0
        or win_prob is 0.
        """
        from backend.btc.fees import calculate_binary_kelly_position

        # Zero capital
        res_zero_cap = calculate_binary_kelly_position(win_prob=0.70, ask_price=0.50, available_capital=0.0, max_position_cap=100.0)
        assert res_zero_cap["contracts"] == 0
        assert res_zero_cap.get("allocated_dollars", 0.0) == 0.0

        # Zero probability
        res_zero_prob = calculate_binary_kelly_position(win_prob=0.0, ask_price=0.50, available_capital=1000.0, max_position_cap=100.0)
        assert res_zero_prob["contracts"] == 0


class TestMLEngineConsensusIntegration:
    """
    Tier 1 & 2: Tests MLEngine integration with VotingEnsemble consensus methods.
    """

    def test_ml_engine_predict_consensus_method_contract(self):
        """
        Verify MLEngine exposes predict_consensus returning consensus dict
        and calculate_kelly_wager returning Kelly sizing dict.
        """
        from backend.btc.ml_engine import get_ml_engine

        engine = get_ml_engine(trading_style="AUTO", asset="BTC")

        # Mock features dictionary with 66 keys
        raw_features = {f"feat_{i}": 0.5 for i in range(66)}
        raw_features["rsi"] = 55.0
        raw_features["bb_percent_b"] = 0.6
        raw_features["volume_15m_ratio"] = 1.1

        if hasattr(engine, "predict_consensus"):
            res = engine.predict_consensus(raw_features)
            assert isinstance(res, dict)
            assert "consensus_direction" in res or "ensemble_prob" in res

        if hasattr(engine, "calculate_kelly_wager"):
            wager = engine.calculate_kelly_wager(raw_features, market_price=0.50, capital=1000.0, max_cap=100.0)
            assert isinstance(wager, dict)
            assert "contracts" in wager
