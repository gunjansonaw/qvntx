/**
 * Thin HTTP layer for the Wind Desk API.
 *
 * All requests are relative to the current origin by default ("/api/..."), which works
 * in dev (Vite proxy), docker-compose (nginx proxy), Heroku (FastAPI serves the SPA)
 * and Vercel (rewrites). Set VITE_API_BASE_URL to call an API on another origin.
 */

const API_BASE = (import.meta.env?.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Build a fully-qualified API URL; undefined/null/'' params are dropped. */
export function apiUrl(path, params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value))
  }
  const qs = query.toString()
  return `${API_BASE}/api${path}${qs ? `?${qs}` : ''}`
}

export async function fetchJson(url, signal) {
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join('; ')
    } catch {
      /* non-JSON error body - keep the generic message */
    }
    throw new ApiError(detail, response.status)
  }
  return response.json()
}

/** Query parameters describing *which* forecast counts as "the forecast at decision time". */
export function policyParams(policy) {
  return policy.mode === 'lead' ? { mode: 'lead', lead: policy.lead } : { mode: 'dayahead', gate: policy.gate }
}
