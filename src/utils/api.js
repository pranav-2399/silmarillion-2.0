/**
 * api.js — Cricket DB API service layer
 *
 * All functions construct a structured JSON payload and call the Python backend.
 * Replace BASE_URL with your actual server address.
 *
 * Backend expects POST /api/query with the payload described below.
 * Backend expects GET  /api/tables/:table/values?field=X for distinct values.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── Core fetch wrapper ────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err.message || `HTTP ${res.status}`);
  }

  return res.json();
}

// ─── Build Query Payload ───────────────────────────────────────────────────────
/**
 * Constructs the structured JSON payload sent to the backend.
 *
 * Payload shape:
 * {
 *   tables:  string[]          // selected table names (maps to DB table names)
 *   fields:  { table, field }[]  // columns to SELECT
 *   filters: {
 *     table, field, op, value, valueTo?  // valueTo only for BETWEEN
 *   }[]
 *   sort:    { table, field, dir }[]
 *   pagination: { page, limit }
 * }
 *
 * The backend is responsible for:
 *   - Resolving JOIN paths from the FK graph
 *   - Building parameterised SQL (NEVER string-interpolate user values)
 *   - Returning { rows: [...], total: number, columns: [...] }
 */
export function buildQueryPayload({ tables = [], fields = [], filters = [], sort = [], pagination = {}, aggregate = false }) {
  return {
    tables,
    fields: fields.map(f => ({ table: f.table, field: f.field })),
    filters: filters.map(f => ({
      table: f.table,
      field: f.field,
      op: f.op,
      value: f.value,
      connector: f.connector || 'AND',   // "AND" | "OR"
      negate: f.negate || false,          // NOT wrapper
      ...(f.op === 'BETWEEN' ? { valueTo: f.valueTo } : {}),
    })),
    sort: sort.map(s => ({ table: s.table, field: s.field, dir: s.dir })),
    pagination: {
      page: pagination.page ?? 1,
      limit: pagination.limit ?? 100,
    },
    aggregate
  };
}

// ─── API Methods ───────────────────────────────────────────────────────────────

/**
 * Execute a query against the cricket database.
 * @returns {{ rows: object[], total: number, columns: string[], query_time_ms: number }}
 */
export async function executeQuery(queryState) {
  const payload = buildQueryPayload(queryState);
  return apiFetch('/api/query', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch distinct values for a field, considering current filter context.
 * @returns {{ values: (string|number)[] }}
 */
export async function fetchContextualValues(table, field, filters = []) {
  return apiFetch('/api/values', {
    method: 'POST',
    body: JSON.stringify({ table, field, filters }),
  });
}

/**
 * Fetch distinct values for a field (legacy simplicity).
 */
export async function fetchDistinctValues(table, field) {
  return apiFetch(`/api/tables/${table}/values?field=${encodeURIComponent(field)}`);
}

/**
 * Fetch table metadata from the backend (optional — schema is embedded in frontend).
 * @returns {{ tables: object }}
 */
export async function fetchSchema() {
  return apiFetch('/api/schema');
}

/**
 * Health-check the backend.
 * @returns {{ status: 'ok', db: 'sqlite' }}
 */
export async function ping() {
  return apiFetch('/api/ping');
}

// ─── Export helpers ────────────────────────────────────────────────────────────

/**
 * Convert rows + columns to CSV string for download.
 */
export function rowsToCSV(columns, rows) {
  const header = columns.join(',');
  const lines = rows.map(row =>
    columns.map(col => {
      const v = row[col] ?? '';
      const s = String(v);
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    }).join(',')
  );
  return [header, ...lines].join('\n');
}

export function downloadCSV(columns, rows, filename = 'cricket_query_result.csv') {
  const csv = rowsToCSV(columns, rows);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Export rows to Excel (.xlsx) using the SheetJS CDN build.
 * SheetJS is imported via the xlsx npm package in package.json.
 */
export async function downloadExcel(columns, rows, filename = 'cricket_query_result.xlsx') {
  const XLSX = await import('xlsx');
  const ws = XLSX.utils.json_to_sheet(rows.map(row =>
    Object.fromEntries(columns.map(c => [c, row[c] ?? '']))
  ));
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Results');
  XLSX.writeFile(wb, filename);
}
