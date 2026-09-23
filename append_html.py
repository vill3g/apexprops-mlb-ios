import os

with open('backend/main.py', 'a', encoding='utf-8') as f:
    f.write("""

@app.get("/login.html")
def get_login():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "login.html"))

@app.get("/saas_dashboard.html")
def get_saas_dashboard():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "saas_dashboard.html"))
""")
