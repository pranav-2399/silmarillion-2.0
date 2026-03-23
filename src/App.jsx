import TableSelector from './components/TableSelector/TableSelector';
import FieldSelector from './components/FieldSelector/FieldSelector';
import FilterBuilder from './components/FilterBuilder/FilterBuilder';
import SortOptions from './components/SortOptions/SortOptions';
import ResultTable from './components/ResultTable/ResultTable';
import QueryBar from './components/shared/QueryBar';
import { useQueryState } from './hooks/useQueryState';
import { useState } from 'react';

export default function App() {
  const q = useQueryState();
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__titles">
          <h1 className="app-header__title">Silmarillion</h1>
        </div>
        <div className="tabs-container">
          <button
            className={`tab-btn ${!q.aggregate ? 'tab-btn--active' : ''}`}
            onClick={() => { q.setAggregate(false); q.clearFilters(); }}
          >
            📊 Career Stats
          </button>
          <button
            className={`tab-btn ${q.aggregate ? 'tab-btn--active' : ''}`}
            onClick={() => { q.setAggregate(true); q.clearFilters(); }}
          >
            🏏 Match-Specific
          </button>
        </div>
        <div className="app-header__actions">
          <div style={{ display: 'flex', flexDirection: 'row', margin: '1vh 1vw', gap: '1vw' }}>
            <span className="app-header__db-tag">SQLite · Cricket DB</span>
            <button
              className={`action-btn ${showAdvanced ? 'action-btn--active' : ''}`}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? 'Hide' : 'Show'} Advanced Sources
            </button>
          </div>
          <button className="run-btn" onClick={q.runQuery} disabled={q.loading}>
            {q.loading ? 'Running...' : 'Run Analysis'}
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="query-grid">
          <div className="query-grid__main">
            <FilterBuilder
              selectedTables={q.tables}
              filters={q.filters}
              addFilter={q.addFilter}
              updateFilter={q.updateFilter}
              removeFilter={q.removeFilter}
              clearFilters={q.clearFilters}
              aggregate={q.aggregate}
            />
          </div>
        </div>

        <ResultTable
          result={q.result}
          loading={q.loading}
          error={q.error}
          pagination={q.pagination}
          setPage={q.setPage}
          setLimit={q.setLimit}
          onReorder={q.reorderField}
          onHide={q.hideField}
          onShow={q.showField}
          hiddenFields={q.hiddenFields}
        />

        {/* 6. Sticky query bar */}
        <QueryBar
          tables={q.tables}
          fields={q.getDerivedFields()}
          filters={q.filters}
          sort={q.sort}
          pagination={q.pagination}
          loading={q.loading}
          onRun={q.runQuery}
          onReset={q.reset}
        />
      </main>
    </div>
  );
}
