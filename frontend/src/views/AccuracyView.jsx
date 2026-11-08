import ChartCard from '../components/ChartCard.jsx'
import StatTile from '../components/StatTile.jsx'
import DailyBiasChart from '../charts/DailyBiasChart.jsx'
import ErrorHistogram from '../charts/ErrorHistogram.jsx'
import GateSweepChart from '../charts/GateSweepChart.jsx'
import HourlyErrorChart from '../charts/HourlyErrorChart.jsx'
import LeadCurveChart from '../charts/LeadCurveChart.jsx'
import LevelBiasChart from '../charts/LevelBiasChart.jsx'
import { COLORS } from '../charts/chartKit.jsx'
import { useApi } from '../hooks/useApi.js'
import { apiUrl } from '../lib/api.js'
import {
  fmtCalendarDay,
  fmtGWh,
  fmtHours,
  fmtInt,
  fmtMW,
  fmtPct,
  fmtShare,
  fmtSignedMW,
  gwTick,
} from '../lib/format.js'

const MIN_LEVEL_SAMPLE = 30

/**
 * View B - quantitative evaluation of the forecast the desk actually trades on,
 * turned into planning numbers (how much wind to "haircut" and when).
 */
export default function AccuracyView({ query, rangeQuery, policy }) {
  const evaluation = useApi(apiUrl('/evaluation', query))
  const lead = useApi(apiUrl('/lead-curve', rangeQuery))
  const sweep = useApi(apiUrl('/gate-sweep', rangeQuery))

  const ev = evaluation.data
  const s = ev?.summary
  const leadRange = s?.minLeadHours != null ? [s.minLeadHours, s.maxLeadHours] : null

  return (
    <div className="view">
      <div className="stats stats--six">
        <StatTile emphasis label="Mean absolute error" value={s ? fmtMW(s.mae) : '–'} detail={s && `${fmtPct(s.wape)} of actual output (WAPE)`} />
        <StatTile label="Root mean square error" value={s ? fmtMW(s.rmse) : '–'} detail="Penalises large misses" />
        <StatTile label="Bias (mean error)" value={s ? fmtSignedMW(s.bias) : '–'} detail={s && `Over-forecast in ${fmtShare(s.overForecastShare)} of periods`} />
        <StatTile label="90th percentile miss" value={s ? fmtMW(s.p90AbsError) : '–'} detail="9 in 10 periods missed by less" />
        <StatTile label="MAPE" value={s ? fmtPct(s.mape) : '–'} detail="Mean % error per period" />
        <StatTile
          label="Periods evaluated"
          value={s ? fmtInt(s.matched) : '–'}
          detail={s && `${fmtShare(s.coverage)} coverage · lead ${fmtHours(s.minLeadHours)}–${fmtHours(s.maxLeadHours)}`}
        />
      </div>

      <Guidance summary={s} levels={ev?.byForecastLevel} sweep={sweep.data} policy={policy} />

      <div className="grid">
        <ChartCard
          title="Error distribution"
          subtitle="Settlement periods by forecast − actual (GW bins). Mass right of zero = wind under-delivered."
          legend={[
            { label: 'Under-forecast (surplus)', color: COLORS.under, kind: 'rect' },
            { label: 'Over-forecast (shortfall)', color: COLORS.over, kind: 'rect' },
          ]}
          loading={evaluation.loading}
          error={evaluation.error}
          empty={!ev?.histogram?.length}
          height={280}
          table={{
            columns: [
              { key: 'range', label: 'Error range', render: (b) => `${fmtSignedMW(b.lower)} to ${fmtSignedMW(b.upper)}` },
              { key: 'count', label: 'Periods', align: 'right', render: (b) => fmtInt(b.count) },
              { key: 'share', label: 'Share', align: 'right', render: (b) => fmtShare(b.share) },
            ],
            rows: ev?.histogram ?? [],
            rowKey: (b) => b.lower,
          }}
        >
          <ErrorHistogram bins={ev?.histogram ?? []} />
        </ChartCard>

        <ChartCard
          title="Bias by forecast level"
          subtitle="Mean forecast − actual (GW) by forecast size. The windier the forecast, the more it over-states delivery."
          legend={[
            { label: 'Over-forecast', color: COLORS.over, kind: 'rect' },
            { label: 'Under-forecast', color: COLORS.under, kind: 'rect' },
          ]}
          loading={evaluation.loading}
          error={evaluation.error}
          empty={!ev?.byForecastLevel?.length}
          height={280}
          table={{
            columns: [
              { key: 'level', label: 'Forecast level', render: (l) => `${gwTick(l.lower)}–${gwTick(l.upper)} GW` },
              { key: 'bias', label: 'Bias', align: 'right', render: (l) => fmtSignedMW(l.bias) },
              { key: 'mae', label: 'MAE', align: 'right', render: (l) => fmtMW(l.mae) },
              { key: 'matched', label: 'Periods', align: 'right', render: (l) => fmtInt(l.matched) },
            ],
            rows: ev?.byForecastLevel ?? [],
            rowKey: (l) => l.lower,
          }}
        >
          <LevelBiasChart levels={ev?.byForecastLevel ?? []} />
        </ChartCard>

        <ChartCard
          title="Accuracy vs decision time on D-1"
          subtitle="MAE (GW) if the day-ahead decision were taken at each time on the previous day. Steps mark new forecast runs."
          loading={sweep.loading}
          error={sweep.error}
          empty={!sweep.data?.points?.length}
          height={280}
          table={{
            columns: [
              { key: 'gate', label: 'Decision time (UK)' },
              { key: 'typicalRun', label: 'Run used' },
              { key: 'mae', label: 'MAE', align: 'right', render: (p) => fmtMW(p.mae) },
              { key: 'bias', label: 'Bias', align: 'right', render: (p) => fmtSignedMW(p.bias) },
              { key: 'coverage', label: 'Coverage', align: 'right', render: (p) => fmtShare(p.coverage) },
            ],
            rows: sweep.data?.points ?? [],
            rowKey: (p) => p.gate,
          }}
        >
          <GateSweepChart
            points={sweep.data?.points ?? []}
            presets={sweep.data?.presets ?? []}
            currentGate={policy.mode === 'dayahead' ? policy.gate : null}
          />
        </ChartCard>

        <ChartCard
          title="Accuracy vs forecast lead time"
          subtitle="MAE (GW) using the latest forecast made at least N hours ahead. Shaded: lead times your decision basis uses."
          loading={lead.loading}
          error={lead.error}
          empty={!lead.data?.points?.length}
          height={280}
          table={{
            columns: [
              { key: 'leadHours', label: 'Lead time', render: (p) => fmtHours(p.leadHours) },
              { key: 'mae', label: 'MAE', align: 'right', render: (p) => fmtMW(p.mae) },
              { key: 'rmse', label: 'RMSE', align: 'right', render: (p) => fmtMW(p.rmse) },
              { key: 'bias', label: 'Bias', align: 'right', render: (p) => fmtSignedMW(p.bias) },
              { key: 'coverage', label: 'Coverage', align: 'right', render: (p) => fmtShare(p.coverage) },
            ],
            rows: lead.data?.points ?? [],
            rowKey: (p) => p.leadHours,
          }}
        >
          <LeadCurveChart points={lead.data?.points ?? []} leadRange={leadRange} />
        </ChartCard>

        <ChartCard
          title="Error by hour of day"
          subtitle="Mean absolute error (GW) by UK hour of the delivery day."
          loading={evaluation.loading}
          error={evaluation.error}
          empty={!ev?.byHour?.length}
          height={280}
          table={{
            columns: [
              { key: 'hour', label: 'Hour (UK)', render: (h) => `${String(h.hour).padStart(2, '0')}:00` },
              { key: 'mae', label: 'MAE', align: 'right', render: (h) => fmtMW(h.mae) },
              { key: 'bias', label: 'Bias', align: 'right', render: (h) => fmtSignedMW(h.bias) },
            ],
            rows: ev?.byHour ?? [],
            rowKey: (h) => h.hour,
          }}
        >
          <HourlyErrorChart hours={ev?.byHour ?? []} />
        </ChartCard>

        <ChartCard
          title="Bias by delivery day"
          subtitle="Mean forecast − actual (GW) per day. Persistent bars above zero mean systematic over-forecasting."
          legend={[
            { label: 'Over-forecast', color: COLORS.over, kind: 'rect' },
            { label: 'Under-forecast', color: COLORS.under, kind: 'rect' },
          ]}
          loading={evaluation.loading}
          error={evaluation.error}
          empty={!ev?.byDay?.length}
          height={280}
          table={{
            columns: [
              { key: 'day', label: 'Delivery day', render: (d) => fmtCalendarDay(d.day) },
              { key: 'bias', label: 'Bias', align: 'right', render: (d) => fmtSignedMW(d.bias) },
              { key: 'mae', label: 'MAE', align: 'right', render: (d) => fmtMW(d.mae) },
              { key: 'shortfall', label: 'Shortfall', align: 'right', render: (d) => fmtGWh(d.shortfallEnergyMwh) },
            ],
            rows: ev?.byDay ?? [],
            rowKey: (d) => d.day,
          }}
        >
          <DailyBiasChart days={ev?.byDay ?? []} />
        </ChartCard>
      </div>
    </div>
  )
}

