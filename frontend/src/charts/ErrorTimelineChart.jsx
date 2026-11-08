import { useMemo } from 'react'
import { Area, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDateTime, fmtSignedMW } from '../lib/format.js'
import {
  activeDatum,
  AXIS_PROPS,
  CHART_MARGIN,
  COLORS,
  CURSOR_LINE,
  gwFormatter,
  niceScale,
  timeTicks,
  TooltipCard,
  Y_AXIS_PROPS,
} from './chartKit.jsx'

/**
 * Forecast error over time, split at zero: above the line the forecast promised
 * more wind than arrived (shortfall to buy), below it wind beat the forecast.
 *
 * Receives the *full* series: it shares `syncId` with the main chart, so Recharts
 * applies the main chart's brush zoom here too (and syncs the tooltip).
 * `visible` is only used to place time ticks for the zoomed window.
 */
export default function ErrorTimelineChart({ data, visible, height = 200 }) {
  const { ticks, format } = timeTicks(visible)
  const y = useMemo(() => niceScale(data.map((d) => d.error), { includeZero: true, target: 6 }), [data])
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={CHART_MARGIN} syncId="desk" syncMethod="value">
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis
          dataKey="ts"
          type="number"
          scale="time"
          domain={['dataMin', 'dataMax']}
          ticks={ticks}
          tickFormatter={format}
          {...AXIS_PROPS}
        />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step, { signed: true })} {...Y_AXIS_PROPS} />
        <Tooltip content={ErrorTooltip} cursor={CURSOR_LINE} isAnimationActive={false} />
        <ReferenceLine y={0} stroke="var(--axis-strong)" />
        <Area
          dataKey="over"
          name="Over-forecast"
          type="linear"
          baseValue={0}
          stroke={COLORS.over}
          strokeWidth={1.5}
          fill={COLORS.over}
          fillOpacity={0.18}
          isAnimationActive={false}
          activeDot={false}
        />
        <Area
          dataKey="under"
          name="Under-forecast"
          type="linear"
          baseValue={0}
          stroke={COLORS.under}
          strokeWidth={1.5}
          fill={COLORS.under}
          fillOpacity={0.18}
          isAnimationActive={false}
          activeDot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function ErrorTooltip(props) {
  const d = activeDatum(props)
  if (!d || d.error == null) return null
  const over = d.error > 0
  return (
    <TooltipCard
      title={`${fmtDateTime(d.ts)} UK`}
      rows={[
        {
          label: over ? 'Over-forecast (shortfall)' : 'Under-forecast (surplus)',
          value: fmtSignedMW(d.error),
          color: over ? COLORS.over : COLORS.under,
          kind: 'wash',
        },
      ]}
    />
  )
}
