/**
 * Thin API client.
 *
 * Base URL comes from VITE_API_BASE when set (see .env.example); otherwise it
 * falls back to the relative "/api" path, which Vite proxies to the backend in
 * development. No keys or secrets live in this file.
 */
const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }

  /**
   * True when the API could not be reached at all, as opposed to reaching it and
   * getting an error back.
   *
   * 0     - fetch() rejected outright (DNS, refused, CORS, offline)
   * 502/4 - a proxy or edge could not reach the upstream service
   * 503   - the service is unavailable / still starting
   *
   * A sleeping free-tier instance produces exactly these while it spins up, so
   * the UI uses this to show a "waking up" state instead of a hard error.
   * A plain 500 is deliberately excluded: that means the backend answered and
   * something is genuinely broken, which the user needs to see.
   */
  get isUnreachable() {
    return this.status === 0 || this.status === 502 || this.status === 503 || this.status === 504
  }
}

async function request(path, options = {}) {
  const url = `${BASE}/api${path}`
  let res
  try {
    res = await fetch(url, options)
  } catch (cause) {
    // fetch() only rejects for network-level failures. Status 0 is the caller's
    // signal that the API was unreachable rather than that it returned an error,
    // so the UI can distinguish "backend still waking up" from "backend broke".
    throw new ApiError('Cannot reach the RockGuard API.', 0)
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* response had no JSON body; keep the status text */
    }
    throw new ApiError(detail, res.status)
  }

  return res.json()
}

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => request('/health'),

  dashboard: () => request('/dashboard'),
  mine: () => request('/mine'),
  zones: () => request('/zones'),
  zone: (id) => request(`/zones/${id}`),

  sensors: () => request('/sensors'),
  setScenario: (scenario) => request('/sensors/scenario', json({ scenario })),
  setOverride: (zoneId, values) => request('/sensors/override', json({ zone_id: zoneId, values })),
  clearOverride: (zoneId) => request(`/sensors/override/${zoneId}`, { method: 'DELETE' }),
  tick: () => request('/sensors/tick', { method: 'POST' }),
  resetSensors: () => request('/sensors/reset', { method: 'POST' }),

  features: () => request('/features'),
  predict: (payload) => request('/predict', json(payload)),
  modelInfo: () => request('/model/info'),

  analyzeImage: (file, zoneId, applyToZone = true) => {
    const form = new FormData()
    form.append('file', file)
    form.append('zone_id', zoneId)
    form.append('apply_to_zone', String(applyToZone))
    return request('/vision/analyze', { method: 'POST', body: form })
  },
  visionHistory: (limit = 25) => request(`/vision/history?limit=${limit}`),

  alerts: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
    ).toString()
    return request(`/alerts${q ? `?${q}` : ''}`)
  },
  acknowledge: (id, by) => request(`/alerts/${id}/acknowledge`, json({ acknowledged_by: by })),
  acknowledgeAll: (by) => request('/alerts/acknowledge-all', json({ acknowledged_by: by })),

  riskHistory: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
    ).toString()
    return request(`/history/risk${q ? `?${q}` : ''}`)
  },
  mineRiskHistory: (buckets = 60) => request(`/history/risk/mine?buckets=${buckets}`),
  sensorHistory: (zoneId, limit = 120) =>
    request(`/history/sensors?limit=${limit}${zoneId ? `&zone_id=${zoneId}` : ''}`),
  historySummary: () => request('/history/summary'),
  predictionLog: (limit = 60, zoneId) =>
    request(`/history/predictions?limit=${limit}${zoneId ? `&zone_id=${zoneId}` : ''}`),
}
