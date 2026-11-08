import { fmtCalendarDay } from '../lib/format.js'

/**
 * One filter row that scopes every chart below it:
 *   1. decision basis - which forecast counts as "the forecast at decision time"
 *   2. delivery-day range
 */
export default function FilterBar({ policy, onPolicyChange, range, onRangeChange, meta }) {
  const presets = meta?.presets ?? []
  const delivery = meta?.deliveryDays
  const choices = [
    ...presets.map((p) => ({ id: p.key, label: p.label, detail: `Gate ${p.gate} D-1` })),
    { id: 'custom', label: 'Custom gate', detail: 'Any time on D-1' },
    { id: 'lead', label: 'Fixed lead time', detail: 'Hours before delivery' },
  ]

  const choose = (id) => {
    const preset = presets.find((p) => p.key === id)
    if (preset) onPolicyChange({ ...policy, choice: id, mode: 'dayahead', gate: preset.gate })
    else if (id === 'custom') onPolicyChange({ ...policy, choice: 'custom', mode: 'dayahead' })
    else onPolicyChange({ ...policy, choice: 'lead', mode: 'lead' })
  }

  const lastWeekStart = delivery ? shiftDay(delivery.lastDay, -6) : null

  return (
    <section className="filters" aria-label="Filters">
      <div className="filters__group">
        <span className="filters__label" id="basis-label">Decision basis</span>
        <div className="segmented" role="radiogroup" aria-labelledby="basis-label">
          {choices.map((c) => (
            <button
              key={c.id}
              type="button"
              role="radio"
              aria-checked={policy.choice === c.id}
              className="segmented__option"
              onClick={() => choose(c.id)}
            >
              <span className="segmented__title">{c.label}</span>
              <span className="segmented__detail">{c.detail}</span>
            </button>
          ))}
        </div>
        {policy.choice === 'custom' && (
          <label className="inline-field">
            Gate time on D-1 (UK)
            <input
              type="time"
              step={600}
              value={policy.gate}
              onChange={(e) => e.target.value && onPolicyChange({ ...policy, gate: e.target.value })}
            />
          </label>
        )}
        {policy.choice === 'lead' && (
          <label className="inline-field inline-field--slider">
            Minimum lead time <strong>{policy.lead} h</strong>
            <input
              type="range"
              min={0}
              max={meta?.maxLeadHours ?? 48}
              step={1}
              value={policy.lead}
              onChange={(e) => onPolicyChange({ ...policy, lead: Number(e.target.value) })}
            />
          </label>
        )}
      </div>

      {delivery && (
        <div className="filters__group">
          <span className="filters__label">Delivery days</span>
          <div className="range-presets">
            <button
              type="button"
              className="chip"
              aria-pressed={range.start === delivery.firstDay && range.end === delivery.lastDay}
              onClick={() => onRangeChange({ start: delivery.firstDay, end: delivery.lastDay })}
            >
              All January decisions
            </button>
            <button
              type="button"
              className="chip"
              aria-pressed={range.start === lastWeekStart && range.end === delivery.lastDay}
              onClick={() => onRangeChange({ start: lastWeekStart, end: delivery.lastDay })}
            >
              Last 7 days
            </button>
          </div>
          <div className="date-range">
            <input
              type="date"
              aria-label="First delivery day"
              min={delivery.firstDay}
              max={range.end}
              value={range.start}
              onChange={(e) => e.target.value && onRangeChange({ ...range, start: e.target.value })}
            />
            <span aria-hidden="true">–</span>
            <input
              type="date"
              aria-label="Last delivery day"
              min={range.start}
              max={delivery.lastDay}
              value={range.end}
              onChange={(e) => e.target.value && onRangeChange({ ...range, end: e.target.value })}
            />
          </div>
          <span className="filters__hint">
            {fmtCalendarDay(range.start)} – {fmtCalendarDay(range.end)}
          </span>
        </div>
      )}
    </section>
  )
}

function shiftDay(isoDate, days) {
  const d = new Date(`${isoDate}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}
