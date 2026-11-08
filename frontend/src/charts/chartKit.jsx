/**
 * Shared chart conventions so every chart reads as one system:
 * recessive hairline grid/axes, 2px lines, colours via CSS custom properties
 * (so light/dark themes swap in one place), and one tooltip design.
 */
import { fmtDayMonth, fmtTime, UK_TZ } from '../lib/format.js'

export const COLORS = {
  actual: 'var(--series-actual)',
  forecast: 'var(--series-forecast)',
  firm: 'var(--series-firm)', // wind the desk can count on (procurement plan)
  over: 'var(--div-over)', // over-forecast -> shortfall
  under: 'var(--div-under)', // under-forecast -> surplus
  primary: 'var(--series-actual)',
  grid: 'var(--grid)',
  axis: 'var(--axis)',
}

export const CHART_MARGIN = { top: 8, right: 12, bottom: 4, left: 0 }

export const AXIS_PROPS = {
  stroke: 'var(--axis)',
  tick: { fill: 'var(--text-muted)', fontSize: 12 },
  tickLine: false,
  axisLine: { stroke: 'var(--axis)' },
}

export const Y_AXIS_PROPS = { ...AXIS_PROPS, axisLine: false, width: 44 }

export const CURSOR_LINE = { stroke: 'var(--text-muted)', strokeWidth: 1 }
export const CURSOR_BAND = { fill: 'var(--hover-wash)' }

const NICE_STEPS = [1, 2, 2.5, 5, 10]
const MINUS = '−'

/**
 * Round axis scale ("nice numbers"): domain and ticks on multiples of 1/2/2.5/5 × 10^k,
 * so axes read 0 / 5 / 10 / 15 GW instead of 0 / 5.5 / 11 / 16.5.
 */
export function niceScale(values, { target = 5, includeZero = false } = {}) {
  const finite = values.filter(Number.isFinite)
  let min = finite.length ? Math.min(...finite) : 0
  let max = finite.length ? Math.max(...finite) : 1
  if (includeZero) {
    min = Math.min(min, 0)
    max = Math.max(max, 0)
  }
  if (min === max) max = min + 1
  const rough = (max - min) / target
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = NICE_STEPS.map((m) => m * magnitude).find((s) => s >= rough)
  const lo = Math.floor(min / step) * step
  const hi = Math.ceil(max / step) * step
  const ticks = []
  for (let v = lo; v <= hi + step / 1e6; v += step) ticks.push(Math.round(v * 1e6) / 1e6)
  return { domain: [lo, hi], ticks, step }
}

const decimalsFor = (step) => {
  const text = String(Math.round(step * 1e6) / 1e6)
  return text.includes('.') ? text.split('.')[1].length : 0
}

/** MW -> GW tick formatter with just enough decimals for the scale's step. */
export function gwFormatter(step, { signed = false } = {}) {
  const decimals = decimalsFor(step / 1000)
  return (mw) => {
    const text = (Math.abs(mw) / 1000).toFixed(decimals)
    if (!signed || mw === 0) return mw < 0 ? `${MINUS}${text}` : text
    return `${mw > 0 ? '+' : MINUS}${text}`
  }
}

const ukHour = new Intl.DateTimeFormat('en-GB', { timeZone: UK_TZ, hour: 'numeric', minute: 'numeric', hourCycle: 'h23' })

/**
 * Time-axis ticks for half-hourly data: UK midnights for multi-day spans,
 * every 3/6 hours when zoomed in. Thinned to at most ~`maxTicks` labels.
 */
export function timeTicks(points, maxTicks = 9) {
  if (!points.length) return { ticks: [], format: fmtDayMonth }
  const spanDays = (points[points.length - 1].ts - points[0].ts) / 86_400_000
  const stepHours = spanDays <= 1.1 ? 3 : spanDays <= 3.1 ? 6 : 24
  const candidates = points.filter((p) => {
    const [h, m] = ukHour.format(p.ts).split(':').map(Number)
    return m === 0 && h % stepHours === 0
  })
  const thin = Math.max(1, Math.ceil(candidates.length / maxTicks))
  const ticks = candidates.filter((_, i) => i % thin === 0).map((p) => p.ts)
  const format =
    stepHours === 24
      ? fmtDayMonth
      : (ts) => (ukHour.format(ts) === '00:00' ? fmtDayMonth(ts) : fmtTime(ts))
  return { ticks, format }
}

/**
 * Tooltip body shared by every chart. Values lead (strong), labels follow;
 * series are keyed with a short line/swatch rather than coloured text.
 */
export function TooltipCard({ title, rows, note }) {
  return (
    <div className="tooltip" role="status">
      {title && <div className="tooltip__title">{title}</div>}
      <dl className="tooltip__rows">
        {rows
          .filter((row) => row && row.value !== undefined)
          .map((row) => (
            <div className="tooltip__row" key={row.label}>
              <dt>
                {row.color && <span className={`key key--${row.kind ?? 'line'}`} style={{ '--key': row.color }} />}
                {row.label}
              </dt>
              <dd>{row.value}</dd>
            </div>
          ))}
      </dl>
      {note && <div className="tooltip__note">{note}</div>}
    </div>
  )
}

/** Recharts passes {active, payload}; this unwraps the hovered datum. */
export const activeDatum = ({ active, payload }) => (active && payload?.length ? payload[0].payload : null)
