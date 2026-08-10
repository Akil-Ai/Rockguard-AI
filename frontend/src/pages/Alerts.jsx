import { useEffect, useMemo, useState } from 'react'
import { BellOff, CheckCheck, Info } from 'lucide-react'

import AlertCard from '../components/AlertCard'
import { EmptyState, ErrorNote, Panel, StatCard } from '../components/ui'
import { api } from '../api/client'
import { useApp } from '../store/AppContext'

const OPERATOR = 'Control Room Operator'

export default function Alerts() {
  const { acknowledge, acknowledgeAll, busy, revision, dispatchMode, zones } = useApp()
  const [payload, setPayload] = useState(null)
  const [levelFilter, setLevelFilter] = useState('')
  const [zoneFilter, setZoneFilter] = useState('')
  const [openOnly, setOpenOnly] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .alerts({
        limit: 150,
        level: levelFilter || undefined,
        zone_id: zoneFilter || undefined,
        unacknowledged_only: openOnly || undefined,
      })
      .then(setPayload)
      .catch((e) => setError(e.message))
  }, [revision, levelFilter, zoneFilter, openOnly])

  const stats = payload?.stats ?? { total: 0, unacknowledged: 0, by_level: {} }
  const alerts = payload?.alerts ?? []

  const grouped = useMemo(() => {
    const open = alerts.filter((a) => !a.acknowledged)
    const closed = alerts.filter((a) => a.acknowledged)
    return { open, closed }
  }, [alerts])

  return (
    <div className="space-y-4">
      <ErrorNote message={error} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Unacknowledged" value={stats.unacknowledged}
                  tone={stats.unacknowledged ? 'critical' : 'low'} hint="Require operator action" />
        <StatCard label="Critical (all time)" value={stats.by_level?.CRITICAL ?? 0} tone="critical" />
        <StatCard label="High (all time)" value={stats.by_level?.HIGH ?? 0} tone="high" />
        <StatCard label="Total Raised" value={stats.total} hint="Since the database was created" />
      </div>

      <div className="flex items-start gap-2 rounded-md border border-sky-500/25 bg-sky-500/5 px-3 py-2.5">
        <Info size={14} className="mt-0.5 shrink-0 text-sky-400" />
        <div className="text-[11px] leading-relaxed text-slate-400">
          <p>
            Dispatch mode: <strong className="text-slate-200">{dispatchMode}</strong>
          </p>
          <p className="mt-0.5">
            {payload?.note ??
              'External SMS/WhatsApp dispatch is simulated unless Twilio credentials are supplied in backend/.env. Alerts are always recorded in-app.'}
          </p>
        </div>
      </div>

      <Panel
        title="Alert Log"
        subtitle="Raised automatically when a zone reaches HIGH or CRITICAL"
        actions={
          <button
            type="button"
            className="btn-ghost text-[10px] py-1"
            disabled={busy || stats.unacknowledged === 0}
            onClick={() => acknowledgeAll(OPERATOR)}
          >
            <CheckCheck size={11} /> Acknowledge all
          </button>
        }
        bodyClass="p-3 space-y-3"
      >
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            className="rounded border border-panel-600 bg-panel-700 px-2 py-1.5 text-[11px] text-slate-200"
          >
            <option value="">All levels</option>
            <option value="CRITICAL">Critical only</option>
            <option value="HIGH">High only</option>
          </select>
          <select
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value)}
            className="rounded border border-panel-600 bg-panel-700 px-2 py-1.5 text-[11px] text-slate-200"
          >
            <option value="">All zones</option>
            {zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>{z.zone_id}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <input type="checkbox" checked={openOnly} onChange={(e) => setOpenOnly(e.target.checked)}
                   className="accent-sky-500" />
            Unacknowledged only
          </label>
          <span className="ml-auto font-mono text-[10px] text-slate-600">{alerts.length} shown</span>
        </div>

        {alerts.length === 0 ? (
          <EmptyState
            icon={BellOff}
            title="No alerts match the current filters"
            hint="Switch the simulator to WARNING or CRITICAL on the Dashboard to generate alerts."
          />
        ) : (
          <div className="space-y-4">
            {grouped.open.length > 0 && (
              <div className="space-y-2">
                <p className="label-xs">Open · {grouped.open.length}</p>
                {grouped.open.map((a) => (
                  <AlertCard key={a.id} alert={a} onAcknowledge={(id) => acknowledge(id, OPERATOR)} busy={busy} />
                ))}
              </div>
            )}
            {grouped.closed.length > 0 && (
              <div className="space-y-2">
                <p className="label-xs">Acknowledged · {grouped.closed.length}</p>
                <div className="space-y-2 opacity-60">
                  {grouped.closed.map((a) => (
                    <AlertCard key={a.id} alert={a} compact />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Panel>
    </div>
  )
}
