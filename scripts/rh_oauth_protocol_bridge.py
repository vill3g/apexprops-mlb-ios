"""
Windows URL Protocol Bridge for `cursor://anysphere.cursor-mcp/oauth/callback?code=...&state=...`
When Robinhood redirects the browser to `cursor://anysphere.cursor-mcp/oauth/callback?...`,
Windows invokes this script with the full URI as sys.argv[1].
It forwards the query string directly to http://127.0.0.1:8058/api/engine/investments/mcp/oauth/callback
so the user's Robinhood Agentic MCP token is exchanged and encrypted automatically!
"""

import sys
import urllib.parse
import webbrowser
import requests

def main():
    if len(sys.argv) < 2:
        return
    raw_uri = sys.argv[1].strip()
    if "?" not in raw_uri:
        return
    query_part = raw_uri.split("?", 1)[1]
    callback_url = f"http://127.0.0.1:8058/api/engine/investments/mcp/oauth/callback?{query_part}"
    try:
        # Trigger the token exchange directly on local backend
        requests.get(callback_url, timeout=10.0)
    except Exception:
        # Fallback: open in browser so the user sees the confirmation card
        webbrowser.open(callback_url)

if __name__ == "__main__":
    main()
