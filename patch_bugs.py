
import re

# Fix main.py
with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()
    
target_prewarm = "get_daily_hr_rbi_props"
if target_prewarm in content:
    content = content.replace("get_daily_hr_rbi_props", "get_cached_homeruns")
    
with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)

# Fix soccer_router.py
with open("backend/soccer_router.py", "r", encoding="utf-8") as f:
    content = f.read()

if "import logging" not in content:
    content = "import logging\nlogger = logging.getLogger(__name__)\n" + content

with open("backend/soccer_router.py", "w", encoding="utf-8") as f:
    f.write(content)

# Fix AutoExecutor defaults
with open("backend/btc/auto_executor/executor.py", "r", encoding="utf-8") as f:
    content = f.read()

target_reversal = """if "positionReversal" not in self.ai_settings:
                                self.ai_settings["positionReversal"] = False"""
new_reversal = """if "positionReversal" not in self.ai_settings:
                                self.ai_settings["positionReversal"] = True"""

content = content.replace(target_reversal, new_reversal)

with open("backend/btc/auto_executor/executor.py", "w", encoding="utf-8") as f:
    f.write(content)

