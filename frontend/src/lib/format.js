/**
 * Formatting helpers. All times are shown in UK local time (Europe/London), which is
 * what GB traders work in; the API returns UTC ISO-8601 strings.
 */

export const UK_TZ = 'Europe/London'
const MINUS = '−' // typographic minus sign
const DASH = '–'

const int = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 })
const oneDp = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

const dayMonth = new Intl.DateTimeFormat('en-GB', { timeZone: UK_TZ, day: 'numeric', month: 'short' })
const weekdayDayMonth = new Intl.DateTimeFormat('en-GB', {
  timeZone: UK_TZ,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
})
const hourMinute = new Intl.DateTimeFormat('en-GB', {
  timeZone: UK_TZ,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})
const isoDay = new Intl.DateTimeFormat('en-CA', { timeZone: UK_TZ, year: 'numeric', month: '2-digit', day: '2-digit' })

const isMissing = (v) => v === null || v === undefined || Number.isNaN(v)

// -- numbers -----------------------------------------------------------------

export const fmtInt = (v) => (isMissing(v) ? DASH : int.format(v))
export const fmtMW = (v) => (isMissing(v) ? DASH : `${int.format(v)} MW`)

/** "+1,234 MW" / "−567 MW" with a real minus sign. */
export function fmtSignedMW(v) {
  if (isMissing(v)) return DASH
  const rounded = Math.round(v)
  const sign = rounded > 0 ? '+' : rounded < 0 ? MINUS : ''
  return `${sign}${int.format(Math.abs(rounded))} MW`
}

/** Energy: MWh in, "1,234 GWh" out (or "12.3 GWh" when small). */
export function fmtGWh(mwh) {
  if (isMissing(mwh)) return DASH
  const gwh = mwh / 1000
  return `${Math.abs(gwh) >= 100 ? int.format(gwh) : oneDp.format(gwh)} GWh`
}

export const fmtPct = (v, digits = 1) => (isMissing(v) ? DASH : `${v.toFixed(digits)}%`)
export const fmtShare = (v) => (isMissing(v) ? DASH : `${Math.round(v * 100)}%`)
export const fmtHours = (h) => (isMissing(h) ? DASH : `${Number.isInteger(h) ? h : h.toFixed(1)} h`)

/** Axis tick: MW -> GW without unit ("15"). */
export const gwTick = (mw) => {
  const gw = mw / 1000
  return Number.isInteger(gw) ? String(gw) : gw.toFixed(1)
}

/** Signed axis tick: MW -> GW ("+2", "−1.5", "0"). */
export const gwSignedTick = (mw) => {
  if (mw === 0) return '0'
  const text = gwTick(Math.abs(mw))
  return `${mw > 0 ? '+' : MINUS}${text}`
}

// -- dates & times -----------------------------------------------------------

const asDate = (value) => (value instanceof Date ? value : new Date(value))

/** "2 Jan" */
export const fmtDayMonth = (value) => dayMonth.format(asDate(value))
/** "00:30" (UK) */
export const fmtTime = (value) => hourMinute.format(asDate(value))
/** "Fri 2 Jan, 00:30" (UK) */
export const fmtDateTime = (value) => `${weekdayDayMonth.format(asDate(value))}, ${fmtTime(value)}`
/** UK calendar day of an instant as YYYY-MM-DD. */
export const ukDayKey = (value) => isoDay.format(asDate(value))

/** Calendar date string "2026-01-02" -> "Fri 2 Jan" (no time-zone shifting). */
export function fmtCalendarDay(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number)
  return weekdayDayMonth.format(new Date(Date.UTC(y, m - 1, d, 12)))
}

/** Forecast run label relative to a delivery day, e.g. "07:30 D-1". */
export function fmtRunRelative(publishIso, deliveryIsoDate) {
  const published = ukDayKey(publishIso)
  const days = Math.round((Date.parse(deliveryIsoDate) - Date.parse(published)) / 86_400_000)
  return `${fmtTime(publishIso)} D-${days}`
}

/** "HH:MM" -> minutes after midnight. */
export const gateToMinutes = (gate) => {
  const [h, m] = gate.split(':').map(Number)
  return h * 60 + m
}

/** minutes after midnight -> "HH:MM". */
export const minutesToGate = (minutes) =>
  `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
