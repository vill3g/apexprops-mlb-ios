import re
path = "static/js/dashboard.js"
with open(path, "r", encoding="utf-8") as f:
    js = f.read()

# Check if Notification API is used
if "new Notification" not in js:
    print("Notification API not yet in dashboard.js")
