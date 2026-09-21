import os
import sys
import json
import optuna
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
import logging

optuna.logging.set_verbosity(optuna.logging.WARNING)

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.btc.ml_ensemble import GodTierEnsemble
from backend.btc.ml_engine import FEATURE_KEYS

TRADES_FILE = os.path.join(os.path.dirname(__file__), '../data/trades_history.json')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '../data/trading_config.json')

def load_data():
    if not os.path.exists(TRADES_FILE):
        print(f"No historical trades found at {TRADES_FILE}")
        return None, None
        
    with open(TRADES_FILE, 'r') as f:
        try:
            trades = json.load(f)
        except:
            return None, None
            
    valid_trades = []
    for t in trades:
        raw = t.get("market_snapshot", {}).get("raw_features")
        if raw and isinstance(raw, dict) and t.get("status") in ["SETTLED", "CLOSED"]:
            res = str(t.get("result", "")).upper().strip()
            direction = str(t.get("direction", "")).upper().strip()
            side = str(t.get("side", "")).upper().strip()
            is_win = ("WIN" in res) or ("WON" in res)
            is_loss = ("LOSS" in res) or ("LOST" in res)
            
            if not is_win and not is_loss:
                continue
                
            label = None
            if direction == "ABOVE" or side == "YES":
                label = 1 if is_win else 0
            elif direction == "BELOW" or side == "NO":
                label = 0 if is_win else 1
            
            if label is not None:
                t["__tuner_label"] = label
                valid_trades.append(t)
                
    if len(valid_trades) < 50:
        print(f"Not enough valid trades for training. Found {len(valid_trades)}.")
        return None, None
        
    print(f"Loaded {len(valid_trades)} historical trades for tuning.")
    
    feature_keys = list(FEATURE_KEYS)
    
    X = []
    y = []
    for t in valid_trades:
        raw = t["market_snapshot"]["raw_features"]
        row = []
        for k in feature_keys:
            val = raw.get(k, 0.0)
            try:
                f_val = float(val) if val is not None else 0.0
                if not np.isfinite(f_val):
                    f_val = 0.0
            except (ValueError, TypeError):
                f_val = 0.0
            row.append(f_val)
        X.append(row)
        y.append(t["__tuner_label"])
        
    return np.array(X), np.array(y)

def objective(trial):
    X, y = load_data()
    if X is None:
        raise optuna.exceptions.TrialPruned()
        
    split_idx = int(len(X) * 0.7)
    X_train, y_train = X[:split_idx], y[:split_idx]
    X_test, y_test = X[split_idx:], y[split_idx:]
    
    n_estimators = trial.suggest_int('n_estimators', 20, 200, step=20)
    max_depth = trial.suggest_int('max_depth', 2, 8)
    learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3, log=True)
    rf_estimators = trial.suggest_int('rf_estimators', 20, 200, step=20)
    
    model = GodTierEnsemble(xgb_estimators=n_estimators, xgb_max_depth=max_depth, xgb_lr=learning_rate, rf_estimators=rf_estimators)
    
    try:
        model.fit(X_train, y_train)
    except Exception as e:
        print(f"Training failed: {e}")
        raise optuna.exceptions.TrialPruned()
        
    probs = model.predict_proba(X_test)
    preds = [1 if p[1] > 0.5 else 0 for p in probs]
    acc = accuracy_score(y_test, preds)
    return acc

def run_tuner():
    print("=======================================")
    print(" KALSHI AI - OPTUNA HYPERPARAMETER TUNER ")
    print("=======================================")
    
    X, y = load_data()
    if X is None:
        return
        
    study = optuna.create_study(direction='maximize')
    print("Starting optimization... this may take a few minutes.")
    
    study.optimize(objective, n_trials=5)
    
    print("\n=======================================")
    print(" TUNING COMPLETE")
    print("=======================================")
    print(f"Best Accuracy: {study.best_value * 100:.2f}%")
    print("Best Parameters:")
    for key, value in study.best_params.items():
        print(f"  {key}: {value}")
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        if "ai_settings" not in config:
            config["ai_settings"] = {}
            
        config["ai_settings"]["xgbEstimators"] = study.best_params["n_estimators"]
        config["ai_settings"]["xgbMaxDepth"] = study.best_params["max_depth"]
        config["ai_settings"]["xgbLearningRate"] = round(study.best_params["learning_rate"], 3)
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
            
        print("\n[SUCCESS] Automatically saved best XGBoost parameters to trading_config.json!")
    except Exception as e:
        print(f"Failed to update config: {e}")

if __name__ == "__main__":
    run_tuner()
