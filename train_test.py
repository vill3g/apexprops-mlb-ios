import sys
sys.path.append('.')
from backend.btc.ml_engine import get_ml_engine

m = get_ml_engine('backend/data')
res = m.train(force=True)
print("TRAINED:", res)
