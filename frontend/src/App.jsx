import { useEffect, useState } from 'react'
import FilterBar from './components/FilterBar.jsx'
import Footer from './components/Footer.jsx'
import Header from './components/Header.jsx'
import { useApi } from './hooks/useApi.js'
import { useDebouncedValue } from './hooks/useDebouncedValue.js'
import { useHashTab } from './hooks/useHashTab.js'
import { apiUrl, policyParams } from './lib/api.js'
import AccuracyView from './views/AccuracyView.jsx'
import MethodologyView from './views/MethodologyView.jsx'
import TradingDesk from './views/TradingDesk.jsx'

const TABS = [
  { id: 'desk', label: 'Trading desk' },
  { id: 'accuracy', label: 'Forecast accuracy' },
  { id: 'method', label: 'Methodology' },
]
const TAB_IDS = TABS.map((t) => t.id)

const DEFAULT_POLICY = { choice: 'epex', mode: 'dayahead', gate: '09:20', lead: 24 }

export default function App() {
  const [tab, setTab] = useHashTab(TAB_IDS, 'desk')
  const [theme, toggleTheme] = useTheme()
  const meta = useApi(apiUrl('/meta'))

  const [policy, setPolicy] = useState(DEFAULT_POLICY)
  const [range, setRange] = useState(null) // null = whole delivery window from /meta

  // Sliders and time inputs fire on every keystroke/drag; only query once they settle.
  const debouncedPolicy = useDebouncedValue(policy, 300)
  const delivery = meta.data?.deliveryDays
  const effectiveRange = range ?? (delivery ? { start: delivery.firstDay, end: delivery.lastDay } : null)

  // Plain objects are fine here: useApi keys requests on the URL string, not identity.
  const rangeQuery = effectiveRange ? { start: effectiveRange.start, end: effectiveRange.end } : null
  const query = rangeQuery ? { ...policyParams(debouncedPolicy), ...rangeQuery } : null

  return (
    <div className="app">
      <Header dataset={meta.data?.dataset} theme={theme} onToggleTheme={toggleTheme} />

      <main className="main">
        <div className="page-intro">
          <h1>Day-ahead wind forecast vs outturn</h1>
          <p>
            How much wind the GB day-ahead desk could count on, how wrong that forecast turned out to be, and what that
            means for procurement. Decisions made in January 2026, national wind, Elexon BMRS.
          </p>
        </div>

        <nav className="tabs" role="tablist" aria-label="Views">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              className="tabs__tab"
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        {tab !== 'method' && (
          <FilterBar
            policy={policy}
            onPolicyChange={setPolicy}
            range={effectiveRange ?? { start: '', end: '' }}
            onRangeChange={setRange}
            meta={meta.data}
          />
        )}

        {meta.error && (
          <div className="alert" role="alert">
            Could not load data: {meta.error.message}. The API may still be fetching from Elexon — refresh in a moment.
          </div>
        )}

        <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
          {tab === 'desk' && query && <TradingDesk query={query} />}
          {tab === 'accuracy' && query && <AccuracyView query={query} rangeQuery={rangeQuery} policy={debouncedPolicy} />}
          {tab === 'method' && <MethodologyView meta={meta.data} />}
          {!query && tab !== 'method' && !meta.error && (
            <div className="loading-panel">Fetching January 2026 wind data from Elexon BMRS…</div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  )
}

/** Light/dark theme: follows the OS by default; an explicit choice is remembered per browser. */
function useTheme() {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem('wind-desk-theme')
      if (saved === 'light' || saved === 'dark') return saved
    } catch {
      /* storage unavailable (private mode) - fall back to OS preference */
    }
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('wind-desk-theme', theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))]
}
