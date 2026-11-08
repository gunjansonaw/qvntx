import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtCalendarDay, fmtDayMonth, fmtGWh, fmtMW, fmtSignedMW } from '../lib/format.js'
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

/** "2 Jan" on the first day and month boundaries, plain day numbers otherwise. */
const dayTick = (iso, index) =>
  index === 0 || iso.endsWith('-01') ? fmtDayMonth(`${iso}T12:00:00Z`) : String(Number(iso.slice(8, 10)))

/** Mean error per delivery day: is over-forecasting persistent or driven by a few days? */
export default function DailyBiasChart({ days, height = 280 }) {
  const data = days.map((d) => ({
    ...d,
    over: d.bias > 0 ? d.bias : null,
    under: d.bias < 0 ? d.bias : null,
  }))
  const y = niceScale(days.map((d) => d.bias), { includeZero: true })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={CHART_MARGIN} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis dataKey="day" tickFormatter={dayTick} interval={2} {...AXIS_PROPS} />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step, { signed: true })} {...Y_AXIS_PROPS} />
        <Tooltip content={DayTooltip} cursor={CURSOR_BAND} isAnimationActive={false} />
        <ReferenceLine y={0} stroke="var(--axis-strong)" />
        <Bar dataKey="over" stackId="d" fill={COLORS.over} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
        <Bar dataKey="under" stackId="d" fill={COLORS.under} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function DayTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  return (
    <TooltipCard
      title={`Delivery ${fmtCalendarDay(d.day)}`}
      rows={[
        { label: 'Mean error (bias)', value: fmtSignedMW(d.bias), color: d.bias > 0 ? COLORS.over : COLORS.under, kind: 'rect' },
        { label: 'Mean absolute error', value: fmtMW(d.mae) },
        { label: 'Forecast energy', value: fmtGWh(d.forecastEnergyMwh) },
        { label: 'Actual energy', value: fmtGWh(d.actualEnergyMwh) },
      ]}
    />
  )
}
