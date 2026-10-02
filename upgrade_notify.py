
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the iosNotify logic
old_notify = """        window.enableIosNotifications = true;

        window.iosNotify = function(title, subtitle, type="success") {
            if (!window.enableIosNotifications) return;"""

new_notify = """        window.enableIosNotifications = localStorage.getItem("enableIosNotifications") !== "false";

        window.toggleIosNotifications = function(checked) {
            window.enableIosNotifications = checked;
            localStorage.setItem("enableIosNotifications", checked);
            if (checked && "Notification" in window && Notification.permission !== "granted" && Notification.permission !== "denied") {
                Notification.requestPermission().then(permission => {
                    if (permission === "granted") {
                        new Notification("ShadowTrade AI", { body: "System notifications are now active. You will receive alerts on your lockscreen." });
                        if (typeof showToast === "function") showToast("System notifications enabled!", "success");
                    }
                });
            }
        };

        window.iosNotify = function(title, subtitle, type="success") {
            if (!window.enableIosNotifications) return;

            if ("Notification" in window && Notification.permission === "granted") {
                try {
                    new Notification(title, { body: subtitle });
                } catch(e) {}
            }
"""
content = content.replace(old_notify, new_notify)

# 2. Update the toggle input
old_toggle = """<input type="checkbox" id="ios-notify-toggle" class="sr-only peer" checked onchange="window.enableIosNotifications = this.checked;">"""
new_toggle = """<input type="checkbox" id="ios-notify-toggle" class="sr-only peer" checked onchange="window.toggleIosNotifications(this.checked)">"""
content = content.replace(old_toggle, new_toggle)

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)
print("Updated successfully.")

