"""
routers/meta.py  –  Database metadata and schema info.

Endpoints:
  GET /api/meta/summary   →  counts of players, teams, matches, deliveries
  GET /api/meta/schema    →  available tables and their columns
"""
from fastapi import APIRouter
from database import query_scalar, query_all

router = APIRouter(prefix="/api/meta", tags=["Meta"])


@router.get("/summary")
def get_summary():
    """High-level counts of every major entity in the database."""
    return {
        "players":    query_scalar("SELECT COUNT(*) FROM PLAYERS"),
        "teams":      query_scalar("SELECT COUNT(*) FROM TEAMS"),
        "matches":    query_scalar("SELECT COUNT(*) FROM MATCHES"),
        "deliveries": query_scalar("SELECT COUNT(*) FROM DELIVERY"),
        "tournaments":query_scalar("SELECT COUNT(*) FROM TOURNAMENTS"),
        "venues":     query_scalar("SELECT COUNT(DISTINCT Venue) FROM MATCHES"),
        "seasons":    query_scalar("SELECT COUNT(DISTINCT strftime('%Y', Date)) FROM MATCHES WHERE Date IS NOT NULL"),
    }


@router.get("/schema")
def get_schema():
    """Return column definitions for all main tables."""
    tables = ["PLAYERS", "TEAMS", "MATCHES", "TOURNAMENTS", "DELIVERY"]
    schema = {}
    from database import get_conn
    conn = get_conn()
    try:
        for t in tables:
            rows = conn.execute(f"PRAGMA table_info({t})").fetchall()
            schema[t] = [
                {"column": r["name"], "type": r["type"], "pk": bool(r["pk"])}
                for r in rows
            ]
    finally:
        conn.close()
    return schema
