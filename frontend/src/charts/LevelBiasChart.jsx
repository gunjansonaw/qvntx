import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtInt, fmtMW, fmtSignedMW, gwTick } from '../lib/format.js'
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

const LOW_SAMPLE = 30

/** Mean error (bias) per forecast-level bucket: is the forecast worse when it is windy? */
export default function LevelBiasChart({ levels, height = 280 }) {
  const data = levels.map((lv) => ({
    ...lv,
    label: `${gwTick(lv.lower)}–${gwTick(lv.upper)}`,
    over: lv.bias > 0 ? lv.bias : null,
    under: lv.bias < 0 ? lv.bias : null,
  }))
  const y = niceScale(levels.map((lv) => lv.bias), { includeZero: true })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={CHART_MARGIN}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis dataKey="label" {...AXIS_PROPS} />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step, { signed: true })} {...Y_AXIS_PROPS} />
        <Tooltip content={LevelTooltip} cursor={CURSOR_BAND} isAnimationActive={false} />
        <ReferenceLine y={0} stroke="var(--axis-strong)" />
        <Bar dataKey="over" stackId="b" fill={COLORS.over} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
        <Bar dataKey="under" stackId="b" fill={COLORS.under} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function LevelTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  return (
    <TooltipCard
      title={`Forecast ${d.label} GW`}
      rows={[
        { label: 'Mean error (bias)', value: fmtSignedMW(d.bias), color: d.bias > 0 ? COLORS.over : COLORS.under, kind: 'rect' },
        { label: 'Mean absolute error', value: fmtMW(d.mae) },
        { label: 'Settlement periods', value: fmtInt(d.matched) },
      ]}
      note={d.matched < LOW_SAMPLE ? 'Small sample - treat with caution' : undefined}
    />
  )
}
