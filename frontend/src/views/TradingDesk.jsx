import { useMemo, useRef, useState } from 'react'
import ChartCard from '../components/ChartCard.jsx'
import StatTile from '../components/StatTile.jsx'
import ErrorTimelineChart from '../charts/ErrorTimelineChart.jsx'
import ForecastVsActualChart from '../charts/ForecastVsActualChart.jsx'
import ProcurementPanel from './ProcurementPanel.jsx'
import { COLORS } from '../charts/chartKit.jsx'
import { useApi } from '../hooks/useApi.js'
import { apiUrl } from '../lib/api.js'
import {
  fmtCalendarDay,
  fmtDateTime,
  fmtGWh,
  fmtHours,
  fmtMW,
  fmtPct,
  fmtRunRelative,
  fmtShare,
  fmtSignedMW,
  ukDayKey,
} from '../lib/format.js'

/**
 * View A - what the forecast said at decision time vs what the wind actually did,
 * plus the procurement consequence (shortfall energy) per delivery day.
 */
export default function TradingDesk({ query }) {
  const series = useApi(apiUrl('/series', query))
  const evaluation = useApi(apiUrl('/evaluation', query))
  const chartRef = useRef(null)

  const data = useMemo(() => toChartData(series.data?.points ?? []), [series.data])
  const summary = series.data?.summary
  const days = evaluation.data?.byDay ?? []

  // Brush zoom, remembered per delivery window so switching decision basis keeps the zoom.
  const windowKey = series.data ? `${series.data.window.firstDay}/${series.data.window.lastDay}/${data.length}` : null
  const [zoom, setZoom] = useState({ key: null, startIndex: 0, endIndex: 0 })
  const range =
    zoom.key === windowKey ? zoom : { key: windowKey, startIndex: 0, endIndex: Math.max(0, data.length - 1) }
  const visible = data.slice(range.startIndex, range.endIndex + 1)
  const isZoomed = range.startIndex > 0 || range.endIndex < data.length - 1

  const setRange = ({ startIndex, endIndex }) => setZoom({ key: windowKey, startIndex, endIndex })
  const zoomToDay = (day) => {
    const first = data.findIndex((p) => p.dayKey === day)
    const last = data.findLastIndex((p) => p.dayKey === day)
    if (first < 0) return
    setRange({ startIndex: first, endIndex: last })
    chartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const runLabel = typicalRunLabel(days, series.data?.policy)
  const error = series.error ?? evaluation.error

  return (
    <div className="view">
      <DecisionContext policy={series.data?.policy} summary={summary} runLabel={runLabel} />

      <div className="stats">
        <StatTile
          emphasis
          label="Wind shortfall vs forecast"
          value={summary ? fmtGWh(summary.shortfallEnergyMwh) : '–'}
          detail={summary && `Wind came in below forecast in ${fmtShare(summary.overForecastShare)} of periods`}
        />
        <StatTile
          label="Wind forecast at decision"
          value={summary ? fmtGWh(summary.forecastEnergyMwh) : '–'}
          detail={summary && `Actual delivered ${fmtGWh(summary.actualEnergyMwh)}`}
        />
        <StatTile
          label="Typical miss (MAE)"
          value={summary ? fmtMW(summary.mae) : '–'}
          detail={summary && `${fmtPct(summary.wape)} of actual output (WAPE)`}
        />
        <StatTile
          label="Average bias"
          value={summary ? fmtSignedMW(summary.bias) : '–'}
          detail="Forecast − actual, per settlement period"
        />
      </div>

      <div ref={chartRef} className="scroll-anchor">
        <ChartCard
          title="Wind generation — forecast at decision time vs actual"
          subtitle={
            <>
              Half-hourly, GW, UK time. Drag the handles below the chart to zoom
              {isZoomed && (
                <>
                  {' · '}
                  <button type="button" className="link-button" onClick={() => setRange({ startIndex: 0, endIndex: data.length - 1 })}>
                    Reset zoom
                  </button>
                </>
              )}
            </>
          }
          legend={[
            { label: 'Actual (FUELHH)', color: COLORS.actual },
            { label: 'Forecast at decision (WINDFOR)', color: COLORS.forecast },
            { label: 'Likely range, P10–P90', color: COLORS.forecast, kind: 'wash' },
          ]}
          loading={series.loading}
          error={error}
          empty={!data.length}
          height={380}
          table={{
            caption: 'Half-hourly actual and forecast wind generation',
            columns: [
              { key: 'ts', label: 'Period start (UK)', render: (r) => fmtDateTime(r.ts) },
              { key: 'actual', label: 'Actual', align: 'right', render: (r) => fmtMW(r.actual) },
              { key: 'forecast', label: 'Forecast', align: 'right', render: (r) => fmtMW(r.forecast) },
              { key: 'error', label: 'Forecast − actual', align: 'right', render: (r) => fmtSignedMW(r.error) },
              { key: 'band', label: 'P10–P90', align: 'right', render: (r) => (r.p10 == null ? '–' : `${fmtMW(r.p10)} – ${fmtMW(r.p90)}`) },
              { key: 'lead', label: 'Lead', align: 'right', render: (r) => fmtHours(r.leadHours) },
            ],
            rows: visible,
            rowKey: (r) => r.ts,
          }}
        >
          <ForecastVsActualChart data={data} range={range} onRangeChange={setRange} />
        </ChartCard>
      </div>

      <ChartCard
        title="Forecast error over time"
        subtitle="Forecast − actual, GW. Above zero the forecast promised more wind than arrived: energy the desk had to buy elsewhere."
        legend={[
          { label: 'Over-forecast (shortfall)', color: COLORS.over, kind: 'wash' },
          { label: 'Under-forecast (surplus)', color: COLORS.under, kind: 'wash' },
        ]}
        loading={series.loading}
        error={error}
        empty={!data.length}
        height={200}
      >
        <ErrorTimelineChart data={data} visible={visible} />
      </ChartCard>

      <ProcurementPanel query={query} />

      <ChartCard
        title="Delivery-day summary"
        subtitle="One row per delivery day. Select a row to zoom the chart to that day."
        loading={evaluation.loading}
        error={evaluation.error}
        empty={!days.length}
        height={240}
        className="card--table"
      >
        <DayTable days={days} onSelect={zoomToDay} />
      </ChartCard>
    </div>
  )
}

function DecisionContext({ policy, summary, runLabel }) {
  if (!policy) return <div className="context-strip" aria-hidden="true" />
  const lead =
    summary?.minLeadHours != null ? `${fmtHours(summary.minLeadHours)} – ${fmtHours(summary.maxLeadHours)}` : '–'
  return (
    <div className="context-strip">
      <div>
        <span className="context-strip__label">Decision basis</span>
        <span className="context-strip__value">{policy.description}</span>
      </div>
      <div>
        <span className="context-strip__label">Forecast run used</span>
        <span className="context-strip__value">{runLabel}</span>
      </div>
      <div>
        <span className="context-strip__label">Lead time</span>
        <span className="context-strip__value">{lead}</span>
      </div>
    </div>
  )
}

function DayTable({ days, onSelect }) {
  return (
    <div className="table-wrap" style={{ maxHeight: 420 }}>
      <table className="data-table">
        <caption className="visually-hidden">Delivery-day forecast accuracy and shortfall</caption>
        <thead>
          <tr>
            <th scope="col">Delivery day</th>
            <th scope="col">Run used</th>
            <th scope="col" className="num">Forecast</th>
            <th scope="col" className="num">Actual</th>
            <th scope="col" className="num">Shortfall</th>
            <th scope="col" className="num">Surplus</th>
            <th scope="col" className="num">MAE</th>
          </tr>
        </thead>
        <tbody>
          {days.map((d) => (
            <tr
              key={d.day}
              className="is-clickable"
              tabIndex={0}
              onClick={() => onSelect(d.day)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(d.day)
                }
              }}
            >
              <td>{fmtCalendarDay(d.day)}</td>
              <td>{runsLabel(d)}</td>
              <td className="num">{fmtGWh(d.forecastEnergyMwh)}</td>
              <td className="num">{fmtGWh(d.actualEnergyMwh)}</td>
              <td className="num">
                <Bar value={d.shortfallEnergyMwh} max={maxOf(days, 'shortfallEnergyMwh')} tone="over" />
                {fmtGWh(d.shortfallEnergyMwh)}
              </td>
              <td className="num">
                <Bar value={d.surplusEnergyMwh} max={maxOf(days, 'surplusEnergyMwh')} tone="under" />
                {fmtGWh(d.surplusEnergyMwh)}
              </td>
              <td className="num">{fmtMW(d.mae)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Inline magnitude bar inside a table cell (decorative; the number carries the value). */
function Bar({ value, max, tone }) {
  // Below ~0.05 GWh the value prints as 0.0, so draw nothing rather than a sliver.
  const width = max > 0 && value >= 50 ? Math.max(2, (value / max) * 48) : 0
  return <span className={`cell-bar cell-bar--${tone}`} style={{ width }} aria-hidden="true" />
}

const maxOf = (rows, key) => rows.reduce((m, r) => Math.max(m, r[key] ?? 0), 0)

function runsLabel(day) {
  const runs = day.runPublishTimes
  if (!runs.length) return '–'
  if (runs.length === 1) return fmtRunRelative(runs[0], day.day)
  return `${runs.length} runs`
}

function typicalRunLabel(days, policy) {
  if (!policy) return '–'
  if (policy.mode === 'lead') return 'Varies by period (latest run before the lead cut-off)'
  const counts = new Map()
  for (const d of days) {
    if (d.runPublishTimes.length !== 1) continue
    const label = fmtRunRelative(d.runPublishTimes[0], d.day)
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  const [best] = [...counts.entries()].sort((a, b) => b[1] - a[1])
  return best ? `NESO run published ${best[0].replace(' D-', ' UK on D-')}` : '–'
}

function toChartData(points) {
  return points.map((p) => {
    const ts = Date.parse(p.time)
    return {
      ts,
      dayKey: ukDayKey(ts),
      actual: p.actual,
      forecast: p.forecast,
      error: p.error,
      over: p.error == null ? null : Math.max(p.error, 0),
      under: p.error == null ? null : Math.min(p.error, 0),
      band: p.p10 == null ? null : [p.p10, p.p90],
      p10: p.p10,
      p50: p.p50,
      p90: p.p90,
      publishTime: p.publishTime,
      leadHours: p.leadHours,
    }
  })
}
