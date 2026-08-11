/**
 * Shared live state for the whole console.
 *
 * One poller feeds every page, so the sidebar badge, the map and the dashboard
 * can never disagree about the current risk. Pages that need extra data (chart
 * history, alert lists) fetch it themselves and read the shared snapshot here.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'

import { api } from '../api/client'

const AppContext = createContext(null)

const POLL_MS = 4000
// Free-tier hosts idle their instances out. Poll harder before the first
// successful response so the console comes alive the moment the API wakes.
const WAKE_POLL_MS = 2500

export function AppProvider({ children }) {
  const [snapshot, setSnapshot] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [alertStats, setAlertStats] = useState({ total: 0, unacknowledged: 0, by_level: {} })
  const [dispatchMode, setDispatchMode] = useState('SIMULATED (in-app only)')
  const [error, setError] = useState(null)
  const [connected, setConnected] = useState(false)
  const [busy, setBusy] = useState(false)
  // True while we have never reached the API and are still retrying — this is
  // the cold-start case, which is normal rather than a fault, and must not be
  // presented to the user as an error.
  const [waking, setWaking] = useState(true)

  // A tick counter lets pages re-fetch their own data whenever the shared state
  // changes, without them each having to run a second timer.
  const [revision, setRevision] = useState(0)
  const mounted = useRef(true)
  const everConnected = useRef(false)

  const refresh = useCallback(async () => {
    try {
      const [dash, alertPayload] = await Promise.all([
        api.dashboard(),
        api.alerts({ limit: 40 }),
      ])
      if (!mounted.current) return
      setSnapshot(dash)
      setAlerts(alertPayload.alerts)
      setAlertStats(alertPayload.stats)
      setDispatchMode(alertPayload.dispatch_mode)
      setConnected(true)
      setError(null)
      setWaking(false)
      everConnected.current = true
      setRevision((r) => r + 1)
    } catch (err) {
      if (!mounted.current) return
      setConnected(false)
      // Unreachable (not merely erroring) before we have ever connected means
      // the backend is most likely still spinning up, not that anything is wrong.
      const coldStart = Boolean(err.isUnreachable) && !everConnected.current
      setWaking(coldStart)
      setError(coldStart ? null : err.message)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    let cancelled = false
    let timer

    // setTimeout chain rather than setInterval: the delay changes once the API
    // answers, and this avoids stacking requests if one poll runs long.
    const loop = async () => {
      await refresh()
      if (cancelled || !mounted.current) return
      timer = setTimeout(loop, everConnected.current ? POLL_MS : WAKE_POLL_MS)
    }
    loop()

    return () => {
      cancelled = true
      mounted.current = false
      clearTimeout(timer)
    }
  }, [refresh])

  /** Wrap a mutating call so the UI shows progress and always re-syncs after. */
  const run = useCallback(
    async (fn) => {
      setBusy(true)
      try {
        const result = await fn()
        await refresh()
        return result
      } catch (err) {
        setError(err.message)
        throw err
      } finally {
        if (mounted.current) setBusy(false)
      }
    },
    [refresh],
  )

  const setScenario = useCallback((scenario) => run(() => api.setScenario(scenario)), [run])
  const resetSimulation = useCallback(() => run(() => api.resetSensors()), [run])
  const forceTick = useCallback(() => run(() => api.tick()), [run])
  const acknowledge = useCallback((id, by) => run(() => api.acknowledge(id, by)), [run])
  const acknowledgeAll = useCallback((by) => run(() => api.acknowledgeAll(by)), [run])

  const value = useMemo(
    () => ({
      snapshot,
      zones: snapshot?.zones ?? [],
      overall: snapshot?.overall ?? null,
      mine: snapshot?.mine ?? null,
      simulation: snapshot?.simulation ?? null,
      engine: snapshot?.engine ?? null,
      alerts,
      activeAlerts: alerts.filter((a) => !a.acknowledged),
      alertStats,
      dispatchMode,
      error,
      connected,
      waking,
      busy,
      revision,
      refresh,
      setScenario,
      resetSimulation,
      forceTick,
      acknowledge,
      acknowledgeAll,
    }),
    [
      snapshot, alerts, alertStats, dispatchMode, error, connected, waking, busy, revision,
      refresh, setScenario, resetSimulation, forceTick, acknowledge, acknowledgeAll,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>')
  return ctx
}
