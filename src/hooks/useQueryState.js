import { useState, useCallback, useRef } from 'react';
import { executeQuery } from '../utils/api';
import { TABLES } from '../data/schema';

const DEFAULT_PAGINATION = { page: 1, limit: 100 };

export function useQueryState() {
  const [tables, setTablesRaw] = useState(['Player']);
  const [filters, setFilters] = useState([]);   // [{ id, table, field, op, value, valueTo }]
  const [sort, setSort] = useState([]);   // [{ id, table, field, dir }]
  const [pagination, setPagination] = useState(DEFAULT_PAGINATION);
  const [aggregate, setAggregate] = useState(false); // Career (false) vs Match-Specific (true)
  const [hiddenFields, setHiddenFields] = useState([]); // [fieldKey, ...]

  // ─── Result state ────────────────────────────────────────────────────────────
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [manualFieldOrder, setManualFieldOrder] = useState([]); // [fieldKey, ...]
  const abortRef = useRef(null);

  // ─── Dynamic Field Prioritization ──────────────────────────────────────────
  const getDerivedFields = useCallback(() => {
    // 1. Determine active categories
    const activeCategories = new Set();
    filters.forEach(f => {
      const fieldDef = TABLES[f.table]?.fields[f.field];
      if (fieldDef?.category) activeCategories.add(fieldDef.category);
    });

    // 2. Start with ALL fields from the Player table
    const playerFields = TABLES.Player.fields;
    let baseFields = Object.keys(playerFields).map(f => ({ table: 'Player', field: f }));

    // 3. Prioritize by Category
    const sorted = [...baseFields].sort((a, b) => {
      const defA = TABLES[a.table]?.fields[a.field];
      const defB = TABLES[b.table]?.fields[b.field];
      const catA = defA?.category || '';
      const catB = defB?.category || '';

      if (catA === 'Identity' && catB !== 'Identity') return -1;
      if (catB === 'Identity' && catA !== 'Identity') return 1;

      const activeA = activeCategories.has(catA);
      const activeB = activeCategories.has(catB);
      if (activeA && !activeB) return -1;
      if (!activeA && activeB) return 1;

      return 0;
    });

    // 4. Manual Order
    let reordered = sorted;
    if (manualFieldOrder.length > 0) {
      reordered = [...sorted].sort((a, b) => {
        const idxA = manualFieldOrder.indexOf(a.field);
        const idxB = manualFieldOrder.indexOf(b.field);
        if (idxA === -1 && idxB === -1) return 0;
        if (idxA === -1) return 1;
        if (idxB === -1) return -1;
        return idxA - idxB;
      });
    }

    // 5. Apply Visibility
    return reordered.filter(f => !hiddenFields.includes(f.field));
  }, [filters, manualFieldOrder, hiddenFields]);

  const hideField = useCallback((fieldKey) => {
    setHiddenFields(prev => [...prev, fieldKey]);
  }, []);

  const showField = useCallback((fieldKey) => {
    setHiddenFields(prev => prev.filter(f => f !== fieldKey));
  }, []);

  const moveResultColumn = useCallback((fromIdx, toIdx) => {
    setResult(prev => {
      if (!prev) return prev;
      const nextCols = [...prev.columns];
      const [item] = nextCols.splice(fromIdx, 1);
      nextCols.splice(toIdx, 0, item);
      setManualFieldOrder(nextCols);
      return { ...prev, columns: nextCols };
    });
  }, []);

  // ─── Helper functions ───────────────────────────────────────────────────────
  const setTables = useCallback((newTables) => setTablesRaw(newTables), []);
  const addFilter = useCallback((table, field) => {
    const id = `filter_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    setFilters(prev => [...prev, {
      id, table, field,
      op: '=', value: '', valueTo: '',
      connector: 'AND',  // AND | OR  (ignored for first filter)
      negate: false,     // wraps condition in NOT(...)
    }]);
  }, []);
  const updateFilter = useCallback((id, patch) => {
    setFilters(prev => prev.map(f => f.id === id ? { ...f, ...patch } : f));
  }, []);
  const removeFilter = useCallback((id) => setFilters(prev => prev.filter(f => f.id !== id)), []);
  const clearFilters = useCallback(() => setFilters([]), []);

  const setPage = useCallback((page) => setPagination(p => ({ ...p, page })), []);
  const setLimit = useCallback((limit) => setPagination(p => ({ ...p, limit, page: 1 })), []);

  // ─── Execution ──────────────────────────────────────────────────────────────
  const runQuery = useCallback(async () => {
    const finalFields = getDerivedFields();
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setError(null);

    try {
      const data = await executeQuery({
        tables: ['Player'],
        fields: finalFields,
        filters,
        sort: [],
        pagination,
        aggregate
      });
      setResult(data);
    } catch (err) {
      if (err.name !== 'AbortError') setError(err.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  }, [filters, pagination, getDerivedFields, aggregate]);

  const reset = useCallback(() => {
    setTablesRaw(['Player']);
    setFilters([]);
    setSort([]);
    setAggregate(false);
    setHiddenFields([]);
    setManualFieldOrder([]);
    setPagination(DEFAULT_PAGINATION);
    setResult(null);
    setError(null);
  }, []);

  return {
    tables, filters, sort, pagination, aggregate, hiddenFields,
    result, loading, error,
    getDerivedFields, reorderField: moveResultColumn,
    hideField, showField, setHiddenFields,
    setTables, setAggregate,
    addFilter, updateFilter, removeFilter, clearFilters,
    setPage, setLimit,
    runQuery, reset,
  };
}
