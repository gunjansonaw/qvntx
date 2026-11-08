import { useCallback, useEffect, useState } from 'react'

/** Tab state mirrored in location.hash so views are linkable (#accuracy) and back/forward works. */
export function useHashTab(tabs, fallback) {
  const read = useCallback(() => {
    const hash = window.location.hash.replace('#', '')
    return tabs.includes(hash) ? hash : fallback
  }, [tabs, fallback])

  const [tab, setTab] = useState(read)

  useEffect(() => {
    const onHashChange = () => setTab(read())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [read])

  const select = useCallback((next) => {
    window.location.hash = next
    setTab(next)
  }, [])

  return [tab, select]
}
