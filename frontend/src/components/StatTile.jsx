/** KPI tile: sentence-case label, one value, optional context line. */
export default function StatTile({ label, value, detail, emphasis = false, tone }) {
  return (
    <div className={`stat${emphasis ? ' stat--emphasis' : ''}${tone ? ` stat--${tone}` : ''}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {detail && <div className="stat__detail">{detail}</div>}
    </div>
  )
}
