import { useMemo } from 'react'
import { Area, Brush, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDateTime, fmtDayMonth, fmtHours, fmtMW, fmtSignedMW } from '../lib/format.js'
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
 * Main trading-desk chart: actual outturn vs the forecast available at decision
 * time, with the empirical P10-P90 outturn band. The brush below zooms; its range
 * is controlled by the parent so other views (error chart, day table) stay in sync.
 */
export default function ForecastVsActualChart({ data, range, onRangeChange, height = 380 }) {
  const visible = data.slice(range.startIndex, range.endIndex + 1)
  const { ticks, format } = timeTicks(visible)
  const y = useMemo(
    () => niceScale(data.flatMap((d) => [d.actual, d.forecast, d.p90]), { includeZero: true }),
    [data],
  )

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
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step)} {...Y_AXIS_PROPS} />
        <Tooltip content={SeriesTooltip} cursor={CURSOR_LINE} isAnimationActive={false} />
        <Area
          dataKey="band"
          name="P10–P90 outturn band"
          stroke="none"
          fill={COLORS.forecast}
          fillOpacity={0.14}
          isAnimationActive={false}
          activeDot={false}
        />
        <Line
          dataKey="forecast"
          name="Forecast at decision"
          stroke={COLORS.forecast}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
          isAnimationActive={false}
        />
        <Line
          dataKey="actual"
          name="Actual"
          stroke={COLORS.actual}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
          isAnimationActive={false}
        />
        <Brush
          dataKey="ts"
          height={30}
          travellerWidth={10}
          startIndex={range.startIndex}
          endIndex={range.endIndex}
          onChange={onRangeChange}
          tickFormatter={fmtDayMonth}
          stroke="var(--axis-strong)"
          fill="var(--surface-2)"
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function SeriesTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  const direction = d.error > 0 ? 'wind short of forecast' : d.error < 0 ? 'wind above forecast' : null
  return (
    <TooltipCard
      title={`${fmtDateTime(d.ts)} UK`}
      rows={[
        { label: 'Actual', value: fmtMW(d.actual), color: COLORS.actual },
        { label: 'Forecast', value: fmtMW(d.forecast), color: COLORS.forecast },
        { label: 'Forecast − actual', value: d.error == null ? undefined : fmtSignedMW(d.error) },
        {
          label: 'Likely range (P10–P90)',
          value: d.p10 == null ? undefined : `${fmtMW(d.p10).replace(' MW', '')}–${fmtMW(d.p90)}`,
          color: COLORS.forecast,
          kind: 'wash',
        },
      ]}
      note={
        d.publishTime
          ? `Run published ${fmtDateTime(d.publishTime)} · ${fmtHours(d.leadHours)} ahead${direction ? ` · ${direction}` : ''}`
          : 'No forecast available at decision time'
      }
    />
  )
}
