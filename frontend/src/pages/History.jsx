import { Fragment, useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import { Database, History as HistoryIcon } from 'lucide-react'

import { EmptyState, ErrorNote, Panel, RiskBadge, Spinner, StatCard } from '../components/ui'
import { api } from '../api/client'
import { formatDateTime, formatTime, riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'

export default function History() {
  const { zones, revision } = useApp()
  const [summary, setSummary] = useState(null)
  const [series, setSeries] = useState([])
  const [log, setLog] = useState([])
  const [zoneFilter, setZoneFilter] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.historySummary().then(setSummary).catch((e) => setError(e.message))
  }, [revision])

  useEffect(() => {
    api
      .riskHistory({ limit: 200, zone_id: zoneFilter || undefined })
      .then((d) => setSeries(d.points.map((p) => ({ ...p, time: formatTime(p.t) }))))
      .catch(() => {})
    api
      .predictionLog(60, zoneFilter || undefined)
      .then((d) => setLog(d.records))
      .catch(() => {})
  }, [revision, zoneFilter])

  if (!summary) {
    return (
      <div className="space-y-3">
        <ErrorNote message={error} />
        <Spinner label="Loading history" />
      </div>
    )
  }

  const levelData = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    .map((lvl) => ({ name: lvl, value: summary.predictions_by_level[lvl] ?? 0 }))
    .filter((d) => d.value > 0)

  return (
    <div className="space-y-4">
      <ErrorNote message={error} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Predictions Logged" value={summary.totals.predictions} icon={Database} />
        <StatCard label="Sensor Readings" value={summary.totals.sensor_readings} icon={Database} />
        <StatCard label="Alerts Raised" value={summary.totals.alerts} tone={summary.totals.alerts ? 'high' : 'low'} />
        <StatCard label="Image Analyses" value={summary.totals.image_analyses} icon={HistoryIcon} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Panel
          title="Risk Score Timeline"
          subtitle={zoneFilter ? `Zone ${zoneFilter}` : 'All zones interleaved'}
          actions={
            <select
              value={zoneFilter}
              onChange={(e) => setZoneFilter(e.target.value)}
              className="rounded border border-panel-600 bg-panel-700 px-2 py-1 text-[11px] text-slate-200"
            >
              <option value="">All zones</option>
              {zones.map((z) => (
                <option key={z.zone_id} value={z.zone_id}>{z.zone_id}</option>
              ))}
            </select>
          }
          bodyClass="p-3 pr-4"
        >
          {series.length < 2 ? (
            <EmptyState icon={HistoryIcon} title="Not enough history yet"
                        hint="Records accumulate as the simulation runs." />
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={series} margin={{ top: 6, right: 6, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke="#222d3d" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" minTickGap={44} />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" width={44} />
                <Tooltip
                  contentStyle={{ background: '#111823', border: '1px solid #222d3d', borderRadius: 6, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Line type="monotone" dataKey="risk_score" stroke="#38bdf8" strokeWidth={1.8} dot={false}
                      isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Panel>

        <Panel title="Predictions by Level" bodyClass="p-3">
          {levelData.length === 0 ? (
            <EmptyState title="No predictions yet" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={170}>
                <PieChart>
                  <Pie data={levelData} dataKey="value" nameKey="name" innerRadius={42} outerRadius={68}
                       paddingAngle={2} stroke="none">
                    {levelData.map((d) => (
                      <Cell key={d.name} fill={riskStyle(d.name).hex} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#111823', border: '1px solid #222d3d', borderRadius: 6, fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1">
                {levelData.map((d) => (
                  <div key={d.name} className="flex items-center gap-2 text-[11px]">
                    <span className="h-2 w-2 rounded-full" style={{ background: riskStyle(d.name).hex }} />
                    <span className="text-slate-400">{d.name}</span>
                    <span className="ml-auto font-mono text-slate-300">{d.value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Panel>
      </div>

      <Panel title="Peak Risk by Zone" bodyClass="p-3 pr-4">
        {summary.zone_peaks.length === 0 ? (
          <EmptyState title="No zone history yet" />
        ) : (
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={summary.zone_peaks} margin={{ top: 6, right: 6, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="#222d3d" vertical={false} />
              <XAxis dataKey="zone_id" tick={{ fill: '#94a3b8', fontSize: 10 }} stroke="#222d3d" />
              <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" width={44} />
              <Tooltip
                cursor={{ fill: '#ffffff08' }}
                contentStyle={{ background: '#111823', border: '1px solid #222d3d', borderRadius: 6, fontSize: 12 }}
              />
              <Bar dataKey="peak" name="Peak risk" radius={[3, 3, 0, 0]}>
                {summary.zone_peaks.map((z) => (
                  <Cell key={z.zone_id} fill={riskStyle(
                    z.peak >= 80 ? 'CRITICAL' : z.peak >= 60 ? 'HIGH' : z.peak >= 35 ? 'MEDIUM' : 'LOW',
                  ).hex} />
                ))}
              </Bar>
              <Bar dataKey="mean" name="Mean risk" fill="#334155" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Panel>

      <Panel title="Prediction Log" subtitle="Newest first — click a row for its explanation" bodyClass="p-0">
        <div className="max-h-[520px] overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-panel-800">
              <tr className="border-b border-panel-600/70 text-[10px] uppercase tracking-wider text-slate-500">
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Zone</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 text-right font-medium">Score</th>
                <th className="px-3 py-2 font-medium">Level</th>
              </tr>
            </thead>
            <tbody>
              {log.map((r) => (
                <Fragment key={r.id}>
                  <tr
                    onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                    className="cursor-pointer border-b border-panel-700/50 hover:bg-panel-700/40"
                  >
                    <td className="px-3 py-1.5 font-mono text-[11px] text-slate-500">{formatDateTime(r.t)}</td>
                    <td className="px-3 py-1.5 text-slate-300">{r.zone_id}</td>
                    <td className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-slate-500">{r.source}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-slate-200">{r.risk_score}</td>
                    <td className="px-3 py-1.5"><RiskBadge level={r.risk_level} size="sm" /></td>
                  </tr>
                  {expanded === r.id && (
                    <tr className="border-b border-panel-700/50 bg-panel-900/60">
                      <td colSpan={5} className="px-3 py-3">
                        <p className="mb-2 text-[11px] leading-relaxed text-slate-400">
                          <span className="label-xs">Action · </span>
                          {r.recommended_action}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {r.contributions
                            .filter((c) => c.contribution_points > 0)
                            .slice(0, 6)
                            .map((c) => {
                              const s = riskStyle(c.level)
                              return (
                                <span
                                  key={c.feature}
                                  className={`rounded border px-2 py-1 text-[10px] ${s.bg} ${s.border} ${s.text}`}
                                >
                                  {c.label}: {c.level}
                                  <span className="ml-1 font-mono opacity-70">+{c.contribution_points}</span>
                                </span>
                              )
                            })}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {log.length === 0 && <EmptyState icon={Database} title="No records yet" />}
        </div>
      </Panel>
    </div>
  )
}
