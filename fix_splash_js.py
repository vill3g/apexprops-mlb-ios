import os

login_path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\login.html"

with open(login_path, "r", encoding="utf-8") as f:
    text = f.read()

# Remove the broken IIFE injection
text = text.replace("    if(window.hideLoginSplash) window.hideLoginSplash();\n      ", "")

# We already injected the splash HTML.
# Let's just update the javascript inside to be robust.

old_js = """<script>
        // Only hide the splash screen if they are NOT being redirected.
        // We will call this if the session check finishes and doesn't redirect.
        window.hideLoginSplash = function() {
            const splash = document.getElementById("splash-screen");
            const bar = document.getElementById("splash-bar");
            if (bar) bar.style.width = "100%";
            if (splash) {
                setTimeout(() => {
                    splash.style.opacity = "0";
                    splash.style.transform = "scale(1.03)";
                    setTimeout(() => splash.remove(), 700);
                }, 800); // Quick fade if we are staying on login
            }
        };
        // Fallback: if script fails or something, hide after 2.5s anyway
        setTimeout(() => {
            if(document.getElementById("splash-screen")) window.hideLoginSplash();
        }, 2500);
    </script>"""

new_js = """<script>
        // Only hide the splash screen if they are NOT being redirected.
        window.hideLoginSplash = function() {
            const splash = document.getElementById("splash-screen");
            const bar = document.getElementById("splash-bar");
            if (bar) bar.style.width = "100%";
            if (splash) {
                setTimeout(() => {
                    splash.style.opacity = "0";
                    splash.style.transform = "scale(1.03)";
                    setTimeout(() => splash.remove(), 700);
                }, 800);
            }
        };
        // If we stay on this page and fully load (no redirect happened), fade it out!
        window.addEventListener('load', () => {
            window.hideLoginSplash();
        });
        // Ultimate fallback
        setTimeout(() => {
            if(document.getElementById("splash-screen")) window.hideLoginSplash();
        }, 3000);
    </script>"""

if old_js in text:
    text = text.replace(old_js, new_js)
else:
    # Just to be sure, let's replace the script entirely if it mutated
    start_script = text.find('<script>\n        // Only hide the splash screen')
    end_script = text.find('</script>', start_script) + 9
    if start_script != -1:
        text = text[:start_script] + new_js + text[end_script:]

with open(login_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Updated JS logic in login.html")
