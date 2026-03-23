"""
routers/analytics.py  –  Advanced situational analytics endpoints.

Endpoints:
  POST /api/analytics/query      →  dynamic situational engine (AND/OR/NOT filters + wildcards)
  POST /api/analytics/values     →  dynamic filter suggestion lists
  GET  /api/analytics/leaderboard →  top-N players by any metric
  POST /api/analytics/compare    →  side-by-side player comparison
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import traceback

from database import get_conn, query_all, query_one

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# ─── Shared metric expressions ────────────────────────────────────────────────

METRIC_EXPRESSIONS = {
    'Innings_batted':      "COUNT(DISTINCT CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker THEN DELIVERY.Match_ID || '-' || DELIVERY.Innings_no END)",
    'Runs_scored':         "SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker THEN COALESCE(DELIVERY_OUTCOME_RUNS.Runs_scored, 0) ELSE 0 END)",
    'Balls_faced':         "COUNT(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker THEN DELIVERY.Ball_no END)",
    'Fours':               "SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker AND DELIVERY_OUTCOME_RUNS.Runs_scored = 4 THEN 1 ELSE 0 END)",
    'Sixes':               "SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker AND DELIVERY_OUTCOME_RUNS.Runs_scored = 6 THEN 1 ELSE 0 END)",
    'Batting_average':     "CAST(SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker THEN COALESCE(DELIVERY_OUTCOME_RUNS.Runs_scored,0) ELSE 0 END) AS REAL) / NULLIF(COUNT(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker AND DELIVERY_OUTCOME_WICKETS.Match_ID IS NOT NULL THEN 1 END), 0)",
    'Batting_strike_rate': "100.0 * SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker THEN COALESCE(DELIVERY_OUTCOME_RUNS.Runs_scored,0) ELSE 0 END) / NULLIF(COUNT(CASE WHEN PLAYERS.Player_ID = DELIVERY.Striker THEN DELIVERY.Ball_no END), 0)",
    'Wickets_taken':       "COUNT(DISTINCT CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler AND DELIVERY_OUTCOME_WICKETS.Out_batter IS NOT NULL THEN DELIVERY.Match_ID||'-'||DELIVERY.Innings_no||'-'||DELIVERY.Over_no||'-'||DELIVERY.Delivery_no END)",
    'Balls_bowled':        "COUNT(CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler THEN DELIVERY.Ball_no END)",
    'Runs_given':          "SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler THEN COALESCE(DELIVERY_OUTCOME_RUNS.Runs_scored,0) + COALESCE(DELIVERY_OUTCOME_EXTRAS.Runs_scored, 0) ELSE 0 END)",
    'Economy':             "6.0 * SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler THEN COALESCE(DELIVERY_OUTCOME_RUNS.Runs_scored,0) + COALESCE(DELIVERY_OUTCOME_EXTRAS.Runs_scored,0) ELSE 0 END) / NULLIF(COUNT(CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler THEN DELIVERY.Ball_no END), 0)",
    'Bowling_average':     "CAST(SUM(CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler THEN COALESCE(DELIVERY_OUTCOME_RUNS.Runs_scored,0)+COALESCE(DELIVERY_OUTCOME_EXTRAS.Runs_scored,0) ELSE 0 END) AS REAL) / NULLIF(COUNT(DISTINCT CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler AND DELIVERY_OUTCOME_WICKETS.Out_batter IS NOT NULL THEN DELIVERY.Match_ID||'-'||DELIVERY.Innings_no||'-'||DELIVERY.Over_no||'-'||DELIVERY.Delivery_no END), 0)",
    'Bowling_strike_rate': "CAST(COUNT(CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler THEN DELIVERY.Ball_no END) AS REAL) / NULLIF(COUNT(DISTINCT CASE WHEN PLAYERS.Player_ID = DELIVERY.Bowler AND DELIVERY_OUTCOME_WICKETS.Out_batter IS NOT NULL THEN DELIVERY.Match_ID||'-'||DELIVERY.Innings_no||'-'||DELIVERY.Over_no||'-'||DELIVERY.Delivery_no END), 0)",
    'Hundreds': "COUNT(DISTINCT CASE WHEN (SELECT SUM(R.Runs_scored) FROM DELIVERY_OUTCOME_RUNS R JOIN DELIVERY D2 ON (R.Match_ID=D2.Match_ID AND R.Innings_no=D2.Innings_no AND R.Over_no=D2.Over_no AND R.Delivery_no=D2.Delivery_no) WHERE D2.Match_ID=DELIVERY.Match_ID AND D2.Striker=PLAYERS.Player_ID) >= 100 THEN DELIVERY.Match_ID END)",
    'Fifties':  "COUNT(DISTINCT CASE WHEN (SELECT SUM(R.Runs_scored) FROM DELIVERY_OUTCOME_RUNS R JOIN DELIVERY D2 ON (R.Match_ID=D2.Match_ID AND R.Innings_no=D2.Innings_no AND R.Over_no=D2.Over_no AND R.Delivery_no=D2.Delivery_no) WHERE D2.Match_ID=DELIVERY.Match_ID AND D2.Striker=PLAYERS.Player_ID) BETWEEN 50 AND 99 THEN DELIVERY.Match_ID END)",
    'Five_wicket_hauls': "COUNT(DISTINCT CASE WHEN (SELECT COUNT(*) FROM DELIVERY_OUTCOME_WICKETS W JOIN DELIVERY D3 ON (W.Match_ID=D3.Match_ID AND W.Innings_no=D3.Innings_no AND W.Over_no=D3.Over_no AND W.Delivery_no=D3.Delivery_no) WHERE D3.Match_ID=DELIVERY.Match_ID AND D3.Bowler=PLAYERS.Player_ID AND W.Out_batter IS NOT NULL) >= 5 THEN DELIVERY.Match_ID END)",
}

TABLE_MAP = {
    'Player':     'PLAYERS',
    'Team':       'TEAMS',
    'Matches':    'MATCHES',
    'Tournament': 'TOURNAMENTS',
}

SITUATIONAL_JOINS = [
    "JOIN DELIVERY ON (PLAYERS.Player_ID = DELIVERY.Striker OR PLAYERS.Player_ID = DELIVERY.Bowler)",
    "LEFT JOIN DELIVERY_OUTCOME_RUNS    ON (DELIVERY.Match_ID=DELIVERY_OUTCOME_RUNS.Match_ID    AND DELIVERY.Innings_no=DELIVERY_OUTCOME_RUNS.Innings_no    AND DELIVERY.Over_no=DELIVERY_OUTCOME_RUNS.Over_no    AND DELIVERY.Delivery_no=DELIVERY_OUTCOME_RUNS.Delivery_no)",
    "LEFT JOIN DELIVERY_OUTCOME_WICKETS ON (DELIVERY.Match_ID=DELIVERY_OUTCOME_WICKETS.Match_ID AND DELIVERY.Innings_no=DELIVERY_OUTCOME_WICKETS.Innings_no AND DELIVERY.Over_no=DELIVERY_OUTCOME_WICKETS.Over_no AND DELIVERY.Delivery_no=DELIVERY_OUTCOME_WICKETS.Delivery_no)",
    "LEFT JOIN DELIVERY_OUTCOME_EXTRAS  ON (DELIVERY.Match_ID=DELIVERY_OUTCOME_EXTRAS.Match_ID  AND DELIVERY.Innings_no=DELIVERY_OUTCOME_EXTRAS.Innings_no  AND DELIVERY.Over_no=DELIVERY_OUTCOME_EXTRAS.Over_no  AND DELIVERY.Delivery_no=DELIVERY_OUTCOME_EXTRAS.Delivery_no)",
    "JOIN MATCHES ON DELIVERY.Match_ID = MATCHES.Match_ID",
]


def coerce(val: Any) -> Any:
    """Convert string numbers to Python int/float for correct SQLite type comparison."""
    if not isinstance(val, str):
        return val
    try:
        f = float(val)
        return int(f) if f == int(f) else f
    except (ValueError, TypeError):
        return val


# ─── Models ───────────────────────────────────────────────────────────────────

class FilterItem(BaseModel):
    table: str
    field: str
    op: str                      # =, !=, >, <, >=, <=, LIKE, NOT LIKE, BETWEEN
    value: Any
    valueTo: Optional[Any] = None
    connector: str = "AND"       # "AND" | "OR"  (ignored on first filter)
    negate: bool = False         # wraps condition in NOT(...)


class QueryPayload(BaseModel):
    tables: List[str]
    fields: List[Dict[str, str]]
    filters: List[FilterItem]
    sort: List[Dict[str, str]]
    pagination: Dict[str, int]
    aggregate: bool = False


class ComparePayload(BaseModel):
    player_ids: List[str]
    venue: Optional[str] = None
    result: Optional[str] = None


# ─── Clause builder ────────────────────────────────────────────────────────────

SAFE_OPS = {'=', '!=', '>', '<', '>=', '<=', 'LIKE', 'NOT LIKE', 'BETWEEN'}


def _wrap(frag: str, negate: bool) -> str:
    """Optionally wrap a SQL fragment in NOT(...)."""
    return f"NOT ({frag})" if negate else frag


def build_clause(conditions: list) -> tuple[str, list]:
    """
    Build a SQL boolean clause from a list of:
        (connector: str, negate: bool, fragment: str, params: list)
    connector is ignored for the first condition.
    Returns (sql_string, flat_params_list).
    """
    if not conditions:
        return "", []
    sql_parts = []
    all_params = []
    for i, (connector, negate, frag, params) in enumerate(conditions):
        wrapped = _wrap(frag, negate)
        if i == 0:
            sql_parts.append(wrapped)
        else:
            conn = connector.upper() if connector.upper() in ("AND", "OR") else "AND"
            sql_parts.append(f"{conn} {wrapped}")
        all_params.extend(params)
    return " ".join(sql_parts), all_params


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/query")
async def situational_query(payload: QueryPayload):
    """
    Situational analytics engine with full AND / OR / NOT boolean logic.
    - aggregate=False → career stats from PLAYERS table (fast lookup)
    - aggregate=True  → recalculate everything from raw DELIVERY data (situational)
    Metric filters (Runs, SR, Economy…) go into HAVING; context filters into WHERE.
    Supports LIKE with % wildcards, NOT negation, and OR connectors between filters.
    """
    start = time.time()
    try:
        select_clauses = []
        where_conditions  = []   # list of (connector, negate, fragment, params)
        having_conditions = []

        def make_frag_params(tbl, col, op, val, val_to=None, aggregate=False):
            """Return (fragment, params) for a single filter condition."""
            if op not in SAFE_OPS:
                raise HTTPException(status_code=400, detail=f"Unsafe operator: {op}")

            if op == 'BETWEEN':
                v2 = coerce(val_to) if val_to is not None else val
                if aggregate and col in METRIC_EXPRESSIONS:
                    expr = METRIC_EXPRESSIONS[col]
                    return f"{expr} BETWEEN ? AND ?", [coerce(val), v2]
                return f"{tbl}.{col} BETWEEN ? AND ?", [coerce(val), v2]

            val = coerce(val)

            if aggregate:
                if col in METRIC_EXPRESSIONS:
                    return f"{METRIC_EXPRESSIONS[col]} {op} ?", [val]
                if tbl == 'MATCHES' and col == 'Winner_team':
                    return (f"MATCHES.Winner_team IN "
                            f"(SELECT Team_ID FROM TEAMS WHERE Team_name {op} ?)"), [val]
                if tbl == 'TEAMS':
                    return (f"(MATCHES.Team1_ID IN (SELECT Team_ID FROM TEAMS WHERE Team_name {op} ?) "
                            f"OR MATCHES.Team2_ID IN (SELECT Team_ID FROM TEAMS WHERE Team_name {op} ?))"), [val, val]
                return f"{tbl}.{col} {op} ?", [val]
            else:
                # non-aggregate: direct PLAYERS filter or subquery for external tables
                if tbl == 'PLAYERS':
                    return f"PLAYERS.{col} {op} ?", [val]
                mw = (f"TEAMS.Team_name {op} ?" if col == 'Winner_team'
                      else f"{tbl}.{col} {op} ?")
                sub = (f"PLAYERS.Player_ID IN ("
                       f"SELECT DISTINCT Striker FROM DELIVERY "
                       f"JOIN MATCHES ON DELIVERY.Match_ID=MATCHES.Match_ID "
                       f"LEFT JOIN TEAMS ON MATCHES.Winner_team=TEAMS.Team_ID "
                       f"WHERE {mw} "
                       f"UNION "
                       f"SELECT DISTINCT Bowler FROM DELIVERY "
                       f"JOIN MATCHES ON DELIVERY.Match_ID=MATCHES.Match_ID "
                       f"LEFT JOIN TEAMS ON MATCHES.Winner_team=TEAMS.Team_ID "
                       f"WHERE {mw})")
                return sub, [val, val]

        if payload.aggregate:
            for f in payload.fields:
                fk = f['field']
                select_clauses.append(
                    f"{METRIC_EXPRESSIONS[fk]} AS {fk}" if fk in METRIC_EXPRESSIONS
                    else f"PLAYERS.{fk}"
                )
            base_from = f"FROM PLAYERS {' '.join(SITUATIONAL_JOINS)}"

            for f in payload.filters:
                tbl = TABLE_MAP.get(f.table, f.table)
                frag, params = make_frag_params(
                    tbl, f.field, f.op, f.value, f.valueTo, aggregate=True
                )
                # Metric expressions → HAVING; everything else → WHERE
                if f.field in METRIC_EXPRESSIONS and f.op != 'LIKE' and f.op != 'NOT LIKE':
                    having_conditions.append((f.connector, f.negate, frag, params))
                else:
                    where_conditions.append((f.connector, f.negate, frag, params))
        else:
            select_clauses = [f"PLAYERS.{f['field']}" for f in payload.fields]
            base_from = "FROM PLAYERS"
            for f in payload.filters:
                tbl = TABLE_MAP.get(f.table, f.table)
                frag, params = make_frag_params(
                    tbl, f.field, f.op, f.value, f.valueTo, aggregate=False
                )
                where_conditions.append((f.connector, f.negate, frag, params))

        if not select_clauses:
            select_clauses = ["PLAYERS.Player_name"]

        where_sql,  where_params  = build_clause(where_conditions)
        having_sql, having_params = build_clause(having_conditions)

        query = f"SELECT {', '.join(select_clauses)} {base_from}"
        if where_sql:  query += f" WHERE {where_sql}"
        if payload.aggregate: query += " GROUP BY PLAYERS.Player_ID"
        if having_sql: query += f" HAVING {having_sql}"
        if payload.sort:
            query += " ORDER BY " + ", ".join(f"{s['field']} {s['dir']}" for s in payload.sort)

        params = tuple(where_params + having_params)
        limit  = payload.pagination.get('limit', 50)
        offset = (payload.pagination.get('page', 1) - 1) * limit
        paged  = f"{query} LIMIT {limit} OFFSET {offset}"

        conn = get_conn()
        try:
            rows  = [dict(r) for r in conn.execute(paged, params).fetchall()]
            total = conn.execute(f"SELECT COUNT(*) FROM ({query})", params).fetchone()[0]
        finally:
            conn.close()

        return {
            "rows": rows, "total": total,
            "columns": list(rows[0].keys()) if rows else [],
            "query_time_ms": int((time.time() - start) * 1000),
        }
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/values")
async def get_filter_values(payload: Dict[str, Any]):
    """Return distinct values for a field to populate filter dropdowns."""
    table_key = payload.get('table')
    field_key  = payload.get('field')
    db_table   = TABLE_MAP.get(table_key, table_key)

    is_winner = (table_key == 'Matches' and field_key == 'Winner_team')
    select    = "TEAMS.Team_name" if is_winner else field_key
    joins     = ["JOIN TEAMS ON MATCHES.Winner_team = TEAMS.Team_ID"] if is_winner else []

    query  = f"SELECT DISTINCT {select} FROM {db_table} {' '.join(joins)}"
    params, where_parts = [], []

    for f in (payload.get('filters') or []):
        f_tbl = TABLE_MAP.get(f['table'], f['table'])
        f_col = f['field']
        if f_tbl != db_table or f_col in METRIC_EXPRESSIONS:
            continue
        where_parts.append(f"{f_col} {f['op']} ?")
        params.append(f['value'])

    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    query += " ORDER BY 1 LIMIT 200"

    try:
        conn = get_conn()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return {"values": [r[0] for r in rows if r[0] is not None]}
    except Exception:
        return {"values": []}


@router.get("/leaderboard")
def get_leaderboard(
    metric: str = Query("Runs_scored", description="Career stat column to rank by"),
    limit:  int = Query(10, ge=1, le=100),
    dir:    str = Query("DESC"),
):
    """Top-N players by any career metric (uses pre-calculated PLAYERS table)."""
    allowed = {
        "Runs_scored", "Innings_batted", "Batting_average", "Batting_strike_rate",
        "Hundreds", "Fifties", "Wickets_taken", "Economy",
        "Bowling_average", "Bowling_strike_rate", "Five_wicket_hauls",
        "Fours", "Sixes", "Balls_faced", "Matches_played",
    }
    if metric not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Choose from: {sorted(allowed)}")
    sort_dir = "DESC" if dir.upper() == "DESC" else "ASC"

    rows = query_all(
        f"""
        SELECT Player_ID, Player_name, {metric}
        FROM PLAYERS
        WHERE {metric} IS NOT NULL
        ORDER BY {metric} {sort_dir}
        LIMIT ?
        """,
        (limit,),
    )
    return {"metric": metric, "direction": sort_dir, "leaderboard": rows}


@router.post("/compare")
async def compare_players(payload: ComparePayload):
    """
    Side-by-side situational comparison of 2-4 players.
    Optionally filter by venue and/or result_type.
    Returns key metrics for each player under those conditions.
    """
    if not (2 <= len(payload.player_ids) <= 4):
        raise HTTPException(status_code=400, detail="Provide between 2 and 4 player IDs")

    where_extra, extra_params = [], []
    if payload.venue:
        where_extra.append("MATCHES.Venue LIKE ?")
        extra_params.append(f"%{payload.venue}%")
    if payload.result:
        where_extra.append("MATCHES.Result_type = ?")
        extra_params.append(payload.result)

    extra_where = (" AND " + " AND ".join(where_extra)) if where_extra else ""

    results = []
    for pid in payload.player_ids:
        player = query_one("SELECT Player_name FROM PLAYERS WHERE Player_ID = ?", (pid,))
        if not player:
            raise HTTPException(status_code=404, detail=f"Player '{pid}' not found")

        conn = get_conn()
        try:
            row = conn.execute(
                f"""
                SELECT
                  {METRIC_EXPRESSIONS['Innings_batted']}      AS Innings_batted,
                  {METRIC_EXPRESSIONS['Runs_scored']}         AS Runs_scored,
                  {METRIC_EXPRESSIONS['Batting_strike_rate']} AS Batting_strike_rate,
                  {METRIC_EXPRESSIONS['Batting_average']}     AS Batting_average,
                  {METRIC_EXPRESSIONS['Fours']}               AS Fours,
                  {METRIC_EXPRESSIONS['Sixes']}               AS Sixes,
                  {METRIC_EXPRESSIONS['Wickets_taken']}       AS Wickets_taken,
                  {METRIC_EXPRESSIONS['Economy']}             AS Economy,
                  {METRIC_EXPRESSIONS['Bowling_average']}     AS Bowling_average,
                  {METRIC_EXPRESSIONS['Hundreds']}            AS Hundreds,
                  {METRIC_EXPRESSIONS['Fifties']}             AS Fifties
                FROM PLAYERS
                JOIN DELIVERY ON (PLAYERS.Player_ID=DELIVERY.Striker OR PLAYERS.Player_ID=DELIVERY.Bowler)
                LEFT JOIN DELIVERY_OUTCOME_RUNS    ON (DELIVERY.Match_ID=DELIVERY_OUTCOME_RUNS.Match_ID    AND DELIVERY.Innings_no=DELIVERY_OUTCOME_RUNS.Innings_no    AND DELIVERY.Over_no=DELIVERY_OUTCOME_RUNS.Over_no    AND DELIVERY.Delivery_no=DELIVERY_OUTCOME_RUNS.Delivery_no)
                LEFT JOIN DELIVERY_OUTCOME_WICKETS ON (DELIVERY.Match_ID=DELIVERY_OUTCOME_WICKETS.Match_ID AND DELIVERY.Innings_no=DELIVERY_OUTCOME_WICKETS.Innings_no AND DELIVERY.Over_no=DELIVERY_OUTCOME_WICKETS.Over_no AND DELIVERY.Delivery_no=DELIVERY_OUTCOME_WICKETS.Delivery_no)
                LEFT JOIN DELIVERY_OUTCOME_EXTRAS  ON (DELIVERY.Match_ID=DELIVERY_OUTCOME_EXTRAS.Match_ID  AND DELIVERY.Innings_no=DELIVERY_OUTCOME_EXTRAS.Innings_no  AND DELIVERY.Over_no=DELIVERY_OUTCOME_EXTRAS.Over_no  AND DELIVERY.Delivery_no=DELIVERY_OUTCOME_EXTRAS.Delivery_no)
                JOIN MATCHES ON DELIVERY.Match_ID=MATCHES.Match_ID
                WHERE PLAYERS.Player_ID = ? {extra_where}
                GROUP BY PLAYERS.Player_ID
                """,
                tuple([pid] + extra_params),
            ).fetchone()
        finally:
            conn.close()

        stats = dict(row) if row else {}
        results.append({"player_id": pid, "player_name": player["Player_name"], "stats": stats})

    return {
        "context": {"venue": payload.venue, "result": payload.result},
        "players": results,
    }
