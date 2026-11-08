import { useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtInt, fmtShare, fmtSignedMW } from '../lib/format.js'
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

/**
 * Distribution of forecast − actual across settlement periods (500 MW bins).
 * Bars sit on a numeric axis at their bin centre, so ticks mark true bin edges (whole GW).
 */
export default function ErrorHistogram({ bins, height = 280 }) {
  const { data, xDomain, xTicks, y } = useMemo(() => {
    const rows = bins.map((b) => ({
      ...b,
      mid: (b.lower + b.upper) / 2,
      under: b.upper <= 0 ? b.count : null,
      over: b.lower >= 0 ? b.count : null,
    }))
    const lo = bins.length ? bins[0].lower : 0
    const hi = bins.length ? bins[bins.length - 1].upper : 1
    const tickStep = hi - lo > 10_000 ? 2000 : 1000
    const ticks = []
    for (let v = Math.ceil(lo / tickStep) * tickStep; v <= hi; v += tickStep) ticks.push(v)
    return { data: rows, xDomain: [lo, hi], xTicks: ticks, y: niceScale(bins.map((b) => b.count), { includeZero: true }) }
  }, [bins])

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={CHART_MARGIN} barCategoryGap={2}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis
          dataKey="mid"
          type="number"
          domain={xDomain}
          ticks={xTicks}
          tickFormatter={gwFormatter(1000, { signed: true })}
          {...AXIS_PROPS}
        />
        <YAxis domain={y.domain} ticks={y.ticks} allowDecimals={false} {...Y_AXIS_PROPS} />
        <Tooltip content={HistogramTooltip} cursor={CURSOR_BAND} isAnimationActive={false} />
        <Bar dataKey="under" stackId="e" fill={COLORS.under} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
        <Bar dataKey="over" stackId="e" fill={COLORS.over} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function HistogramTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  const over = d.lower >= 0
  return (
    <TooltipCard
      title={`Error ${fmtSignedMW(d.lower)} to ${fmtSignedMW(d.upper)}`}
      rows={[
        {
          label: 'Settlement periods',
          value: `${fmtInt(d.count)} (${fmtShare(d.share)})`,
          color: over ? COLORS.over : COLORS.under,
          kind: 'rect',
        },
      ]}
      note={over ? 'Forecast above actual: shortfall to cover' : 'Forecast below actual: surplus wind'}
    />
  )
}
