import { fmtDateTime } from '../lib/format.js'

const SOURCE_LABELS = {
  live: { text: 'Live · Elexon BMRS', tone: 'good' },
  'disk-cache': { text: 'Cached · Elexon BMRS', tone: 'good' },
  snapshot: { text: 'Offline snapshot', tone: 'warning' },
}

export default function Header({ dataset, theme, onToggleTheme }) {
  const source = dataset ? (SOURCE_LABELS[dataset.source] ?? { text: dataset.source, tone: 'warning' }) : null
  return (
    <header className="topbar">
      <div className="topbar__inner">
        <div className="brand">
          <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="7" />
            <g fill="none" strokeWidth="2.4" strokeLinecap="round">
              <path d="M7 12h12a3.5 3.5 0 1 0-3.5-3.5" />
              <path d="M7 17h17a3.5 3.5 0 1 1-3.5 3.5" />
              <path d="M7 22h7" />
            </g>
          </svg>
          <div>
            <div className="brand__name">Wind Desk</div>
            <div className="brand__tagline">GB day-ahead wind forecast intelligence</div>
          </div>
        </div>
        <div className="topbar__meta">
          {source && (
            <span className={`badge badge--${source.tone}`} title={`Data retrieved ${fmtDateTime(dataset.retrievedAt)} UK`}>
              <span className="badge__dot" aria-hidden="true" />
              {source.text}
            </span>
          )}
          <button
            type="button"
            className="icon-button"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            title="Toggle theme"
          >
            {theme === 'dark' ? (
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5" /><path d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8 6 18M18 6l1.8-1.8" /></svg>
            ) : (
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></svg>
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
