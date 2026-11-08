import { useState } from 'react'
import ChartCard from '../components/ChartCard.jsx'
import StatTile from '../components/StatTile.jsx'
import ProcurementChart from '../charts/ProcurementChart.jsx'
import { COLORS } from '../charts/chartKit.jsx'
import { useApi } from '../hooks/useApi.js'
import { apiUrl } from '../lib/api.js'
import { fmtCalendarDay, fmtGWh, fmtMW, fmtShare } from '../lib/format.js'

const CONFIDENCE_LEVELS = [0.8, 0.9, 0.95]

/**
 * Answers the desk's core question on the wind side: how much wind can we count on,
 * and how much extra must we buy beyond the raw forecast, at a chosen confidence?
 * Total to buy = demand - firm wind (demand is outside this pilot's Elexon-only data).
 */
export default function ProcurementPanel({ query }) {
  const [confidence, setConfidence] = useState(0.9)
  const plan = useApi(apiUrl('/procurement', { ...query, confidence }))
  const total = plan.data?.total
  const days = plan.data?.days ?? []
  const pct = `${Math.round(confidence * 100)}%`

  return (
    <section className="section" aria-labelledby="procurement-title">
      <div className="section__head">
        <div>
          <h2 id="procurement-title" className="section__title">
            Procurement plan — how much wind to count on
          </h2>
          <p className="section__subtitle">
            Power to buy for each half-hour = <strong>your demand − firm wind</strong>. Firm wind is the volume delivered
            in {pct} of periods at that forecast level. Demand is outside this pilot&apos;s data (Elexon wind only), so
            apply your own demand forecast.
          </p>
        </div>
        <div className="confidence-control">
          <span className="filters__label" id="confidence-label">
            Confidence
          </span>
          <div className="segmented" role="radiogroup" aria-labelledby="confidence-label">
            {CONFIDENCE_LEVELS.map((level) => (
              <button
                key={level}
                type="button"
                role="radio"
                aria-checked={confidence === level}
                className="segmented__option segmented__option--compact"
                onClick={() => setConfidence(level)}
              >
                <span className="segmented__title">{Math.round(level * 100)}%</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className={`stats${plan.loading && total ? ' is-refreshing' : ''}`}>
        <StatTile
          emphasis
          label={`Firm wind at ${pct} confidence`}
          value={total ? fmtGWh(total.firmEnergyMwh) : '–'}
          detail={total && `Of ${fmtGWh(total.forecastEnergyMwh)} forecast at decision time`}
        />
        <StatTile
          label="Extra cover to buy"
          value={total ? fmtGWh(total.extraCoverMwh) : '–'}
          detail="On top of buying against the raw forecast"
        />
        <StatTile
          label="Peak extra capacity"
          value={total ? fmtMW(total.peakExtraCoverMw) : '–'}
          detail="Largest half-hourly gap to have cover for"
        />
        <StatTile
          label="Plan held (back-test)"
          value={total ? fmtShare(total.coveredShare) : '–'}
          detail={`Periods where actual wind ≥ firm wind · target ${pct}`}
        />
      </div>

      <ChartCard
        title="Firm wind and extra cover by delivery day"
        subtitle="GWh per day. Bar height = forecast at decision time, split into wind to count on and volume to cover elsewhere; dots = wind actually delivered."
        legend={[
          { label: 'Firm wind (count on)', color: COLORS.firm, kind: 'rect' },
          { label: 'Extra cover (buy)', color: COLORS.forecast, kind: 'rect' },
          { label: 'Actually delivered', color: COLORS.actual },
        ]}
        loading={plan.loading}
        error={plan.error}
        empty={!days.length}
        height={300}
        table={{
          caption: 'Procurement plan by delivery day',
          columns: [
            { key: 'day', label: 'Delivery day', render: (d) => fmtCalendarDay(d.day) },
            { key: 'forecast', label: 'Forecast', align: 'right', render: (d) => fmtGWh(d.forecastEnergyMwh) },
            { key: 'firm', label: 'Firm wind', align: 'right', render: (d) => fmtGWh(d.firmEnergyMwh) },
            { key: 'extra', label: 'Extra cover', align: 'right', render: (d) => fmtGWh(d.extraCoverMwh) },
            { key: 'peak', label: 'Peak extra', align: 'right', render: (d) => fmtMW(d.peakExtraCoverMw) },
            { key: 'actual', label: 'Actual', align: 'right', render: (d) => fmtGWh(d.actualEnergyMwh) },
            { key: 'held', label: 'Plan held', align: 'right', render: (d) => fmtShare(d.coveredShare) },
          ],
          rows: days,
          rowKey: (d) => d.day,
        }}
      >
        <ProcurementChart days={days} />
      </ChartCard>
    </section>
  )
}
