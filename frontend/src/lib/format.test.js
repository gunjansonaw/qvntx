import { describe, expect, it } from 'vitest'
import {
  fmtCalendarDay,
  fmtGWh,
  fmtRunRelative,
  fmtSignedMW,
  fmtTime,
  gateToMinutes,
  gwSignedTick,
  minutesToGate,
  ukDayKey,
} from './format.js'
import { apiUrl, policyParams } from './api.js'

describe('number formatting', () => {
  it('signs MW with a real minus and thousands separators', () => {
    expect(fmtSignedMW(1744.4)).toBe('+1,744 MW')
    expect(fmtSignedMW(-530)).toBe('−530 MW')
    expect(fmtSignedMW(0.2)).toBe('0 MW')
    expect(fmtSignedMW(null)).toBe('–')
  })

  it('formats energy in GWh', () => {
    expect(fmtGWh(8_395_000)).toBe('8,395 GWh')
    expect(fmtGWh(12_340)).toBe('12.3 GWh')
  })

  it('formats signed GW axis ticks', () => {
    expect(gwSignedTick(2000)).toBe('+2')
    expect(gwSignedTick(-1500)).toBe('−1.5')
    expect(gwSignedTick(0)).toBe('0')
  })
})

describe('UK time handling', () => {
  it('uses GMT in winter and BST in summer', () => {
    expect(fmtTime('2026-01-02T00:30:00Z')).toBe('00:30')
    expect(fmtTime('2026-07-02T00:30:00Z')).toBe('01:30')
    expect(ukDayKey('2026-07-01T23:30:00Z')).toBe('2026-07-02')
  })

  it('labels calendar days without shifting them', () => {
    expect(fmtCalendarDay('2026-01-02')).toBe('Fri 2 Jan')
  })

  it('labels runs relative to the delivery day', () => {
    expect(fmtRunRelative('2026-01-01T07:30:00Z', '2026-01-02')).toBe('07:30 D-1')
  })

  it('converts gate times', () => {
    expect(gateToMinutes('09:20')).toBe(560)
    expect(minutesToGate(590)).toBe('09:50')
  })
})

describe('api helpers', () => {
  it('builds query strings and drops empty params', () => {
    expect(apiUrl('/series', { mode: 'dayahead', gate: '09:20', start: undefined })).toBe(
      '/api/series?mode=dayahead&gate=09%3A20',
    )
  })

  it('maps policies to query params', () => {
    expect(policyParams({ mode: 'dayahead', gate: '09:50', lead: 24 })).toEqual({ mode: 'dayahead', gate: '09:50' })
    expect(policyParams({ mode: 'lead', gate: '09:50', lead: 6 })).toEqual({ mode: 'lead', lead: 6 })
  })
})
