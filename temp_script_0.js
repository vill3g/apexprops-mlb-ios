
        window.API_BASE_URL = "";
        
        (async function initApiBackend() {
            const isApp = window.location.protocol === "file:" || window.location.protocol.includes("capacitor");
            
            // If we are running in any standard web browser (http/https), always use same-origin relative API routes.
            if (!isApp) {
                console.log("Running in standard web browser, using relative API routes.");
                return; 
            }

            const localUrl = "http://192.168.1.194:8058";
            const remoteUrl = "https://moneyprinter.ngrok.app";
            const originalFetch = window.fetch;
            
            try {
                const controller = new AbortController();
                const id = setTimeout(() => controller.abort(), 1200);
                
                console.log("Pinging local network...");
                // no-cors so we do not get blocked just testing if the server is physically reachable
                const res = await originalFetch(localUrl + "/api/health", { signal: controller.signal, mode: "no-cors" }).catch(e => null);
                clearTimeout(id);
                
                if (res) {
                    window.API_BASE_URL = localUrl;
                    console.log("Connected to Home Wi-Fi Backend:", window.API_BASE_URL);
                } else {
                    throw new Error("Local ping failed");
                }
            } catch (e) {
                console.log("Not on Home Wi-Fi, falling back to Ngrok tunnel:", remoteUrl);
                window.API_BASE_URL = remoteUrl;
            }
            
            // Override global fetch to automatically prepend the chosen base URL while preserving existing fetch wrappers
            const currentFetch = window.fetch;
            window.fetch = async function() {
                let [resource, config] = arguments;
                if (typeof resource === "string" && resource.startsWith("/api/")) {
                    resource = window.API_BASE_URL + resource;
                }
                return currentFetch(resource, config);
            };
        })();
    