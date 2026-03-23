"""
routers/players.py  –  Player profile and career stats endpoints.

Endpoints:
  GET /api/players                →  paginated list, supports ?search= & ?sort=
  GET /api/players/{player_id}    →  full player profile + career stats
  GET /api/players/{player_id}/matches  →  matches the player appeared in
"""
from fastapi import APIRouter, HTTPException, Query
from database import query_one, query_all, query_scalar, get_conn

router = APIRouter(prefix="/api/players", tags=["Players"])


@router.get("")
def list_players(
    search: str = Query("", description="Filter by player name"),
    sort: str  = Query("Runs_scored", description="Column to sort by"),
    dir: str   = Query("DESC", description="ASC or DESC"),
    page: int  = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Return a paginated list of players.
    Supports fuzzy name search and sorting by any career stat column.
    """
    allowed_sorts = {
        "Player_name", "Runs_scored", "Batting_average", "Batting_strike_rate",
        "Wickets_taken", "Economy", "Bowling_average", "Hundreds", "Fifties",
        "Matches_played", "Innings_batted"
    }
    sort_col = sort if sort in allowed_sorts else "Runs_scored"
    sort_dir = "DESC" if dir.upper() == "DESC" else "ASC"

    where = "WHERE Player_name LIKE ?" if search else ""
    params_list = [f"%{search}%"] if search else []

    count = query_scalar(
        f"SELECT COUNT(*) FROM PLAYERS {where}", tuple(params_list)
    )

    offset = (page - 1) * limit
    rows = query_all(
        f"""
        SELECT Player_ID, Player_name, Matches_played, Innings_batted,
               Runs_scored, Batting_average, Batting_strike_rate, Hundreds, Fifties,
               Wickets_taken, Economy, Bowling_average, Five_wicket_hauls
        FROM PLAYERS {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
        """,
        tuple(params_list + [limit, offset]),
    )
    return {"total": count, "page": page, "limit": limit, "players": rows}


@router.get("/{player_id}")
def get_player(player_id: str):
    """Full player profile including all career stats."""
    player = query_one(
        "SELECT * FROM PLAYERS WHERE Player_ID = ?", (player_id,)
    )
    if not player:
        raise HTTPException(status_code=404, detail=f"Player '{player_id}' not found")

    # Also fetch any teams they've captained
    captaincies = query_all(
        """
        SELECT T.Team_name, TCI.Year
        FROM TEAM_CAPTAIN_INFORMATION TCI
        JOIN TEAMS T ON TCI.Team_ID = T.Team_ID
        WHERE TCI.Captain_ID = ?
        ORDER BY TCI.Year DESC
        """,
        (player_id,),
    )
    player["captaincies"] = captaincies
    return player


@router.get("/{player_id}/matches")
def get_player_matches(
    player_id: str,
    page: int  = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
):
    """Matches this player appeared in as batter or bowler."""
    # Check player exists
    if not query_one("SELECT 1 FROM PLAYERS WHERE Player_ID = ?", (player_id,)):
        raise HTTPException(status_code=404, detail="Player not found")

    offset = (page - 1) * limit
    rows = query_all(
        """
        SELECT DISTINCT
            M.Match_ID, M.Match_name, M.Date, M.Venue,
            T1.Team_name AS team1, T2.Team_name AS team2,
            W.Team_name  AS winner, M.Win_margin, M.Win_margin_type
        FROM DELIVERY D
        JOIN MATCHES M  ON D.Match_ID = M.Match_ID
        JOIN TEAMS   T1 ON M.Team1_ID = T1.Team_ID
        JOIN TEAMS   T2 ON M.Team2_ID = T2.Team_ID
        LEFT JOIN TEAMS W ON M.Winner_team = W.Team_ID
        WHERE D.Striker = ? OR D.Bowler = ?
        ORDER BY M.Date DESC
        LIMIT ? OFFSET ?
        """,
        (player_id, player_id, limit, offset),
    )
    total = query_scalar(
        """
        SELECT COUNT(DISTINCT D.Match_ID) FROM DELIVERY D
        WHERE D.Striker = ? OR D.Bowler = ?
        """,
        (player_id, player_id),
    )
    return {"total": total, "page": page, "limit": limit, "matches": rows}
