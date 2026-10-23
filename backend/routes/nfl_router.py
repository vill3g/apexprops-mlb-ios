
from fastapi import APIRouter, Request, Query, Depends
from typing import Optional
from backend.auth.dependencies import require_auth
from backend.routes.engine_sports import api_sports_events, api_sports_predict, api_sports_execute, api_sports_trade_manual

router = APIRouter(prefix="/api/engine/NFL")

@router.get("/events", dependencies=[Depends(require_auth)])
def get_nfl_events(league: Optional[str] = None, filter: Optional[str] = None):
    return api_sports_events(sport="NFL", league=league, filter=filter)

@router.get("/predict", dependencies=[Depends(require_auth)])
def get_nfl_predict(event_ticker: str = Query(...)):
    return api_sports_predict(event_ticker=event_ticker)

@router.post("/execute", dependencies=[Depends(require_auth)])
async def post_nfl_execute(request: Request):
    return await api_sports_execute(request=request)

@router.post("/trade/manual", dependencies=[Depends(require_auth)])
async def post_nfl_trade_manual(
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
        sport="NFL", trade_size=trade_size, amount_dollars=amount_dollars,
        user_id=user_id, request=request
    )
