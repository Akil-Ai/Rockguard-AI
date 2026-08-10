import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity, Bell, Gauge, History, LayoutDashboard, Map, Mountain, ScanLine, Wifi, WifiOff,
} from 'lucide-react'

import { riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'
import { RiskBadge, SimulatedTag } from './ui'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/map', label: 'Mine Map', icon: Map },
  { to: '/rock-analysis', label: 'Rock Analysis', icon: ScanLine },
  { to: '/sensors', label: 'Sensor Monitoring', icon: Activity },
  { to: '/prediction', label: 'Risk Prediction', icon: Gauge },
  { to: '/alerts', label: 'Alerts', icon: Bell },
  { to: '/history', label: 'History', icon: History },
]

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="font-mono text-xs tabular-nums text-slate-400">
      {now.toLocaleTimeString('en-GB', { hour12: false })}
      <span className="ml-2 text-slate-600">
        {now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
      </span>
    </span>
  )
}

export default function Layout() {
  const { overall, activeAlerts, connected, mine, simulation } = useApp()
  const level = overall?.risk_level ?? 'LOW'
  const s = riskStyle(level)

  return (
    <div className="flex h-full min-h-screen bg-panel-900">
      {/* ---- Sidebar ---- */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-panel-600/70 bg-panel-800/60 lg:flex">
        <div className="flex items-center gap-2.5 border-b border-panel-600/70 px-4 py-4">
          <div className="grid h-9 w-9 place-items-center rounded bg-sky-500/15 ring-1 ring-sky-500/30">
            <Mountain size={18} className="text-sky-400" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold tracking-tight text-slate-100">RockGuard AI</p>
            <p className="text-[10px] uppercase tracking-[0.12em] text-slate-500">Slope Safety Console</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? 'bg-sky-500/15 text-sky-300 ring-1 ring-inset ring-sky-500/25'
                    : 'text-slate-400 hover:bg-panel-700 hover:text-slate-200'
                }`
              }
            >
              <Icon size={15} className="shrink-0" />
              <span className="truncate">{label}</span>
              {to === '/alerts' && activeAlerts.length > 0 && (
                <span className="ml-auto rounded-full bg-red-500 px-1.5 py-0.5 font-mono text-[10px] font-bold text-white">
                  {activeAlerts.length}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-2 border-t border-panel-600/70 p-3">
          <div className={`rounded-md border px-3 py-2 ${s.bg} ${s.border}`}>
            <p className="label-xs">Mine-Wide Risk</p>
            <p className={`stat-value mt-0.5 text-2xl ${s.text}`}>
              {overall ? Math.round(overall.risk_score) : '--'}
              <span className="ml-1 text-xs font-normal text-slate-500">/100</span>
            </p>
            <p className={`text-[10px] font-semibold uppercase tracking-[0.12em] ${s.text}`}>{level}</p>
          </div>
          <SimulatedTag className="w-full justify-center" />
          <p className="text-[9px] leading-relaxed text-slate-600">
            Demo system for SIH25071. Synthetic data, fictional mine — not for operational use.
          </p>
        </div>
      </aside>

      {/* ---- Main column ---- */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-2 border-b border-panel-600/70 bg-panel-800/60 px-4 py-2.5">
          <div className="flex items-center gap-2 lg:hidden">
            <Mountain size={16} className="text-sky-400" />
            <span className="text-sm font-bold text-slate-100">RockGuard AI</span>
          </div>

          <div className="hidden min-w-0 md:block">
            <p className="truncate text-xs font-medium text-slate-300">{mine?.name ?? 'Loading site…'}</p>
            <p className="text-[10px] text-slate-600">
              {mine?.zone_count ?? 0} monitored zones · {mine?.total_personnel ?? 0} personnel on site
            </p>
          </div>

          <div className="ml-auto flex items-center gap-3">
            {simulation && (
              <span className="hidden items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-slate-500 sm:flex">
                Scenario
                <span className="rounded bg-panel-700 px-1.5 py-0.5 text-slate-300">{simulation.scenario}</span>
              </span>
            )}
            <RiskBadge level={level} score={overall?.risk_score} size="sm" />
            <span
              className={`flex items-center gap-1 text-[10px] uppercase tracking-wider ${
                connected ? 'text-emerald-500' : 'text-red-400'
              }`}
              title={connected ? 'Connected to the RockGuard API' : 'Backend unreachable'}
            >
              {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
              {connected ? 'Live' : 'Offline'}
            </span>
            <Clock />
          </div>
        </header>

        {/* Mobile nav */}
        <nav className="flex gap-1 overflow-x-auto border-b border-panel-600/70 bg-panel-800/40 px-2 py-1.5 lg:hidden">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-1.5 rounded px-2.5 py-1.5 text-xs ${
                  isActive ? 'bg-sky-500/15 text-sky-300' : 'text-slate-400'
                }`
              }
            >
              <Icon size={13} />
              {label}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 overflow-y-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
