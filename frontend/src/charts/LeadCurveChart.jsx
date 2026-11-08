import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtHours, fmtMW, fmtShare, fmtSignedMW } from '../lib/format.js'
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

const LEAD_TICKS = [0, 6, 12, 18, 24, 30, 36, 42, 48]

/**
 * MAE vs forecast lead time (0-48 h). The shaded band marks the lead times the
 * selected decision policy actually uses, so the trader sees where they sit.
 */
export default function LeadCurveChart({ points, leadRange, height = 280 }) {
  const y = niceScale(points.map((p) => p.mae), { target: 4 })
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ ...CHART_MARGIN, top: 22 }}>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis
          dataKey="leadHours"
          type="number"
          domain={[0, 48]}
          ticks={LEAD_TICKS}
          tickFormatter={(h) => `${h}h`}
          {...AXIS_PROPS}
        />
        <YAxis domain={y.domain} ticks={y.ticks} tickFormatter={gwFormatter(y.step)} {...Y_AXIS_PROPS} />
        <Tooltip content={LeadTooltip} cursor={CURSOR_LINE} isAnimationActive={false} />
        {leadRange && (
          <ReferenceArea
            x1={leadRange[0]}
            x2={Math.min(leadRange[1], 48)}
            fill={COLORS.forecast}
            fillOpacity={0.1}
            stroke="none"
            label={{ value: 'Your decision lead times', position: 'insideTop', fill: 'var(--text-2)', fontSize: 11, dy: -18 }}
          />
        )}
        <Line
          dataKey="mae"
          name="MAE"
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

function LeadTooltip(props) {
  const d = activeDatum(props)
  if (!d) return null
  return (
    <TooltipCard
      title={`Forecast made ≥ ${fmtHours(d.leadHours)} ahead`}
      rows={[
        { label: 'Mean absolute error', value: fmtMW(d.mae), color: COLORS.primary },
        { label: 'RMSE', value: fmtMW(d.rmse) },
        { label: 'Bias', value: fmtSignedMW(d.bias) },
      ]}
      note={d.coverage < 1 ? `Forecasts exist for ${fmtShare(d.coverage)} of periods at this lead` : undefined}
    />
  )
}
