import { TABLES, FILTER_OPS_BY_TYPE } from '../../data/schema';
import { useState, useEffect } from 'react';
import { fetchContextualValues } from '../../utils/api';

// ─── Connector Pill (AND / OR between rows) ───────────────────────────────────
function ConnectorPill({ connector, onToggle }) {
  return (
    <div className="filter-connector">
      <button
        className={`connector-pill connector-pill--${connector.toLowerCase()}`}
        onClick={onToggle}
        title="Click to toggle AND / OR"
      >
        {connector}
      </button>
    </div>
  );
}

// ─── Individual Filter Row ────────────────────────────────────────────────────
function FilterRow({ filter, onUpdate, onRemove, tableDef, allFilters }) {
  const fieldDef = tableDef?.fields[filter.field];
  const type = fieldDef?.type || 'string';
  const ops = FILTER_OPS_BY_TYPE[type] || ['='];

  const [dynamicValues, setDynamicValues] = useState([]);
  const [loadingValues, setLoadingValues] = useState(false);

  // Fetch dynamic options for Winner_team / Venue
  useEffect(() => {
    const shouldFetch = (filter.table === 'Matches' && (filter.field === 'Winner_team' || filter.field === 'Venue'));
    if (!shouldFetch) { setDynamicValues([]); return; }

    let active = true;
    setLoadingValues(true);
    fetchContextualValues(filter.table, filter.field, allFilters.filter(f => f.id !== filter.id))
      .then(res => { if (active) setDynamicValues(res.values || []); })
      .catch(() => { })
      .finally(() => { if (active) setLoadingValues(false); });

    return () => { active = false; };
  }, [filter.table, filter.field, allFilters.length]);

  const isLike = filter.op === 'LIKE' || filter.op === 'NOT LIKE';

  const renderValueInput = () => {
    // 1. Boolean
    if (type === 'boolean') {
      return (
        <select className="filter-input" value={filter.value} onChange={e => onUpdate({ value: e.target.value })}>
          <option value="">— pick —</option>
          <option value="1">True</option>
          <option value="0">False</option>
        </select>
      );
    }
    // 2. Static enum (but allow text input when LIKE is selected)
    if (type === 'enum' && fieldDef?.values && !isLike) {
      return (
        <select className="filter-input" value={filter.value} onChange={e => onUpdate({ value: e.target.value })}>
          <option value="">— pick —</option>
          {fieldDef.values.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      );
    }
    // 3. Dynamic dropdown (but allow free text when LIKE is selected)
    if (dynamicValues.length > 0 && !isLike) {
      return (
        <select className="filter-input" value={filter.value} onChange={e => onUpdate({ value: e.target.value })}>
          <option value="">— select {fieldDef?.label.toLowerCase()} —</option>
          {dynamicValues.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
      );
    }
    // 4. BETWEEN range
    if (filter.op === 'BETWEEN') {
      return (
        <div className="filter-between">
          <input className="filter-input" type={type === 'number' ? 'number' : 'text'} value={filter.value} onChange={e => onUpdate({ value: e.target.value })} placeholder="From" />
          <span className="filter-between__sep">↔</span>
          <input className="filter-input" type={type === 'number' ? 'number' : 'text'} value={filter.valueTo} onChange={e => onUpdate({ valueTo: e.target.value })} placeholder="To" />
        </div>
      );
    }
    // 5. Generic / wildcard text
    return (
      <input
        className="filter-input"
        type={type === 'date' ? 'date' : type === 'number' ? 'number' : 'text'}
        placeholder={
          loadingValues ? 'Loading…'
            : isLike ? 'e.g. %Kohli% or Virat%'
              : type === 'string' ? 'Value or %wildcard%'
                : 'Value'
        }
        value={filter.value}
        onChange={e => onUpdate({ value: e.target.value })}
      />
    );
  };

  return (
    <div className={`filter-row${filter.negate ? ' filter-row--negated' : ''}`}>
      {/* Field label */}
      <div className="filter-row__source">
        <span className="filter-row__table-dot" style={{ background: TABLES[filter.table]?.color || '#888' }} />
        <span className="filter-row__table">{filter.table}</span>
        <span className="filter-row__field">.{fieldDef?.label || filter.field}</span>
      </div>

      {/* NOT toggle */}
      <button
        className={`not-btn${filter.negate ? ' not-btn--active' : ''}`}
        onClick={() => onUpdate({ negate: !filter.negate })}
        title={filter.negate ? 'Remove NOT' : 'Wrap in NOT (negate)'}
      >
        NOT
      </button>

      {/* Operator */}
      <select
        className="filter-input filter-input--op"
        value={filter.op}
        onChange={e => onUpdate({ op: e.target.value, valueTo: '' })}
      >
        {ops.map(op => <option key={op} value={op}>{op}</option>)}
      </select>

      {/* Value */}
      <div className="filter-row__value">
        {renderValueInput()}
      </div>

      {/* Remove */}
      <button className="icon-btn icon-btn--danger" onClick={onRemove} title="Remove filter">✕</button>
    </div>
  );
}

// ─── Filter Categories Helper ─────────────────────────────────────────────────
function getFilterGroups(isSpecific) {
  const groups = [
    { label: '👤 Player Identity', tables: ['Player'], categories: ['Identity'] },
    { label: '🏏 Batting Metrics', tables: ['Player', 'Performance'], categories: ['Batting'] },
    { label: '🎳 Bowling Metrics', tables: ['Player'], categories: ['Bowling'] },
  ];
  if (isSpecific) {
    groups.push({ label: '📅 Match Context (situational)', tables: ['Matches', 'Tournament', 'Team'] });
  }
  return groups;
}

// ─── Add-filter panel ─────────────────────────────────────────────────────────
function AddFilterPanel({ filters, onAdd, aggregate }) {
  const [search, setSearch] = useState('');
  const groups = getFilterGroups(aggregate);

  return (
    <div className="add-filter-container">
      <div className="add-filter-search">
        <input
          className="filter-search-input"
          placeholder="Search attributes (e.g. runs, wickets, venue)..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <div className="add-filter-groups">
        {groups.map(group => {
          const matchingContent = group.tables.map(tableName => {
            const def = TABLES[tableName];
            const fields = Object.entries(def.fields).filter(([key, field]) => {
              if (group.categories && !group.categories.includes(field.category)) return false;
              return field.label.toLowerCase().includes(search.toLowerCase()) ||
                tableName.toLowerCase().includes(search.toLowerCase());
            });
            return { tableName, def, fields };
          }).filter(t => t.fields.length > 0);

          if (matchingContent.length === 0) return null;

          return (
            <div key={group.label} className="filter-group">
              <h4 className="filter-group__title">{group.label}</h4>
              <div className="filter-group__fields">
                {matchingContent.flatMap(({ tableName, fields }) =>
                  fields.map(([fieldKey, fieldDef]) => {
                    const already = filters.filter(f => f.table === tableName && f.field === fieldKey).length;
                    return (
                      <button
                        key={`${tableName}-${fieldKey}`}
                        className="add-filter-chip"
                        onClick={() => onAdd(tableName, fieldKey)}
                      >
                        <span className="add-filter-chip__label">{fieldDef.label}</span>
                        {already > 0 && <span className="add-filter-chip__count">{already}</span>}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function FilterBuilder({
  filters,
  addFilter,
  updateFilter,
  removeFilter,
  clearFilters,
  aggregate
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div className="panel-header__left">
          <span className="panel-icon">⧉</span>
          <h2 className="panel-title">Player Attributes & Filters</h2>
        </div>
        {filters.length > 0 && (
          <div className="panel-header__right">
            <button className="action-btn action-btn--danger" onClick={clearFilters}>
              Clear all
            </button>
          </div>
        )}
      </div>

      <div className="panel-sub">
        {!aggregate
          ? "Browse career leaderboards. Filter by player type or name."
          : "Situation Analysis: Filters applied here will recalculate stats for specific matches."
        }
      </div>

      {filters.length > 0 && (
        <div className="filter-list">
          {filters.map((filter, index) => (
            <div key={filter.id}>
              {/* AND / OR connector pill between rows */}
              {index > 0 && (
                <ConnectorPill
                  connector={filter.connector || 'AND'}
                  onToggle={() =>
                    updateFilter(filter.id, {
                      connector: (filter.connector || 'AND') === 'AND' ? 'OR' : 'AND',
                    })
                  }
                />
              )}
              <FilterRow
                filter={filter}
                tableDef={TABLES[filter.table]}
                onUpdate={patch => updateFilter(filter.id, patch)}
                onRemove={() => removeFilter(filter.id)}
                allFilters={filters}
              />
            </div>
          ))}
        </div>
      )}

      <div className="add-filter-section">
        <AddFilterPanel filters={filters} onAdd={addFilter} aggregate={aggregate} />
      </div>
    </section>
  );
}
