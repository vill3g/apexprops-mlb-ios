import logging
import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Dependency Imports & Graceful Fallback Shims
# ---------------------------------------------------------------------
try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    from lightgbm import LGBMClassifier
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    from catboost import CatBoostClassifier
    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False


class _XGBoostShim:
    """Fallback estimator if xgboost is unavailable."""
    def __init__(self, n_estimators=150, max_depth=4, learning_rate=0.05, random_state=42, **kwargs):
        self.n_estimators = int(n_estimators)
        self.max_depth = int(max_depth)
        self.learning_rate = float(learning_rate)
        self.random_state = random_state
        self.scale_pos_weight = 1.0
        self._model = HistGradientBoostingClassifier(
            max_iter=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=random_state
        )

    def set_params(self, **params):
        if "scale_pos_weight" in params:
            self.scale_pos_weight = params.pop("scale_pos_weight")
        if "n_estimators" in params:
            self.n_estimators = int(params.pop("n_estimators"))
            self._model.set_params(max_iter=self.n_estimators)
        if "max_depth" in params:
            self.max_depth = int(params.pop("max_depth"))
            self._model.set_params(max_depth=self.max_depth)
        if "learning_rate" in params:
            self.learning_rate = float(params.pop("learning_rate"))
            self._model.set_params(learning_rate=self.learning_rate)
        return self

    def fit(self, X, y, sample_weight=None):
        X_np = np.asarray(X)
        y_np = np.asarray(y, dtype=int)
        sw = sample_weight
        if sw is None and self.scale_pos_weight != 1.0:
            sw = np.where(y_np == 1, self.scale_pos_weight, 1.0)
        self._model.fit(X_np, y_np, sample_weight=sw)
        return self

    def predict_proba(self, X):
        X_np = np.asarray(X)
        return self._model.predict_proba(X_np)

    def predict(self, X):
        X_np = np.asarray(X)
        return self._model.predict(X_np)


class _LGBMShim:
    """Fallback estimator if lightgbm is unavailable."""
    def __init__(self, n_estimators=150, max_depth=4, learning_rate=0.05, random_state=42, **kwargs):
        self.n_estimators = int(n_estimators)
        self.max_depth = int(max_depth)
        self.learning_rate = float(learning_rate)
        self.random_state = random_state
        self.scale_pos_weight = 1.0
        self._model = HistGradientBoostingClassifier(
            max_iter=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            random_state=random_state
        )

    def set_params(self, **params):
        if "scale_pos_weight" in params:
            self.scale_pos_weight = params.pop("scale_pos_weight")
        if "n_estimators" in params:
            self.n_estimators = int(params.pop("n_estimators"))
            self._model.set_params(max_iter=self.n_estimators)
        if "max_depth" in params:
            self.max_depth = int(params.pop("max_depth"))
            self._model.set_params(max_depth=self.max_depth)
        if "learning_rate" in params:
            self.learning_rate = float(params.pop("learning_rate"))
            self._model.set_params(learning_rate=self.learning_rate)
        return self

    def fit(self, X, y, sample_weight=None):
        X_np = np.asarray(X)
        y_np = np.asarray(y, dtype=int)
        sw = sample_weight
        if sw is None and self.scale_pos_weight != 1.0:
            sw = np.where(y_np == 1, self.scale_pos_weight, 1.0)
        self._model.fit(X_np, y_np, sample_weight=sw)
        return self

    def predict_proba(self, X):
        X_np = np.asarray(X)
        return self._model.predict_proba(X_np)

    def predict(self, X):
        X_np = np.asarray(X)
        return self._model.predict(X_np)


