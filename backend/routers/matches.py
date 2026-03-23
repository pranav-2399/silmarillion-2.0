"""
routers/matches.py  –  Match info and scorecard endpoints.

Endpoints:
  GET /api/matches                  →  paginated match list with filters
  GET /api/matches/{match_id}       →  full match detail + scorecard summary
  GET /api/venues                   →  all unique venues
"""
from fastapi import APIRouter, HTTPException, Query
from database import query_one, query_all, query_scalar

router = APIRouter(tags=["Matches"])


# ─── Matches ──────────────────────────────────────────────────────────────────

matches_router = APIRouter(prefix="/api/matches")

@matches_router.get("")
def list_matches(
    venue: str      = Query("", description="Filter by venue (partial match)"),
    team: str       = Query("", description="Filter by team name (partial match)"),
    tournament: str = Query("", description="Filter by tournament name (partial)"),
    page: int       = Query(1, ge=1),
    limit: int      = Query(50, ge=1, le=500),
):
    """Paginated match list with optional venue/team/tournament filters."""
    where_parts = []
    params = []

    if venue:
        where_parts.append("M.Venue LIKE ?")
        params.append(f"%{venue}%")
    if team:
        where_parts.append("(T1.Team_name LIKE ? OR T2.Team_name LIKE ?)")
        params.extend([f"%{team}%", f"%{team}%"])
    if tournament:
        where_parts.append("TN.Tournament_Name LIKE ?")
        params.append(f"%{tournament}%")

    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    base = f"""
        FROM MATCHES M
        JOIN TEAMS T1  ON M.Team1_ID = T1.Team_ID
        JOIN TEAMS T2  ON M.Team2_ID = T2.Team_ID
        LEFT JOIN TEAMS W  ON M.Winner_team = W.Team_ID
        LEFT JOIN TOURNAMENTS TN ON M.Tournament_ID = TN.Tournament_ID
        {where}
    """

    total = query_scalar(f"SELECT COUNT(*) {base}", tuple(params))
    offset = (page - 1) * limit
    rows = query_all(
        f"""
        SELECT M.Match_ID, M.Match_name, M.Date, M.Venue,
               T1.Team_name AS team1, T2.Team_name AS team2,
               W.Team_name  AS winner, M.Win_margin, M.Win_margin_type,
               M.Result_type, TN.Tournament_Name AS tournament
        {base}
        ORDER BY M.Date DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [limit, offset]),
    )
    return {"total": total, "page": page, "limit": limit, "matches": rows}


@matches_router.get("/{match_id}")
def get_match(match_id: int):
    """Full match detail including scorecard (top batter + bowler per innings)."""
    match = query_one(
        """
        SELECT M.*,
               T1.Team_name AS team1_name, T2.Team_name AS team2_name,
               W.Team_name  AS winner_name,
               TN.Tournament_Name AS tournament
        FROM MATCHES M
        JOIN TEAMS T1  ON M.Team1_ID = T1.Team_ID
        JOIN TEAMS T2  ON M.Team2_ID = T2.Team_ID
        LEFT JOIN TEAMS W  ON M.Winner_team = W.Team_ID
        LEFT JOIN TOURNAMENTS TN ON M.Tournament_ID = TN.Tournament_ID
        WHERE M.Match_ID = ?
        """,
        (match_id,),
    )
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Top batting performances per innings
    batting = query_all(
        """
        SELECT D.Innings_no, P.Player_name,
               SUM(COALESCE(R.Runs_scored, 0)) AS runs,
               COUNT(D.Ball_no)                AS balls
        FROM DELIVERY D
        JOIN PLAYERS P ON D.Striker = P.Player_ID
        LEFT JOIN DELIVERY_OUTCOME_RUNS R ON (
            R.Match_ID=D.Match_ID AND R.Innings_no=D.Innings_no
            AND R.Over_no=D.Over_no AND R.Delivery_no=D.Delivery_no
        )
        WHERE D.Match_ID = ?
        GROUP BY D.Innings_no, D.Striker
        ORDER BY D.Innings_no ASC, runs DESC
        """,
        (match_id,),
    )

    # Top bowling performances per innings
    bowling = query_all(
        """
        SELECT D.Innings_no, P.Player_name,
               COUNT(D.Ball_no) AS balls,
               SUM(COALESCE(R.Runs_scored,0) + COALESCE(E.Runs_scored,0)) AS runs_given,
               COUNT(DISTINCT CASE WHEN W.Out_batter IS NOT NULL
                    THEN D.Over_no||'-'||D.Delivery_no END) AS wickets
        FROM DELIVERY D
        JOIN PLAYERS P ON D.Bowler = P.Player_ID
        LEFT JOIN DELIVERY_OUTCOME_RUNS    R ON (R.Match_ID=D.Match_ID AND R.Innings_no=D.Innings_no AND R.Over_no=D.Over_no AND R.Delivery_no=D.Delivery_no)
        LEFT JOIN DELIVERY_OUTCOME_WICKETS W ON (W.Match_ID=D.Match_ID AND W.Innings_no=D.Innings_no AND W.Over_no=D.Over_no AND W.Delivery_no=D.Delivery_no)
        LEFT JOIN DELIVERY_OUTCOME_EXTRAS  E ON (E.Match_ID=D.Match_ID AND E.Innings_no=D.Innings_no AND E.Over_no=D.Over_no AND E.Delivery_no=D.Delivery_no)
        WHERE D.Match_ID = ?
        GROUP BY D.Innings_no, D.Bowler
        ORDER BY D.Innings_no ASC, wickets DESC, runs_given ASC
        """,
        (match_id,),
    )

    match["batting_scorecard"] = batting
    match["bowling_scorecard"] = bowling
    return match


# ─── Venues ──────────────────────────────────────────────────────────────────

venues_router = APIRouter(prefix="/api/venues")

@venues_router.get("")
def list_venues():
    """All unique match venues with match counts."""
    venues = query_all(
        """
        SELECT Venue,
               COUNT(*) AS matches_hosted,
               MIN(Date) AS first_match,
               MAX(Date) AS last_match
        FROM MATCHES
        WHERE Venue IS NOT NULL
        GROUP BY Venue
        ORDER BY matches_hosted DESC
        """
    )
    return {"venues": venues}


# Export both under the same tag
router = APIRouter()
router.include_router(matches_router)
router.include_router(venues_router)
