import { describe, expect, it } from 'vitest'
import { gwFormatter, niceScale } from './chartKit.jsx'

describe('niceScale', () => {
  it('rounds a 0-21 GW range to 5 GW steps', () => {
    const scale = niceScale([0, 21_064], { includeZero: true })
    expect(scale.ticks).toEqual([0, 5000, 10000, 15000, 20000, 25000])
    expect(scale.domain).toEqual([0, 25000])
  })

  it('handles ranges that straddle zero', () => {
    const scale = niceScale([-3_400, 10_400], { includeZero: true, target: 6 })
    expect(scale.step).toBe(2500)
    expect(scale.domain).toEqual([-5000, 12500])
  })

  it('zooms in on narrow, non-zero ranges', () => {
    const scale = niceScale([1_805, 2_111], { target: 4 })
    expect(scale.ticks).toEqual([1800, 1900, 2000, 2100, 2200])
  })

  it('survives empty input', () => {
    expect(niceScale([]).ticks.length).toBeGreaterThan(1)
  })
})

describe('gwFormatter', () => {
  it('uses just enough decimals for the step', () => {
    expect(gwFormatter(5000)(15000)).toBe('15')
    expect(gwFormatter(100)(1900)).toBe('1.9')
    expect(gwFormatter(2500, { signed: true })(-2500)).toBe('−2.5')
    expect(gwFormatter(2500, { signed: true })(7500)).toBe('+7.5')
  })
})
