import os

html_path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\saas_dashboard.html"
login_path = r"C:\Users\Vill3\Desktop\ShadowTraderAi\static\login.html"

with open(html_path, "r", encoding="utf-8") as f:
    text = f.read()

start_idx = text.find('<div id="splash-screen"')
# The splash screen ends at:
# </div> <!-- end inner -->
# </div> <!-- end wrapper -->
# </div> <!-- end splash-screen -->
# So we can just find '<!-- Splash screen dismiss script'
end_idx = text.find('<!-- Splash screen dismiss script')

splash_html = text[start_idx:end_idx].strip()

# Now we inject it into login.html right after <body>
with open(login_path, "r", encoding="utf-8") as f:
    login_text = f.read()

if '<div id="splash-screen"' not in login_text:
    body_idx = login_text.find('<body')
    body_end_idx = login_text.find('>', body_idx) + 1
    
    # Also add the fade-out logic to login_text for when they actually need to log in
    # If the user has a valid token, checkExistingSession() redirects, so the splash just stays up.
    # If the user does not have a valid token, checkExistingSession() finishes and we fade out the splash.
    
    splash_js = """
    <script>
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
    </script>
    """
    
    new_login_text = login_text[:body_end_idx] + "\n" + splash_html + "\n" + splash_js + "\n" + login_text[body_end_idx:]
    
    # Now we must call window.hideLoginSplash() inside checkExistingSession() if no redirect happened.
    # The IIFE is (function checkExistingSession() { ... })();
    # At the end of the IIFE, if it didn't return (redirect), we should call it.
    
    # We can just let the fallback timeout handle it, or explicitly call it.
    # The easiest is inserting `if(window.hideLoginSplash) window.hideLoginSplash();` at the end of the IIFE block.
    iife_end = new_login_text.find('})();', body_end_idx)
    new_login_text = new_login_text[:iife_end] + "    if(window.hideLoginSplash) window.hideLoginSplash();\n      " + new_login_text[iife_end:]
    
    with open(login_path, "w", encoding="utf-8") as f:
        f.write(new_login_text)
    print("Injected splash screen into login.html")
else:
    print("Splash screen already exists in login.html")
