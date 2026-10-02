
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("function openSettings() {", """function openSettings() {
    setTimeout(() => {
        const notifyToggle = document.getElementById("ios-notify-toggle");
        if (notifyToggle) notifyToggle.checked = window.enableIosNotifications;
    }, 50);""")

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

