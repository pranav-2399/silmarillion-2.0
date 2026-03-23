from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import meta, players, teams, matches, analytics

app = FastAPI(
    title="Silmarillion Cricket Analytics API",
    description="RESTful API for querying IPL cricket statistics and player analytics.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)         # GET /api/meta/*
app.include_router(players.router)      # GET /api/players/*
app.include_router(teams.router)        # GET /api/teams/*
app.include_router(matches.router)      # GET /api/matches/*, GET /api/venues
app.include_router(analytics.router)    # POST /api/analytics/*

# Old frontend calls /api/query and /api/values

app.include_router(
    analytics.router,
    prefix="",
    include_in_schema=False,
)

from fastapi import APIRouter as _AR
from routers.analytics import situational_query, get_filter_values
from pydantic import BaseModel
from typing import List, Dict, Any

_legacy = _AR()

class _QP(BaseModel):
    tables: List[str]
    fields: List[Dict[str, str]]
    filters: List[Dict[str, Any]]
    sort: List[Dict[str, str]]
    pagination: Dict[str, int]
    aggregate: bool = False

@_legacy.post("/api/query", include_in_schema=False)
async def _legacy_query(payload: _QP):
    from routers.analytics import QueryPayload
    return await situational_query(QueryPayload(**payload.dict()))

@_legacy.post("/api/values", include_in_schema=False)
async def _legacy_values(payload: Dict[str, Any]):
    return await get_filter_values(payload)

app.include_router(_legacy)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
