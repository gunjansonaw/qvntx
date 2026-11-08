import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtMW, fmtShare, fmtSignedMW, gateToMinutes, minutesToGate } from '../lib/format.js'
import {
  activeDatum,
  AXIS_PROPS,
  CHART_MARGIN,
  COLORS,
  CURSOR_LINE,
  gwFormatter,
  niceScale,
  TooltipCard,
  Y_AXIS_PROPS,
} from './chartKit.jsx'

const HOUR_TICKS = [0, 3, 6, 9, 12, 15, 18, 21, 24].map((h) => h * 60)

/**
 * MAE as a function of the decision time on D-1. The line steps down each time a
 * new forecast run is published - showing what waiting for a later run is worth.
 */
export default function GateSweepChart({ points, presets, currentGate, height = 280 }) {
  const data = points.map((p) => ({ ...p, minutes: gateToMinutes(p.gate) }))
  const presetGates = new Set(presets.map((p) => p.gate))
  // Not zero-based on purpose: the story is the step changes between runs.
  const y = niceScale(points.map((p) => p.mae), { target: 4 })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ ...CHART_MARGIN, top: 22 }}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis
          dataKey="minutes"
          type="number"
          domain={[0, 24 * 60]}
          ticks={HOUR_TICKS}
          tickFormatter={(m) => minutesToGate(m % (24 * 60))}
          {...AXIS_PROPS}
        />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step)} {...Y_AXIS_PROPS} />
        <Tooltip content={GateTooltip} cursor={CURSOR_LINE} isAnimationActive={false} />
        {presets.map((preset, i) => (
          <ReferenceLine
            key={preset.key}
            x={gateToMinutes(preset.gate)}
            stroke="var(--axis-strong)"
            label={{
              value: `${preset.key.toUpperCase()} ${preset.gate}`,
              position: i % 2 === 0 ? 'insideTopRight' : 'insideTopLeft',
              fill: 'var(--text-2)',
              fontSize: 11,
              dy: -18,
            }}
          />
        ))}
        {currentGate && !presetGates.has(currentGate) && (
          <ReferenceLine
            x={gateToMinutes(currentGate)}
            stroke={COLORS.forecast}
            label={{ value: `Your gate ${currentGate}`, position: 'insideTopLeft', fill: 'var(--text-2)', fontSize: 11, dy: -18 }}
          />
        )}
        <Line
          dataKey="mae"
          name="MAE"
          type="stepAfter"
          stroke={COLORS.primary}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

function GateTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  return (
    <TooltipCard
      title={`Decide at ${d.gate} UK on D-1`}
      rows={[
        { label: 'Mean absolute error', value: fmtMW(d.mae), color: COLORS.primary },
        { label: 'RMSE', value: fmtMW(d.rmse) },
        { label: 'Bias', value: fmtSignedMW(d.bias) },
        { label: 'Forecast run used', value: d.typicalRun ?? '–' },
      ]}
      note={d.coverage < 1 ? `Run covers only ${fmtShare(d.coverage)} of delivery-day periods` : undefined}
    />
  )
}
