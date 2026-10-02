
import re

with open("static/login.html", "r", encoding="utf-8") as f:
    content = f.read()

target = "<title>ShadowTrade AI - Login</title>"

network_script = """<title>ShadowTrade AI - Login</title>
    <!-- AUTO-DETECT API BACKEND -->
    <script>
        window.API_BASE_URL = "";
        
        (async function initApiBackend() {
            const isApp = window.location.protocol === "file:" || window.location.protocol.includes("capacitor");
            if (!isApp && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1" && !window.location.hostname.startsWith("192.168.")) {
                return; 
            }

            const localUrl = "http://192.168.1.194:8058";
            const remoteUrl = "https://moneyprinter.ngrok.app";
            const originalFetch = window.fetch;
            
            try {
                const controller = new AbortController();
                const id = setTimeout(() => controller.abort(), 1200);
                const res = await originalFetch(localUrl + "/api/health", { signal: controller.signal, mode: "no-cors" }).catch(e => null);
                clearTimeout(id);
                if (res) {
                    window.API_BASE_URL = localUrl;
                } else {
                    throw new Error("Local ping failed");
                }
            } catch (e) {
                window.API_BASE_URL = remoteUrl;
            }
            
            window.fetch = async function() {
                let [resource, config] = arguments;
                if (typeof resource === "string" && resource.startsWith("/api/")) {
                    resource = window.API_BASE_URL + resource;
                }
                return originalFetch(resource, config);
            };
        })();
    </script>"""

if target in content:
    content = content.replace(target, network_script)
else:
    # Fallback to <head>
    content = content.replace("<head>", "<head>\n" + network_script.replace("<title>ShadowTrade AI - Login</title>", ""))

with open("static/login.html", "w", encoding="utf-8") as f:
    f.write(content)