/** Plain-language planning guidance derived from the error statistics. */
function Guidance({ summary: s, levels, sweep, policy }) {
  if (!s || s.matched === 0) return null

  const items = [
    {
      title: 'Plan with a wind haircut',
      body: (
        <>
          Actual wind reached at least <strong>forecast − {fmtMW(s.errorP90)}</strong> in 90% of settlement periods.
          Use that as the firm wind volume when sizing day-ahead purchases.
        </>
      ),
    },
    {
      title: 'Expect a systematic over-forecast',
      body: (
        <>
          On average the forecast over-stated delivery by <strong>{fmtSignedMW(s.bias)}</strong>; wind fell short in{' '}
          <strong>{fmtShare(s.overForecastShare)}</strong> of periods, totalling{' '}
          <strong>{fmtGWh(s.shortfallEnergyMwh)}</strong> of energy to source elsewhere.
        </>
      ),
    },
    {
      title: 'Likely range',
      body: (
        <>
          In 80% of periods actual wind landed between <strong>forecast − {fmtMW(s.errorP90)}</strong> and{' '}
          <strong>forecast + {fmtMW(Math.max(0, -s.errorP10))}</strong>.
        </>
      ),
    },
  ]

  const windiest = [...(levels ?? [])].reverse().find((lv) => lv.matched >= MIN_LEVEL_SAMPLE && lv.bias != null)
  if (windiest) {
    items.push({
      title: 'Haircut more on windy days',
      body: (
        <>
          When the forecast was {gwTick(windiest.lower)}–{gwTick(windiest.upper)} GW, wind came in{' '}
          <strong>{fmtMW(windiest.bias)}</strong> below forecast on average ({fmtInt(windiest.matched)} periods).
        </>
      ),
    })
  }

  const gatePoints = Object.fromEntries((sweep?.points ?? []).map((p) => [p.gate, p]))
  const [early, late] = sweep?.presets ?? []
  if (early && late && gatePoints[early.gate] && gatePoints[late.gate]) {
    const delta = gatePoints[late.gate].mae - gatePoints[early.gate].mae
    items.push({
      title: 'Which auction gate?',
      body: (
        <>
          Deciding at the {late.label} gate ({late.gate}, run {gatePoints[late.gate].typicalRun}) instead of{' '}
          {early.label} ({early.gate}, run {gatePoints[early.gate].typicalRun}) changes MAE by{' '}
          <strong>{fmtSignedMW(delta)}</strong>.
        </>
      ),
    })
  }

  return (
    <section className="guidance" aria-labelledby="guidance-title">
      <h2 id="guidance-title" className="guidance__title">
        Planning guidance{' '}
        <span className="guidance__scope">
          {policy.mode === 'lead' ? `forecasts made ≥ ${policy.lead} h ahead` : `decisions at ${policy.gate} UK on D-1`}
        </span>
      </h2>
      <ul className="guidance__list">
        {items.map((item) => (
          <li key={item.title}>
            <span className="guidance__item-title">{item.title}</span>
            <span className="guidance__item-body">{item.body}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
