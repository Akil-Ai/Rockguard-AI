import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  BellOff, Boxes, CloudRain, HardHat, Layers, ShieldAlert, TrendingUp, Users, Waves,
} from 'lucide-react'

import AlertCard from '../components/AlertCard'
import ScenarioControls from '../components/ScenarioControls'
import {
  EmptyState, ErrorNote, FactorBar, Panel, RiskBadge, RiskGauge, SimulatedTag,
  Spinner, StatCard, WakingScreen,
} from '../components/ui'
import { api } from '../api/client'
import { formatTime, riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'

function ZoneRow({ zone }) {
  const s = riskStyle(zone.risk_level)
  return (
    <Link
      to="/map"
      className="flex items-center gap-3 rounded-md border border-panel-600/50 bg-panel-700/30 px-3 py-2 transition-colors hover:bg-panel-700/70"
    >
      <span className={`h-8 w-1 shrink-0 rounded-full ${s.solid}`} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-semibold text-slate-200">
          {zone.zone_id}
          <span className="ml-2 font-normal text-slate-500">{zone.zone_name}</span>
        </p>
        <p className="mt-0.5 flex items-center gap-2.5 font-mono text-[10px] text-slate-500">
          <span className="inline-flex items-center gap-1"><Users size={9} />{zone.personnel}</span>
          <span className="inline-flex items-center gap-1"><CloudRain size={9} />{zone.sensors.rainfall?.toFixed(0)}mm</span>
          <span className="inline-flex items-center gap-1"><Waves size={9} />{zone.sensors.vibration?.toFixed(1)}mm/s</span>
          <span className="inline-flex items-center gap-1"><Layers size={9} />{zone.sensors.crack_density?.toFixed(1)}%</span>
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className={`stat-value text-lg ${s.text}`}>{Math.round(zone.risk_score)}</p>
        <p className={`text-[9px] font-semibold uppercase tracking-wider ${s.text}`}>{zone.risk_level}</p>
      </div>
    </Link>
  )
}

export default function Dashboard() {
  const { overall, zones, mine, activeAlerts, error, waking, acknowledge, busy, revision, engine } = useApp()
  const [trend, setTrend] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .mineRiskHistory(70)
      .then((d) => {
        if (cancelled) return
        setTrend(d.points.map((p) => ({ ...p, time: formatTime(p.t) })))
      })
      .catch(() => {
        /* the shared poller already surfaces connection errors */
      })
    return () => {
      cancelled = true
    }
  }, [revision])

  if (!overall) {
    if (waking) return <WakingScreen />
    return (
      <div className="space-y-3">
        <ErrorNote message={error} />
        <Spinner label="Connecting to the RockGuard control system" />
      </div>
    )
  }

  const worst = overall.worst_zone
  const worstZone = zones.find((z) => z.zone_id === worst?.zone_id)
  const tone = overall.risk_level.toLowerCase()

  return (
    <div className="space-y-4">
      <ErrorNote message={error} />

      {/* Banner for an active HIGH/CRITICAL situation */}
      {activeAlerts.length > 0 && (
        <div
          className={`flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3 ${
            riskStyle(activeAlerts[0].risk_level).border
          } ${riskStyle(activeAlerts[0].risk_level).bg}`}
        >
          <ShieldAlert size={18} className={riskStyle(activeAlerts[0].risk_level).text} />
          <div className="min-w-0 flex-1">
            <p className={`text-sm font-bold ${riskStyle(activeAlerts[0].risk_level).text}`}>
              {activeAlerts.length} unacknowledged alert{activeAlerts.length > 1 ? 's' : ''} —{' '}
              {activeAlerts[0].zone_id} at {Math.round(activeAlerts[0].risk_score)}/100
            </p>
            <p className="truncate text-xs text-slate-400">{activeAlerts[0].recommended_action}</p>
          </div>
          <Link to="/alerts" className="btn-ghost shrink-0 text-xs">Open alert log</Link>
        </div>
      )}

      {/* Top strip: gauge + KPIs */}
      <div className="grid gap-4 xl:grid-cols-[300px_1fr]">
        <Panel title="Mine-Wide Risk Index" bodyClass="p-4 flex flex-col items-center justify-center">
          <RiskGauge score={overall.risk_score} level={overall.risk_level} size={190} />
          <p className="mt-2 text-center text-[10px] leading-relaxed text-slate-600">{overall.method}</p>
          <div className="mt-3 w-full rounded-md border border-panel-600/60 bg-panel-900/50 px-3 py-2">
            <p className="label-xs">Highest-risk zone</p>
            <div className="mt-1 flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-slate-200">{worst?.zone_id ?? '—'}</span>
              <RiskBadge level={worst?.risk_level ?? 'LOW'} score={worst?.risk_score} size="sm" />
            </div>
          </div>
        </Panel>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Active Alerts" value={activeAlerts.length}
                      tone={activeAlerts.length ? 'critical' : 'low'} icon={ShieldAlert}
                      hint={activeAlerts.length ? 'Awaiting acknowledgement' : 'No open alerts'} />
            <StatCard label="Personnel At Risk" value={overall.personnel_at_risk}
                      tone={overall.personnel_at_risk ? 'high' : 'low'} icon={HardHat}
                      hint={`of ${mine?.total_personnel ?? 0} on site`} />
            <StatCard label="Zones Monitored" value={zones.length} icon={Boxes}
                      hint={Object.entries(overall.zones_by_level).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(' · ')} />
            <StatCard label="Failure Probability" value={(overall.probability * 100).toFixed(1)} unit="%"
                      tone={tone} icon={TrendingUp} hint="Mean across all zones" />
          </div>

          <Panel
            title="Risk History"
            subtitle="Peak and mean zone risk over recent simulation ticks"
            actions={<SimulatedTag />}
            bodyClass="p-3 pr-4"
          >
            {trend.length < 2 ? (
              <EmptyState icon={TrendingUp} title="Collecting telemetry"
                          hint="The trend line appears after a few simulation ticks." />
            ) : (
              <ResponsiveContainer width="100%" height={188}>
                <AreaChart data={trend} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
                  <defs>
                    <linearGradient id="peakFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f97316" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#f97316" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="meanFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#38bdf8" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="2 4" stroke="#222d3d" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" minTickGap={40} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" width={44} />
                  <Tooltip
                    contentStyle={{ background: '#111823', border: '1px solid #222d3d', borderRadius: 6, fontSize: 12 }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  <Area type="monotone" dataKey="peak" name="Peak zone" stroke="#f97316" strokeWidth={2}
                        fill="url(#peakFill)" dot={false} isAnimationActive={false} />
                  <Area type="monotone" dataKey="mean" name="Mean" stroke="#38bdf8" strokeWidth={1.5}
                        fill="url(#meanFill)" dot={false} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Panel>
        </div>
      </div>

      {/* Bottom strip */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Zone Status Board" subtitle="Sorted by current risk" bodyClass="p-3 space-y-2">
          {[...zones].sort((a, b) => b.risk_score - a.risk_score).map((z) => (
            <ZoneRow key={z.zone_id} zone={z} />
          ))}
        </Panel>

        <div className="space-y-4">
          <Panel title="Scenario Simulator" subtitle="Drives the simulated IoT network" bodyClass="p-3">
            <ScenarioControls />
          </Panel>

          <Panel
            title="Why — Contributing Factors"
            subtitle={worstZone ? `Explaining ${worstZone.zone_id}` : 'Highest-risk zone'}
            bodyClass="p-3"
          >
            {worstZone ? (
              <>
                <div className="space-y-0.5">
                  {worstZone.contributions.slice(0, 5).map((f) => (
                    <FactorBar key={f.feature} factor={f} />
                  ))}
                </div>
                <p className="mt-3 rounded border border-panel-600/60 bg-panel-900/50 px-2.5 py-2 text-[11px] leading-relaxed text-slate-400">
                  {worstZone.recommended_action}
                </p>
              </>
            ) : (
              <Spinner />
            )}
          </Panel>
        </div>

        <Panel
          title="Active Alerts"
          subtitle={activeAlerts.length ? 'Unacknowledged' : 'All clear'}
          actions={<Link to="/alerts" className="text-[10px] uppercase tracking-wider text-sky-400 hover:text-sky-300">View all</Link>}
          bodyClass="p-3 space-y-2 max-h-[520px] overflow-y-auto"
        >
          {activeAlerts.length === 0 ? (
            <EmptyState icon={BellOff} title="No active alerts"
                        hint="Alerts are raised automatically when a zone reaches HIGH or CRITICAL." />
          ) : (
            activeAlerts.slice(0, 6).map((a) => (
              <AlertCard key={a.id} alert={a} onAcknowledge={(id) => acknowledge(id, 'Control Room Operator')} busy={busy} />
            ))
          )}
        </Panel>
      </div>

      <p className="pb-2 text-center text-[10px] leading-relaxed text-slate-600">
        Risk engine: {engine?.engine ?? 'unknown'} · trained on a synthetic dataset · explanations by counterfactual
        ablation. All readings are simulated; this system has not been validated against real rockfall events.
      </p>
    </div>
  )
}
