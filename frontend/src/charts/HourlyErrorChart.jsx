import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtInt, fmtMW, fmtSignedMW } from '../lib/format.js'
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

const pad = (h) => String(h).padStart(2, '0')

/** Mean absolute error by UK hour of day - when in the day is the forecast least reliable? */
export default function HourlyErrorChart({ hours, height = 280 }) {
  const y = niceScale(hours.map((h) => h.mae), { includeZero: true })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={hours} margin={CHART_MARGIN} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis dataKey="hour" tickFormatter={pad} interval={2} {...AXIS_PROPS} />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step)} {...Y_AXIS_PROPS} />
        <Tooltip content={HourTooltip} cursor={CURSOR_BAND} isAnimationActive={false} />
        <Bar dataKey="mae" fill={COLORS.primary} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function HourTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  return (
    <TooltipCard
      title={`${pad(d.hour)}:00–${pad(d.hour)}:59 UK`}
      rows={[
        { label: 'Mean absolute error', value: fmtMW(d.mae), color: COLORS.primary, kind: 'rect' },
        { label: 'Bias', value: fmtSignedMW(d.bias) },
        { label: 'Settlement periods', value: fmtInt(d.matched) },
      ]}
    />
  )
}
