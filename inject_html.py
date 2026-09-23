import re

with open('backend/main.py', 'r') as f:
    content = f.read()

injection = '''
@app.get("/login.html")
async def get_login():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "login.html"))

@app.get("/saas_dashboard.html")
async def get_saas_dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "saas_dashboard.html"))
'''

if 'get_login' not in content:
    content = content.replace(
        'def root():\n    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "index.html"))',
        'def root():\n    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "index.html"))\n' + injection
    )
    with open('backend/main.py', 'w') as f:
        f.write(content)
    print("Injected routes.")
