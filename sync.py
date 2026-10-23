import shutil
import os
for f in ["backend/routes/engine.py", "backend/sports_bridge/executor.py", "backend/sports_bridge/prediction_client.py"]:
    shutil.copy(f, f"C:/Users/Vill3/Desktop/ShadowTraderAi/{f}")
print("Synced!")
