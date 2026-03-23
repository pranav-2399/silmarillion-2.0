"""
routers/teams.py  –  Team info and squad endpoints.

Endpoints:
  GET /api/teams                  →  all teams
  GET /api/teams/{team_id}        →  team detail + captain history
  GET /api/teams/{team_id}/players →  players who played for this team
"""
from fastapi import APIRouter, HTTPException
from database import query_one, query_all, query_scalar

router = APIRouter(prefix="/api/teams", tags=["Teams"])


@router.get("")
def list_teams():
    """All IPL franchises with basic info."""
    teams = query_all(
        """
        SELECT T.Team_ID, T.Team_name, T.Founded_year,
               COUNT(DISTINCT M.Match_ID) AS matches_played
        FROM TEAMS T
        LEFT JOIN MATCHES M ON (M.Team1_ID = T.Team_ID OR M.Team2_ID = T.Team_ID)
        GROUP BY T.Team_ID
        ORDER BY T.Team_name
        """
    )
    return {"teams": teams}


@router.get("/{team_id}")
def get_team(team_id: int):
    """Team profile including captain history and titles won."""
    team = query_one("SELECT * FROM TEAMS WHERE Team_ID = ?", (team_id,))
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Captain history
    captains = query_all(
        """
        SELECT P.Player_name, TCI.Year
        FROM TEAM_CAPTAIN_INFORMATION TCI
        JOIN PLAYERS P ON TCI.Captain_ID = P.Player_ID
        WHERE TCI.Team_ID = ?
        ORDER BY TCI.Year DESC
        """,
        (team_id,),
    )

    # Tournament wins
    titles = query_all(
        """
        SELECT Tournament_Name
        FROM TOURNAMENTS
        WHERE Winner_team_id = ?
        ORDER BY Tournament_ID DESC
        """,
        (team_id,),
    )

    # Match record
    total    = query_scalar("SELECT COUNT(*) FROM MATCHES WHERE Team1_ID=? OR Team2_ID=?", (team_id, team_id))
    wins     = query_scalar("SELECT COUNT(*) FROM MATCHES WHERE Winner_team=?", (team_id,))

    team["captain_history"] = captains
    team["titles"]          = [t["Tournament_Name"] for t in titles]
    team["matches_played"]  = total
    team["wins"]            = wins
    team["losses"]          = (total or 0) - (wins or 0)
    return team


@router.get("/{team_id}/players")
def get_team_players(team_id: int):
    """All players who have batted or bowled for this team."""
    # Check team exists
    if not query_one("SELECT 1 FROM TEAMS WHERE Team_ID = ?", (team_id,)):
        raise HTTPException(status_code=404, detail="Team not found")

    players = query_all(
        """
        SELECT DISTINCT P.Player_ID, P.Player_name,
               P.Runs_scored, P.Batting_average, P.Batting_strike_rate,
               P.Wickets_taken, P.Economy
        FROM PLAYERS P
        JOIN DELIVERY D ON (D.Striker = P.Player_ID OR D.Bowler = P.Player_ID)
        JOIN MATCHES  M ON D.Match_ID = M.Match_ID
        WHERE M.Team1_ID = ? OR M.Team2_ID = ?
        ORDER BY P.Runs_scored DESC
        """,
        (team_id, team_id),
    )
    return {"team_id": team_id, "players": players}
