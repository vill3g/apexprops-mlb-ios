import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

bad = '''app = FastAPI(
from backend.database.models import init_db
init_db()
from backend.auth.routes import router as auth_router
app.include_router(auth_router)
    title="BTC 15M Pattern & Confluence Engine",
    version="4.0.0",
    description="Real-time Bitcoin 15-Minute Pattern & Confluence Analyzer."
)'''

good = '''app = FastAPI(
    title="BTC 15M Pattern & Confluence Engine",
    version="4.0.0",
    description="Real-time Bitcoin 15-Minute Pattern & Confluence Analyzer."
)

from backend.database.models import init_db
init_db()
from backend.auth.routes import router as auth_router
app.include_router(auth_router)'''

c = c.replace(bad, good)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(c)