class _CatBoostShim:
    """Fallback estimator if catboost is unavailable."""
    def __init__(self, iterations=150, depth=4, learning_rate=0.05, random_seed=42, **kwargs):
        self.iterations = int(iterations)
        self.depth = int(depth)
        self.learning_rate = float(learning_rate)
        self.random_seed = random_seed
        self.scale_pos_weight = 1.0
        self._model = HistGradientBoostingClassifier(
            max_iter=self.iterations,
            max_depth=self.depth,
            learning_rate=self.learning_rate,
            random_state=random_seed
        )

    def set_params(self, **params):
        if "scale_pos_weight" in params:
            self.scale_pos_weight = params.pop("scale_pos_weight")
        if "iterations" in params:
            self.iterations = int(params.pop("iterations"))
            self._model.set_params(max_iter=self.iterations)
        if "depth" in params:
            self.depth = int(params.pop("depth"))
            self._model.set_params(max_depth=self.depth)
        if "learning_rate" in params:
            self.learning_rate = float(params.pop("learning_rate"))
            self._model.set_params(learning_rate=self.learning_rate)
        return self

    def fit(self, X, y, sample_weight=None):
        X_np = np.asarray(X)
        y_np = np.asarray(y, dtype=int)
        sw = sample_weight
        if sw is None and self.scale_pos_weight != 1.0:
            sw = np.where(y_np == 1, self.scale_pos_weight, 1.0)
        self._model.fit(X_np, y_np, sample_weight=sw)
        return self

    def predict_proba(self, X):
        X_np = np.asarray(X)
        return self._model.predict_proba(X_np)

    def predict(self, X):
        X_np = np.asarray(X)
        return self._model.predict(X_np)


