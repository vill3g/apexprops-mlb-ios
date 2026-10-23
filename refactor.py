import re

def main():
    engine_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\engine.py'
    sports_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\engine_sports.py'
    nfl_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\nfl_router.py'
    mlb_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\mlb_router.py'
    ufc_path = r'C:\Users\Vill3\Desktop\kalshi-ai-trader\backend\routes\ufc_router.py'

    with open(engine_path, 'r', encoding='utf-8') as f:
        content = f.read()

    start_match = re.search(r'def _get_user_sports_criteria\(user_id: int\) -> dict:', content)
    if not start_match:
        print("Could not find start of sports logic.")
        return
        
    start_idx = start_match.start()
    
    end_match = re.search(r'# -------------------------------------------------------------\n# Live Kalshi Market Cache & Scanner Endpoints', content)
    if not end_match:
        print("Could not find end of sports logic.")
        return
        
    end_idx = end_match.start()
    
    sports_content = content[start_idx:end_idx]
    
    imports_match = re.search(r'router = APIRouter', content)
    imports_text = content[:imports_match.start()]
    
    sports_engine_code = imports_text + "\n\n" + """
from fastapi import APIRouter
sports_router = APIRouter()

""" + sports_content.replace('@_engine_root_router.', '@sports_router.')
    
    with open(sports_path, 'w', encoding='utf-8') as f:
        f.write(sports_engine_code)

    # Now create nfl, mlb, ufc routers
    sub_router_template = """
from fastapi import APIRouter, Request, Query, Depends
from typing import Optional
from backend.auth.dependencies import require_auth
from backend.routes.engine_sports import api_sports_events, api_sports_predict, api_sports_execute, api_sports_trade_manual

router = APIRouter(prefix="/api/engine/{SPORT}")

@router.get("/events", dependencies=[Depends(require_auth)])
def get_{SPORT_LOWER}_events(league: Optional[str] = None, filter: Optional[str] = None):
    return api_sports_events(sport="{SPORT}", league=league, filter=filter)

@router.get("/predict", dependencies=[Depends(require_auth)])
def get_{SPORT_LOWER}_predict(event_ticker: str = Query(...)):
    return api_sports_predict(event_ticker=event_ticker)

@router.post("/execute", dependencies=[Depends(require_auth)])
async def post_{SPORT_LOWER}_execute(request: Request):
    return await api_sports_execute(request=request)

@router.post("/trade/manual", dependencies=[Depends(require_auth)])
async def post_{SPORT_LOWER}_trade_manual(
    event_ticker: Optional[str] = Query(None),
    ticker: Optional[str] = Query(None),
    market_ticker: Optional[str] = Query(None),
    side: Optional[str] = Query("YES"),
    direction: Optional[str] = Query(None),
    manual_team: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    trade_size: Optional[float] = Query(None),
    amount_dollars: Optional[float] = Query(None),
    user_id: Optional[int] = Query(None),
    request: Request = None
):
    return await api_sports_trade_manual(
        event_ticker=event_ticker, ticker=ticker, market_ticker=market_ticker,
        side=side, direction=direction, manual_team=manual_team, team=team,
        sport="{SPORT}", trade_size=trade_size, amount_dollars=amount_dollars,
        user_id=user_id, request=request
    )
"""

    with open(nfl_path, 'w', encoding='utf-8') as f:
        f.write(sub_router_template.replace("{SPORT}", "NFL").replace("{SPORT_LOWER}", "nfl"))
        
    with open(mlb_path, 'w', encoding='utf-8') as f:
        f.write(sub_router_template.replace("{SPORT}", "MLB").replace("{SPORT_LOWER}", "mlb"))
        
    with open(ufc_path, 'w', encoding='utf-8') as f:
        f.write(sub_router_template.replace("{SPORT}", "UFC").replace("{SPORT_LOWER}", "ufc"))
        
    # Wire them up in engine.py
    wiring = """
# Sports routes have been modularized
from backend.routes.engine_sports import sports_router
from backend.routes.nfl_router import router as nfl_router
from backend.routes.mlb_router import router as mlb_router
from backend.routes.ufc_router import router as ufc_router

_engine_root_router.include_router(sports_router)
_engine_root_router.include_router(nfl_router)
_engine_root_router.include_router(mlb_router)
_engine_root_router.include_router(ufc_router)
"""

    new_engine_content = content[:start_idx] + wiring + "\n" + content[end_idx:]
    
    with open(engine_path, 'w', encoding='utf-8') as f:
        f.write(new_engine_content)

    print("Refactoring done.")
    
if __name__ == '__main__':
    main()
