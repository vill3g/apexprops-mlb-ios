import os, json, urllib.request, urllib.error
from dotenv import load_dotenv
load_dotenv()
k = os.environ["GEMINI_API_KEY"]
for m in ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
    body = json.dumps({"contents": [{"parts": [{"text": "Reply with the word ok"}]}]}).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}), timeout=25)
        print(m, r.status)
    except urllib.error.HTTPError as e:
        print(m, "HTTP", e.code)
    except Exception as e:
        print(m, "ERR", repr(e))
