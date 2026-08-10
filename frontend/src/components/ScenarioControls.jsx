/** NORMAL / WARNING / CRITICAL scenario switch for the simulated sensor network. */
import { Activity, RotateCcw, StepForward } from 'lucide-react'

import { useApp } from '../store/AppContext'

const SCENARIOS = [
  {
    key: 'NORMAL',
    label: 'Normal',
    desc: 'Dry bench, no blasting',
    idle: 'border-emerald-500/30 text-emerald-400/70 hover:bg-emerald-500/10',
    active: 'bg-emerald-500/20 border-emerald-500 text-emerald-300',
  },
  {
    key: 'WARNING',
    label: 'Warning',
    desc: 'Heavy rainfall + fractures',
    idle: 'border-amber-500/30 text-amber-400/70 hover:bg-amber-500/10',
    active: 'bg-amber-500/20 border-amber-500 text-amber-300',
  },
  {
    key: 'CRITICAL',
    label: 'Critical',
    desc: 'Storm + blasting, severe cracks',
    idle: 'border-red-500/30 text-red-400/70 hover:bg-red-500/10',
    active: 'bg-red-500/20 border-red-500 text-red-300',
  },
]

export default function ScenarioControls({ compact = false }) {
  const { simulation, setScenario, resetSimulation, forceTick, busy } = useApp()
  const current = simulation?.scenario ?? 'NORMAL'

  return (
    <div className="space-y-3">
      <div className={`grid gap-2 ${compact ? 'grid-cols-3' : 'grid-cols-1 sm:grid-cols-3'}`}>
        {SCENARIOS.map((s) => {
          const isActive = current === s.key
          return (
            <button
              key={s.key}
              type="button"
              disabled={busy}
              onClick={() => setScenario(s.key)}
              aria-pressed={isActive}
              className={`rounded-md border px-3 py-2.5 text-left transition-all disabled:opacity-50
                          ${isActive ? s.active : `bg-panel-700/50 ${s.idle}`}`}
            >
              <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider">
                {isActive && <Activity size={11} className="animate-pulse-fast" />}
                {s.label}
              </span>
              {!compact && <span className="block text-[10px] text-slate-500 mt-0.5">{s.desc}</span>}
            </button>
          )
        })}
      </div>

      <div className="flex items-center gap-2">
        <button type="button" className="btn-ghost text-xs py-1.5" onClick={forceTick} disabled={busy}>
          <StepForward size={12} /> Step
        </button>
        <button type="button" className="btn-ghost text-xs py-1.5" onClick={resetSimulation} disabled={busy}>
          <RotateCcw size={12} /> Reset
        </button>
        <span className="ml-auto font-mono text-[10px] text-slate-600">
          tick #{simulation?.tick ?? 0}
        </span>
      </div>
    </div>
  )
}
