import os
import json
import logging
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from backend.btc.indicators import add_all_indicators

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "model_cache")
XGB_MODEL_PATH = os.path.join(CACHE_DIR, "forex_xgb.json")

FEATURES = [
    "rsi", "bb_percent_b", "ema_9_diff", "ema_21_diff", "atr", 
    "vol_ratio", "hour_of_day"
]

def load_or_train_xgb_model(pair: str = "EURUSD", force_retrain: bool = False):
    """
    Load the XGBoost model, or train a new one using 60 days of 15m data.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if os.path.exists(XGB_MODEL_PATH) and not force_retrain:
        model = xgb.XGBClassifier()
        model.load_model(XGB_MODEL_PATH)
        return model
        
    logger.info("Training new Forex XGBoost Model...")
    from backend.forex.data_fetcher import fetch_forex_candles
    
    # yfinance max period for 15m is 60d
    df = fetch_forex_candles(pair, "15m", limit=60 * 24 * 4) # approx 60 days
    if df.empty or len(df) < 500:
        logger.warning("Not enough data to train Forex ML model.")
        return None
        
    df = add_all_indicators(df)
    
    # Feature Engineering
    df["ema_9_diff"] = (df["close"] - df["ema_9"]) / df["close"]
    df["ema_21_diff"] = (df["close"] - df["ema_21"]) / df["close"]
    df["bb_percent_b"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-9)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
    
    # Get EST hour
    import pytz
    df["hour_of_day"] = df["datetime"].dt.tz_convert("America/New_York").dt.hour
    
    df = df.dropna(subset=FEATURES).copy()
    
    # Generate Labels: Did price rise 1 ATR before it dropped 1 ATR? (Bullish bias)
    # Simple future lookahead for training
    df["future_high"] = df["high"].shift(-1).rolling(10, min_periods=1).max()
    df["future_low"] = df["low"].shift(-1).rolling(10, min_periods=1).min()
    
    df["bull_hit"] = df["future_high"] >= (df["close"] + df["atr"])
    df["bear_hit"] = df["future_low"] <= (df["close"] - df["atr"])
    
    # Target = 1 if Bull hit before Bear hit, else 0
    # Simplification for bootstrap: if bull_hit and not bear_hit -> 1
    df["target"] = ((df["bull_hit"]) & (~df["bear_hit"])).astype(int)
    
    X = df[FEATURES]
    y = df["target"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42,
        eval_metric="logloss"
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    model.save_model(XGB_MODEL_PATH)
    logger.info(f"Forex XGBoost Model trained and saved to {XGB_MODEL_PATH}")
    return model

def predict_forex_probability(summary: dict) -> float:
    """
    Returns probability of a successful trade setup (0.0 to 1.0).
    """
    model = load_or_train_xgb_model()
    if not model:
        return 0.5
        
    price = summary["price"]
    
    # Construct feature vector matching training
    try:
        from datetime import datetime
        import pytz
        now_est = datetime.now(pytz.timezone("America/New_York"))
        
        bb_upper = summary.get("bb_upper", price)
        bb_lower = summary.get("bb_lower", price)
        bb_pct_b = (price - bb_lower) / (bb_upper - bb_lower + 1e-9)
        
        feat_vector = pd.DataFrame([{
            "rsi": summary.get("rsi", 50.0),
            "bb_percent_b": bb_pct_b,
            "ema_9_diff": (price - summary.get("ema_9", price)) / price,
            "ema_21_diff": (price - summary.get("ema_21", price)) / price,
            "atr": summary.get("atr", 0.001),
            "vol_ratio": summary.get("vol_ratio", 1.0),
            "hour_of_day": now_est.hour
        }])
        
        prob = model.predict_proba(feat_vector)[0][1] # Probability of Class 1
        return float(prob)
        
    except Exception as e:
        logger.error(f"Failed ML prediction: {e}")
        return 0.5
