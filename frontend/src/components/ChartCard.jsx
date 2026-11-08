import { useId, useState } from 'react'
import DataTable from './DataTable.jsx'

/**
 * Card wrapper for every chart: title, plain-language subtitle, legend, and a
 * "Table" toggle that renders the same data as an accessible table.
 * While a refetch is in flight the previous chart stays visible, dimmed.
 */
export default function ChartCard({ title, subtitle, legend, table, loading, error, empty, height = 300, children, className = '' }) {
  const [showTable, setShowTable] = useState(false)
  const headingId = useId()

  let body
  if (error) {
    body = <StateMessage height={height} tone="error">{error.message ?? String(error)}</StateMessage>
  } else if (empty) {
    body = <StateMessage height={height}>{loading ? 'Loading data…' : 'No data for this selection.'}</StateMessage>
  } else if (showTable && table) {
    body = <DataTable {...table} maxHeight={height + 40} />
  } else {
    body = children
  }

  return (
    <section className={`card ${className}`} aria-labelledby={headingId}>
      <header className="card__header">
        <div>
          <h2 className="card__title" id={headingId}>{title}</h2>
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
        </div>
        {table && !empty && !error && (
          <button
            type="button"
            className="ghost-button"
            aria-pressed={showTable}
            onClick={() => setShowTable((v) => !v)}
          >
            {showTable ? 'Chart' : 'Table'}
          </button>
        )}
      </header>
      {legend && !showTable && <Legend items={legend} />}
      <div className={`card__body${loading && !empty ? ' is-refreshing' : ''}`}>{body}</div>
    </section>
  )
}

function Legend({ items }) {
  return (
    <ul className="legend">
      {items.map((item) => (
        <li key={item.label}>
          <span className={`key key--${item.kind ?? 'line'}`} style={{ '--key': item.color }} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  )
}

function StateMessage({ children, height, tone }) {
  return (
    <div className={`state-message${tone ? ` state-message--${tone}` : ''}`} style={{ minHeight: height }}>
      {children}
    </div>
  )
}
