import sys
sys.path.append('.')
from backend.btc.ml_engine import get_ml_engine

m = get_ml_engine('backend/data')
try:
    m._extract_features_and_labels("all")
except Exception as e:
    import traceback
    traceback.print_exc()
print("Extract finished.")
