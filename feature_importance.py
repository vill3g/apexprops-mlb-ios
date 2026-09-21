from backend.btc.ml_engine import get_ml_engine
import logging
logging.basicConfig(level=logging.ERROR)

eng = get_ml_engine()
target_eng = eng.day_engine if hasattr(eng, 'day_engine') else eng
if hasattr(target_eng, 'model') and hasattr(target_eng.model, 'model'):
    xgb = target_eng.model.model.named_steps['xgbclassifier']
    importances = xgb.feature_importances_
    features = target_eng.feature_keys
    
    paired = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
    print("XGBOOST FEATURE IMPORTANCES (DAY MODEL):")
    for feat, imp in paired:
        if 'volume' in feat:
            print(f"--> {feat}: {imp:.4f} <--")
        else:
            print(f"{feat}: {imp:.4f}")
else:
    print("No feature importances found.")
