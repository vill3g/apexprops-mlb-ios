import json
import os
import numpy as np
import logging

logger = logging.getLogger(__name__)

class NumpyLogisticRegression:
    def __init__(self, learning_rate=0.01, num_iterations=1000):
        self.learning_rate = learning_rate
        self.num_iterations = num_iterations
        self.weights = None
        self.bias = None
        self.mean = None
        self.std = None

    def _sigmoid(self, z):
        # Clip z to avoid overflow in exp
        z = np.clip(z, -250, 250)
        return 1 / (1 + np.exp(-z))

    def fit(self, X, y):
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        n_samples, n_features = X.shape
        
        # Normalize features (Standardization)
        self.mean = np.mean(X, axis=0)
        self.std = np.std(X, axis=0)
        # Avoid division by zero
        self.std[self.std == 0] = 1.0
        
        X_norm = (X - self.mean) / self.std

        self.weights = np.zeros(n_features)
        self.bias = 0

        # Gradient Descent
        for _ in range(self.num_iterations):
            linear_model = np.dot(X_norm, self.weights) + self.bias
            y_predicted = self._sigmoid(linear_model)

            # Gradients
            dw = (1 / n_samples) * np.dot(X_norm.T, (y_predicted - y))
            db = (1 / n_samples) * np.sum(y_predicted - y)

            # Update parameters
            self.weights -= self.learning_rate * dw
            self.bias -= self.learning_rate * db

    def predict_proba(self, X):
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        if self.weights is None or self.mean is None:
            return np.array([0.5] * X.shape[0])
            
        X_norm = (X - self.mean) / self.std
        linear_model = np.dot(X_norm, self.weights) + self.bias
        return self._sigmoid(linear_model)


class MLEngine:
    def __init__(self, data_dir):
        self.history_file = os.path.join(data_dir, "trades_history.json")
        self.model = NumpyLogisticRegression(learning_rate=0.05, num_iterations=2000)
        self.is_trained = False
        self.feature_keys = [
            "rsi", "bb_upper", "bb_lower", "ema_9", "ema_21", "ema_50", 
            "atr", "price_vs_vwap", "cvd_value", "delta_to_target", "score"
        ]
        
    def _extract_features_and_labels(self):
        if not os.path.exists(self.history_file):
            return None, None
            
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                trades = json.load(f)
        except Exception as e:
            logger.error(f"[MLEngine] Error loading trades: {e}")
            return None, None
            
        X = []
        y = []
        
        for t in trades:
            # We only train on closed/settled trades that have raw_features
            if t.get("status") not in ["SETTLED", "CLOSED"]:
                continue
                
            res = t.get("result", "")
            if "WIN" in res:
                label = 1
            elif "LOSS" in res:
                label = 0
            else:
                continue
                
            snapshot = t.get("market_snapshot", {})
            raw = snapshot.get("raw_features")
            if not raw:
                # Fallback: if old trades don't have raw_features, skip them
                continue
                
            feature_vec = []
            valid = True
            for k in self.feature_keys:
                val = raw.get(k)
                if val is None:
                    valid = False
                    break
                feature_vec.append(float(val))
                
            if valid:
                X.append(feature_vec)
                y.append(label)
                
        if len(X) < 10:
            # Not enough data to train a reliable model
            return None, None
            
        return np.array(X), np.array(y)
        
    def train(self):
        X, y = self._extract_features_and_labels()
        if X is not None and len(X) >= 10:
            logger.info(f"[MLEngine] Training custom ML model on {len(X)} historical trades...")
            self.model.fit(X, y)
            self.is_trained = True
            logger.info("[MLEngine] Training complete.")
            return len(X)
        return 0
        
    def predict_probability(self, current_raw_features: dict) -> float:
        """
        Returns the ML model's probability of a WIN given the current features.
        Returns 0.5 (50%) if the model isn't trained yet.
        """
        if not self.is_trained:
            self.train()
            
        if not self.is_trained:
            return 0.5
            
        feature_vec = []
        for k in self.feature_keys:
            val = current_raw_features.get(k, 0.0)
            feature_vec.append(float(val))
            
        X_pred = np.array([feature_vec])
        prob = self.model.predict_proba(X_pred)[0]
        return prob
