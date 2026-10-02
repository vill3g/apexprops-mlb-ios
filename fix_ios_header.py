
import re
with open("static/saas_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Change status bar style
content = content.replace("<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\">", "<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black\">")

# 2. Remove the weird main-header::before rule
bad_css = """        #main-header::before {
            content: "";
            position: absolute;
            top: -150px;
            left: 0;
            right: 0;
            height: 150px;
            background-color: #000000;
            pointer-events: none;
        }"""
content = content.replace(bad_css, "")

# 3. Simplify the header padding just in case, but keep safe-area for notched iPhones if not using PWA mode
# Wait, let us leave style="padding-top: calc(env(safe-area-inset-top, 0px));" because if content="black" works, safe-area-inset-top will naturally become 0 on iOS PWA, but still protect notched browsers.

with open("static/saas_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

