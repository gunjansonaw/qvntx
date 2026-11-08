import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtCalendarDay, fmtDayMonth, fmtGWh, fmtMW, fmtShare } from '../lib/format.js'
import {
  activeDatum,
  AXIS_PROPS,
  CHART_MARGIN,
  COLORS,
  CURSOR_BAND,
  gwFormatter,
  niceScale,
  TooltipCard,
  Y_AXIS_PROPS,
} from './chartKit.jsx'

const dayTick = (iso, index) =>
  index === 0 || iso.endsWith('-01') ? fmtDayMonth(`${iso}T12:00:00Z`) : String(Number(iso.slice(8, 10)))

/**
 * Per delivery day: firm wind (counted on) + extra cover (bought on top) = the forecast,
 * with the wind actually delivered overlaid to show how the plan would have fared.
 * Energy in MWh; axis shows GWh.
 */
export default function ProcurementChart({ days, height = 300 }) {
  const data = days.map((d) => ({
    ...d,
    firm: d.firmEnergyMwh,
    extra: d.extraCoverMwh,
    actual: d.actualEnergyMwh,
  }))
  const y = niceScale(
    days.flatMap((d) => [d.forecastEnergyMwh, d.actualEnergyMwh]),
    { includeZero: true },
  )
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={CHART_MARGIN} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis dataKey="day" tickFormatter={dayTick} interval={2} {...AXIS_PROPS} />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step)} {...Y_AXIS_PROPS} />
        <Tooltip content={PlanTooltip} cursor={CURSOR_BAND} isAnimationActive={false} />
        <Bar dataKey="firm" stackId="plan" fill={COLORS.firm} stroke="var(--surface)" strokeWidth={1} maxBarSize={24} isAnimationActive={false} />
        <Bar
          dataKey="extra"
          stackId="plan"
          fill={COLORS.forecast}
          stroke="var(--surface)"
          strokeWidth={1}
          radius={[4, 4, 0, 0]}
          maxBarSize={24}
          isAnimationActive={false}
        />
        <Line
          dataKey="actual"
          stroke={COLORS.actual}
          strokeWidth={2}
          dot={{ r: 3.5, fill: COLORS.actual, stroke: 'var(--surface)', strokeWidth: 2 }}
          activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function PlanTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  return (
    <TooltipCard
      title={`Delivery ${fmtCalendarDay(d.day)}`}
      rows={[
        { label: 'Forecast at decision', value: fmtGWh(d.forecastEnergyMwh) },
        { label: 'Firm wind (count on)', value: fmtGWh(d.firmEnergyMwh), color: COLORS.firm, kind: 'rect' },
        { label: 'Extra cover (buy)', value: fmtGWh(d.extraCoverMwh), color: COLORS.forecast, kind: 'rect' },
        { label: 'Actually delivered', value: fmtGWh(d.actualEnergyMwh), color: COLORS.actual },
        { label: 'Peak extra capacity', value: fmtMW(d.peakExtraCoverMw) },
      ]}
      note={d.coveredShare == null ? undefined : `Plan held in ${fmtShare(d.coveredShare)} of this day's periods`}
    />
  )
}