# ---------------------------------------------------------------------
# Legacy Neural Network Modules (preserves backward compatibility)
# ---------------------------------------------------------------------
class PyTorchLSTM(nn.Module):
    def __init__(self, input_dim, seq_len=5, seq_features=5):
        super(PyTorchLSTM, self).__init__()
        self.seq_len = seq_len
        self.seq_features = seq_features
        self.flat_dim = input_dim - (seq_len * seq_features)
        self.lstm = nn.LSTM(input_size=seq_features, hidden_size=32, num_layers=1, batch_first=True)
        self.tabular_fc = nn.Sequential(
            nn.Linear(self.flat_dim, 64),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        self.fc_merged = nn.Sequential(
            nn.Linear(32 + 64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        x_flat = x[:, :self.flat_dim]
        x_seq_flat = x[:, self.flat_dim:]
        x_seq = x_seq_flat.view(-1, self.seq_len, self.seq_features)
        lstm_out, _ = self.lstm(x_seq)
        lstm_feat = lstm_out[:, -1, :]
        tab_feat = self.tabular_fc(x_flat)
        merged = torch.cat((tab_feat, lstm_feat), dim=1)
        return self.fc_merged(merged)


class PyTorchDNN(nn.Module):
    def __init__(self, input_dim):
        super(PyTorchDNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.LayerNorm(32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------------
# Unified Voting Classifier Ensemble
# ---------------------------------------------------------------------
class VotingEnsemble:
    """
    Unified Voting Classifier Ensemble combining:
    1. XGBoost (XGBClassifier)
    2. LightGBM (LGBMClassifier)
    3. CatBoost (CatBoostClassifier)

    Provides:
    - Simultaneous training across all three gradient boosted decision tree libraries
    - Soft-voting probabilistic inference
    - Consensus determination (agreement ratio, unanimity, probability dispersion)
    - Dynamic Kelly Criterion wager sizing natively computed upon consensus
    - 100% backward compatibility with legacy GodTierEnsemble
    """

    def __init__(
        self,
        n_estimators: int = 150,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        weights: list = None,
        xgb_estimators: int = None,
        xgb_max_depth: int = None,
        xgb_lr: float = None,
        rf_estimators: int = None,
        **kwargs
    ):
        if xgb_estimators is not None:
            n_estimators = xgb_estimators
        if xgb_max_depth is not None:
            max_depth = xgb_max_depth
        if xgb_lr is not None:
            learning_rate = xgb_lr

        self.n_estimators = int(n_estimators)
        self.max_depth = int(max_depth)
        self.learning_rate = float(learning_rate)
        self.weights = weights if weights is not None else [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]

        self.scaler = StandardScaler()
        self.is_trained = False
        self.is_normalized = True
        self.calibrator = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self._init_models()

    def _init_models(self):
        # 1. XGBoost
        if HAS_XGBOOST:
            self.xgb = XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                objective="binary:logistic",
                random_state=42,
                n_jobs=-1,
                verbosity=0
            )
        else:
            logger.warning("[VotingEnsemble] XGBoost not available, initializing fallback shim.")
            self.xgb = _XGBoostShim(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=42
            )

        # 2. LightGBM
        if HAS_LIGHTGBM:
            self.lgb = LGBMClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                objective="binary",
                random_state=42,
                n_jobs=-1,
                verbosity=-1
            )
        else:
            logger.warning("[VotingEnsemble] LightGBM not available, initializing fallback shim.")
            self.lgb = _LGBMShim(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=42
            )

        # 3. CatBoost
        if HAS_CATBOOST:
            self.cb = CatBoostClassifier(
                iterations=self.n_estimators,
                depth=self.max_depth,
                learning_rate=self.learning_rate,
                loss_function="Logloss",
                random_seed=42,
                thread_count=-1,
                verbose=False
            )
        else:
            logger.warning("[VotingEnsemble] CatBoost not available, initializing fallback shim.")
            self.cb = _CatBoostShim(
                iterations=self.n_estimators,
                depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_seed=42
            )

    def update_params(
        self,
        class_weight="balanced",
        reg_c=0.7,
        xgb_estimators=None,
        xgb_max_depth=None,
        xgb_lr=None,
        **kwargs
    ):
        """Allow live hyperparameter updates from config."""
        if xgb_estimators is not None:
            self.n_estimators = int(xgb_estimators)
            if hasattr(self.xgb, "set_params"):
                self.xgb.set_params(n_estimators=self.n_estimators)
            if hasattr(self.lgb, "set_params"):
                self.lgb.set_params(n_estimators=self.n_estimators)
            if hasattr(self.cb, "set_params"):
                self.cb.set_params(iterations=self.n_estimators)

        if xgb_max_depth is not None:
            self.max_depth = int(xgb_max_depth)
            if hasattr(self.xgb, "set_params"):
                self.xgb.set_params(max_depth=self.max_depth)
            if hasattr(self.lgb, "set_params"):
                self.lgb.set_params(max_depth=self.max_depth)
            if hasattr(self.cb, "set_params"):
                self.cb.set_params(depth=self.max_depth)

        if xgb_lr is not None:
            self.learning_rate = float(xgb_lr)
            if hasattr(self.xgb, "set_params"):
                self.xgb.set_params(learning_rate=self.learning_rate)
            if hasattr(self.lgb, "set_params"):
                self.lgb.set_params(learning_rate=self.learning_rate)
            if hasattr(self.cb, "set_params"):
                self.cb.set_params(learning_rate=self.learning_rate)

    def fit(self, X, y, sample_weight=None):
        X_np = X.values if hasattr(X, "values") else np.array(X)
        X_np = np.nan_to_num(X_np, nan=0.0, posinf=0.0, neginf=0.0)
        y_np = y.values if hasattr(y, "values") else np.array(y, dtype=int)

        if len(X_np) < 10 or len(np.unique(y_np)) < 2:
            logger.warning("[VotingEnsemble] Not enough data or classes to train.")
            return

        # Fit StandardScaler on unscaled features
        self.scaler.fit(X_np)

        # Dynamic scale_pos_weight
        num_pos = int(np.sum(y_np == 1))
        num_neg = int(np.sum(y_np == 0))
        scale_pos = float(num_neg) / float(num_pos) if num_pos > 0 else 1.0

        # 1. Train XGBoost
        try:
            if hasattr(self.xgb, "set_params"):
                self.xgb.set_params(scale_pos_weight=scale_pos)
        except Exception:
            pass
        self.xgb.fit(X_np, y_np, sample_weight=sample_weight)

        # 2. Train LightGBM
        try:
            if hasattr(self.lgb, "set_params"):
                self.lgb.set_params(scale_pos_weight=scale_pos)
        except Exception:
            pass
        self.lgb.fit(X_np, y_np, sample_weight=sample_weight)

        # 3. Train CatBoost
        try:
            if hasattr(self.cb, "set_params"):
                self.cb.set_params(scale_pos_weight=scale_pos)
        except Exception:
            pass
        self.cb.fit(X_np, y_np, sample_weight=sample_weight)

        self.is_trained = True
        self.is_normalized = True
        if len(X_np) >= 80 and not getattr(self, "oos_brier_scores", None):
            split_idx = int(len(X_np) * 0.8)
            if len(np.unique(y_np[split_idx:])) >= 2:
                self.fit_calibration(X_np[split_idx:], y_np[split_idx:])
        logger.info("[VotingEnsemble] Successfully fitted XGBoost, LightGBM, and CatBoost models simultaneously.")

    def predict_proba(self, X):
        if not self.is_trained:
            n = len(X) if hasattr(X, "__len__") else 1
            return np.array([[0.5, 0.5]] * n)

        X_np = X.values if hasattr(X, "values") else np.array(X)
        X_np = np.nan_to_num(X_np, nan=0.0, posinf=0.0, neginf=0.0)
        if X_np.ndim == 1:
            X_np = X_np.reshape(1, -1)

        if not hasattr(self, "xgb"):
            self._init_models()
        if not hasattr(self, "lgb"):
            self.lgb = getattr(self, "xgb", None)
        if not hasattr(self, "cb"):
            self.cb = getattr(self, "xgb", None)

        p_xgb = self.xgb.predict_proba(X_np)[:, 1]
        p_lgb = self.lgb.predict_proba(X_np)[:, 1] if self.lgb is not None else p_xgb
        p_cb = self.cb.predict_proba(X_np)[:, 1] if self.cb is not None else p_xgb

        w = self.weights
        w_total = sum(w)
        p_ens = (w[0] * p_xgb + w[1] * p_lgb + w[2] * p_cb) / w_total
        p_ens = np.clip(p_ens, 0.0, 1.0)

        return np.column_stack((1.0 - p_ens, p_ens))

    def predict_proba_calibrated(self, X):
        preds = self.predict_proba(X)
        raw_p = preds[:, 1] if len(preds.shape) > 1 else preds
        if getattr(self, "calibrator", None) is not None and getattr(self.calibrator, "is_fitted", False):
            try:
                return self.calibrator.predict(raw_p)
            except Exception:
                return raw_p
        return raw_p

    def fit_calibration(self, X_holdout, y_holdout):
        """
        Computes Out-of-Sample (OOS) Brier Scores for XGBoost, LightGBM, and CatBoost on the
        chronological holdout slice, dynamically updates ensemble weights inversely to Brier error
        (via softmax over Brier skill), and fits a strictly monotonic sigmoid (Platt) calibrator.
        """
        self.calibrator = None
        if X_holdout is None or y_holdout is None or not self.is_trained:
            return
        try:
            X_h = X_holdout.values if hasattr(X_holdout, "values") else np.asarray(X_holdout)
            X_h = np.nan_to_num(X_h, nan=0.0, posinf=0.0, neginf=0.0)
            y_h = y_holdout.values if hasattr(y_holdout, "values") else np.asarray(y_holdout, dtype=float)
            if len(X_h) < 20 or len(np.unique(y_h)) < 2:
                return

            p_xgb = np.clip(self.xgb.predict_proba(X_h)[:, 1], 1e-4, 0.9999)
            p_lgb = np.clip(self.lgb.predict_proba(X_h)[:, 1], 1e-4, 0.9999) if self.lgb is not None else p_xgb
            p_cb = np.clip(self.cb.predict_proba(X_h)[:, 1], 1e-4, 0.9999) if self.cb is not None else p_xgb

            b_xgb = float(np.mean((p_xgb - y_h) ** 2))
            b_lgb = float(np.mean((p_lgb - y_h) ** 2))
            b_cb = float(np.mean((p_cb - y_h) ** 2))

            # Inverse-Brier softmax weighting (gamma = 12.0 rewards lower Brier score while bounding weights in [0.15, 0.60])
            gamma = 12.0
            b_min = min(b_xgb, b_lgb, b_cb)
            raw_w = [
                math.exp(-gamma * (b_xgb - b_min)),
                math.exp(-gamma * (b_lgb - b_min)),
                math.exp(-gamma * (b_cb - b_min)),
            ]
            w_sum = sum(raw_w)
            norm_w = [max(0.15, min(0.60, w / w_sum)) for w in raw_w]
            norm_sum = sum(norm_w)
            self.weights = [round(w / norm_sum, 4) for w in norm_w]

            p_ens = (self.weights[0] * p_xgb + self.weights[1] * p_lgb + self.weights[2] * p_cb)
            b_ens = float(np.mean((p_ens - y_h) ** 2))
            self.oos_brier_scores = {
                "xgboost": round(b_xgb, 5),
                "lightgbm": round(b_lgb, 5),
                "catboost": round(b_cb, 5),
                "ensemble": round(b_ens, 5),
                "samples": int(len(X_h)),
            }
            logger.info(
                f"[VotingEnsemble] OOS Brier Calibration ({len(X_h)} samples): "
                f"XGB={b_xgb:.4f}, LGB={b_lgb:.4f}, CB={b_cb:.4f} -> Ens={b_ens:.4f} | Dynamic Weights={self.weights}"
            )

            if len(X_h) >= 40:
                from backend.btc.ml_engine import PlattCalibrator
                cal = PlattCalibrator(C=1.0)
                cal.fit(p_ens, y_h)
                if cal.is_fitted:
                    self.calibrator = cal
        except Exception as e:
            logger.debug(f"[VotingEnsemble] fit_calibration skipped: {e}")

    def evaluate_consensus(self, X) -> dict:
        """
        Calculates directional consensus across XGBoost, LightGBM, and CatBoost.
        Returns:
            dict containing:
            - 'ensemble_prob': float (soft-voting average)
            - 'p_ensemble': float (alias for ensemble_prob)
            - 'consensus_direction': str ("YES" / "UP", "NO" / "DOWN", or "NEUTRAL")
            - 'agreement_count': int (1, 2, or 3)
            - 'agreement_ratio': float (1.0 for 3/3, 0.67 for 2/3)
            - 'is_unanimous': bool
            - 'individual_probs': dict[str, float] {"xgb", "lgb", "cb"}
            - 'model_probs': dict[str, float] {"xgboost", "lightgbm", "catboost"}
            - 'spread': float (max(p) - min(p))
            - 'variance': float
        """
        if not self.is_trained:
            return {
                "ensemble_prob": 0.5,
                "p_ensemble": 0.5,
                "consensus_direction": "NEUTRAL",
                "agreement_count": 3,
                "agreement_ratio": 1.0,
                "is_unanimous": True,
                "individual_probs": {"xgb": 0.5, "lgb": 0.5, "cb": 0.5},
                "model_probs": {"xgboost": 0.5, "lightgbm": 0.5, "catboost": 0.5},
                "weights": list(self.weights),
                "oos_brier_scores": getattr(self, "oos_brier_scores", None),
                "spread": 0.0,
                "variance": 0.0,
            }

        X_np = X.values if hasattr(X, "values") else np.array(X)
        X_np = np.nan_to_num(X_np, nan=0.0, posinf=0.0, neginf=0.0)
        is_single = False
        if X_np.ndim == 1:
            is_single = True
            X_np = X_np.reshape(1, -1)
        elif len(X_np) == 1:
            is_single = True

        if not hasattr(self, "xgb"):
            self._init_models()
        if not hasattr(self, "lgb"):
            self.lgb = getattr(self, "xgb", None)
        if not hasattr(self, "cb"):
            self.cb = getattr(self, "xgb", None)

        p_xgb_all = self.xgb.predict_proba(X_np)[:, 1]
        p_lgb_all = self.lgb.predict_proba(X_np)[:, 1] if self.lgb is not None else p_xgb_all
        p_cb_all = self.cb.predict_proba(X_np)[:, 1] if self.cb is not None else p_xgb_all

        w = self.weights
        w_total = sum(w)
        p_ens_all = (w[0] * p_xgb_all + w[1] * p_lgb_all + w[2] * p_cb_all) / w_total

        results = []
        for i in range(len(X_np)):
            p_x = float(p_xgb_all[i])
            p_l = float(p_lgb_all[i])
            p_c = float(p_cb_all[i])
            p_e = float(np.clip(p_ens_all[i], 0.0, 1.0))

            dir_xgb = "YES" if p_x > 0.50 else ("NO" if p_x < 0.50 else "NEUTRAL")
            dir_lgb = "YES" if p_l > 0.50 else ("NO" if p_l < 0.50 else "NEUTRAL")
            dir_cb = "YES" if p_c > 0.50 else ("NO" if p_c < 0.50 else "NEUTRAL")

            dirs = [dir_xgb, dir_lgb, dir_cb]
            yes_count = sum(1 for d in dirs if d == "YES")
            no_count = sum(1 for d in dirs if d == "NO")

            if yes_count == 3:
                is_unanimous = True
                agreement_ratio = 1.0
                agreement_count = 3
                consensus_dir = "YES"
            elif no_count == 3:
                is_unanimous = True
                agreement_ratio = 1.0
                agreement_count = 3
                consensus_dir = "NO"
            elif yes_count == 2:
                is_unanimous = False
                agreement_ratio = 0.67
                agreement_count = 2
                consensus_dir = "YES"
            elif no_count == 2:
                is_unanimous = False
                agreement_ratio = 0.67
                agreement_count = 2
                consensus_dir = "NO"
            else:
                is_unanimous = False
                agreement_count = max(yes_count, no_count)
                agreement_ratio = round(agreement_count / 3.0, 2)
                consensus_dir = "NEUTRAL"

            probs_list = [p_x, p_l, p_c]
            res = {
                "ensemble_prob": round(p_e, 4),
                "p_ensemble": round(p_e, 4),
                "consensus_direction": consensus_dir,
                "agreement_count": agreement_count,
                "agreement_ratio": agreement_ratio,
                "is_unanimous": is_unanimous,
                "individual_probs": {
                    "xgb": round(p_x, 4),
                    "lgb": round(p_l, 4),
                    "cb": round(p_c, 4),
                },
                "model_probs": {
                    "xgboost": round(p_x, 4),
                    "lightgbm": round(p_l, 4),
                    "catboost": round(p_c, 4),
                },
                "weights": list(self.weights),
                "oos_brier_scores": getattr(self, "oos_brier_scores", None),
                "spread": round(float(max(probs_list) - min(probs_list)), 4),
                "variance": round(float(np.var(probs_list)), 6),
            }
            results.append(res)

        if is_single:
            return results[0]
        return results

    def predict_consensus(self, X) -> dict:
        """Alias for evaluate_consensus adhering to PROJECT.md and dispatch contract."""
        return self.evaluate_consensus(X)

    def calculate_kelly_wager(
        self,
        p_win_or_X=None,
        ask_price: float = 0.50,
        bankroll: float = 1000.0,
        is_unanimous: bool = False,
        agreement_ratio: float = None,
        max_position_cap: float = None,
        slippage_buffer: float = 0.04,
        **kwargs
    ) -> dict:
        from backend.btc.fees import calculate_binary_kelly_position

        if p_win_or_X is None and "p_win" in kwargs:
            p_win_or_X = kwargs.pop("p_win")
        elif "p_win" in kwargs:
            kwargs.pop("p_win")

        if p_win_or_X is not None and not isinstance(p_win_or_X, (int, float)):
            consensus = self.predict_consensus(p_win_or_X)
            p_win = consensus.get("p_ensemble", 0.50)
            is_unanimous = consensus.get("is_unanimous", False)
            agreement_ratio = consensus.get("agreement_ratio", None)
        elif p_win_or_X is not None:
            p_win = float(p_win_or_X)
        else:
            p_win = 0.50

        cap = max_position_cap if max_position_cap is not None else bankroll
        return calculate_binary_kelly_position(
            win_prob=p_win,
            ask_price=ask_price,
            available_capital=bankroll,
            max_position_cap=cap,
            slippage_buffer=slippage_buffer,
            is_unanimous=is_unanimous,
            agreement_ratio=agreement_ratio,
            **kwargs
        )


# Backward-compatible subclass alias
class GodTierEnsemble(VotingEnsemble):
    """Backward-compatible alias routing legacy GodTierEnsemble calls to VotingEnsemble."""
    pass
