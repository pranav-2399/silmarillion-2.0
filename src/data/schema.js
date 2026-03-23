// ─── Field Types ───────────────────────────────────────────────────────────────
export const FIELD_TYPES = {
  STRING: 'string',
  NUMBER: 'number',
  BOOLEAN: 'boolean',
  DATE: 'date',
  ENUM: 'enum',
};

// ─── Filter Operators ──────────────────────────────────────────────────────────
export const FILTER_OPS_BY_TYPE = {
  string: ['=', '!=', 'LIKE', 'NOT LIKE'],
  number: ['=', '!=', '>', '<', '>=', '<=', 'BETWEEN'],
  boolean: ['='],
  date: ['=', '>', '<', '>=', '<=', 'BETWEEN'],
  enum: ['=', '!=', 'LIKE', 'NOT LIKE'],
};

// ─── Enum Values ───────────────────────────────────────────────────────────────
export const WICKET_TYPES = [
  'bowled', 'caught', 'lbw', 'run out', 'stumped',
  'hit wicket', 'caught and bowled', 'obstructing the field',
  'retired out', 'timed out', 'retired hurt'
];
export const EXTRAS_TYPES = ['wides', 'noballs', 'byes', 'legbyes', 'penalty'];
export const ELECTED_OPTIONS = ['bat', 'field'];
export const RESULT_OPTIONS = ['Win', 'Tie', 'Abandoned', 'No-result'];
export const MARGIN_TYPES = ['runs', 'wickets'];
export const PLAYER_TYPES = ['Batsman', 'Bowler', 'All-rounder', 'Wicket-keeper'];

// ─── Table Definitions ─────────────────────────────────────────────────────────
export const TABLES = {
  Player: {
    label: 'Player Profile',
    dbTable: 'PLAYERS',
    color: '#6366f1',
    icon: '👤',
    fields: {
      Player_name: { label: 'Player Name', type: 'string', category: 'Identity' },

      // Batting Metrics (Aggregated)
      Innings_batted: { label: 'Innings Batted', type: 'number', aggregation: 'SUM', category: 'Batting' },
      Runs_scored: { label: 'Total Runs', type: 'number', aggregation: 'SUM', category: 'Batting' },
      Balls_faced: { label: 'Balls Faced', type: 'number', aggregation: 'SUM', category: 'Batting' },
      Batting_strike_rate: { label: 'Strike Rate', type: 'number', aggregation: 'AVG', category: 'Batting' },
      Batting_average: { label: 'Batting Average', type: 'number', aggregation: 'AVG', category: 'Batting' },
      Fours: { label: 'Total 4s', type: 'number', aggregation: 'SUM', category: 'Batting' },
      Sixes: { label: 'Total 6s', type: 'number', aggregation: 'SUM', category: 'Batting' },
      Hundreds: { label: 'Centuries (100s)', type: 'number', aggregation: 'SUM', category: 'Batting' },
      Fifties: { label: 'Fifties (50s)', type: 'number', aggregation: 'SUM', category: 'Batting' },

      // Bowling Metrics (Aggregated)
      Wickets_taken: { label: 'Wickets Taken', type: 'number', aggregation: 'SUM', category: 'Bowling' },
      Balls_bowled: { label: 'Balls Bowled', type: 'number', aggregation: 'SUM', category: 'Bowling' },
      Runs_given: { label: 'Runs Conceded', type: 'number', aggregation: 'SUM', category: 'Bowling' },
      Economy: { label: 'Economy Rate', type: 'number', aggregation: 'AVG', category: 'Bowling' },
      Bowling_average: { label: 'Bowling Average', type: 'number', aggregation: 'AVG', category: 'Bowling' },
      Bowling_strike_rate: { label: 'Bowling Strike Rate', type: 'number', aggregation: 'AVG', category: 'Bowling' },
      Five_wicket_hauls: { label: '5-Wicket Hauls', type: 'number', aggregation: 'SUM', category: 'Bowling' },
    },
  },

  Team: {
    label: 'Teams',
    dbTable: 'TEAMS',
    color: '#10b981',
    icon: '🛡️',
    fields: {
      Team_name: { label: 'Team Name', type: 'string', category: 'Identity' },
      Founded_year: { label: 'Founded In', type: 'number', category: 'History' },
    },
  },

  Matches: {
    label: 'Match Context',
    dbTable: 'MATCHES',
    color: '#ef4444',
    icon: '📅',
    fields: {
      Match_name: { label: 'Match Matchup', type: 'string', category: 'General' },
      Date: { label: 'Match Date', type: 'date', category: 'General' },
      Venue: { label: 'Venue (Ground)', type: 'string', category: 'Conditions' },
      Result_type: { label: 'Result Status', type: 'enum', values: RESULT_OPTIONS, category: 'Outcome' },
      Winner_team: { label: 'Winning Team', type: 'string', category: 'Outcome' },
      Win_margin: { label: 'Winning Margin', type: 'number', category: 'Outcome' },
      Win_margin_type: { label: 'Margin Type', type: 'enum', values: MARGIN_TYPES, category: 'Outcome' },
    },
  },

  Tournament: {
    label: 'Tournaments',
    dbTable: 'TOURNAMENTS',
    color: '#f59e0b',
    icon: '🏆',
    fields: {
      Tournament_Name: { label: 'Tournament', type: 'string', category: 'Identity' },
    },
  },

  Performance: {
    label: 'Innings Stats',
    dbTable: 'DELIVERY',
    color: '#8b5cf6',
    icon: '📈',
    fields: {
      Innings_no: { label: 'Innings Number', type: 'number', category: 'Context' },
      Runs_scored: { label: 'Individual Score', type: 'number', category: 'Batting' },
      Wicket_type: { label: 'Dismissal Mode', type: 'enum', values: WICKET_TYPES, category: 'Outcome' },
    },
  },
};

// ─── FK Join Graph ─────────────────────────────────────────────────────────────
export const JOIN_PATHS = [
  { from: 'Matches', fromField: 'Tournament_ID', to: 'Tournament', toField: 'Tournament_ID' },
  { from: 'Matches', fromField: 'Team1_ID', to: 'Team', toField: 'Team_ID' },
  { from: 'Matches', fromField: 'Team2_ID', to: 'Team', toField: 'Team_ID' },
  { from: 'Matches', fromField: 'Winner_team', to: 'Team', toField: 'Team_ID' },
  { from: 'Performance', fromField: 'Match_ID', to: 'Matches', toField: 'Match_ID' },
  { from: 'Performance', fromField: 'Striker', to: 'Player', toField: 'Player_ID' },
  { from: 'Performance', fromField: 'Bowler', to: 'Player', toField: 'Player_ID' },
];

export const TABLE_LIST = Object.keys(TABLES);
