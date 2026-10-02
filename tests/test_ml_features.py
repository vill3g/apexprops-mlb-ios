import pytest
from backend.btc.ml_engine import normalize_features

def test_feature_normalization():
    raw = {
        "ema_50": 60000.0,
        "ema_9": 66000.0,
        "atr": 600.0,
        "volume_24h": 1000.0
    }
    norm = normalize_features(raw)
    
    # 66000 / 60000 - 1 = 0.1
    assert abs(norm["ema_9"] - 0.1) < 1e-5
    # (600 / 60000) * 100 = 1.0
    assert abs(norm["atr"] - 1.0) < 1e-5

