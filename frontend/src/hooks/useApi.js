import { useEffect, useState } from 'react'
import { fetchJson } from '../lib/api.js'

/**
 * Fetch JSON for `url` (pass null to skip). Aborts superseded requests and keeps the
 * previous data while a new request is in flight, so charts hold their frame instead
 * of flashing a skeleton on every filter change.
 *
 * Returns { data, error, loading } where `loading` is true until `url`'s response lands.
 */
export function useApi(url) {
  const [state, setState] = useState({ url: null, data: null, error: null })

  useEffect(() => {
    if (!url) return undefined
    const controller = new AbortController()
    fetchJson(url, controller.signal)
      .then((data) => setState({ url, data, error: null }))
      .catch((error) => {
        if (!controller.signal.aborted) setState((prev) => ({ url, data: prev.data, error }))
      })
    return () => controller.abort()
  }, [url])

  return {
    data: state.data,
    error: state.url === url ? state.error : null,
    loading: Boolean(url) && state.url !== url,
  }
}
