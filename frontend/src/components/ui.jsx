/** Small presentational primitives shared across every page. */
import { AlertTriangle, Loader2 } from 'lucide-react'

import { riskStyle } from '../lib/risk'

export function Panel({ title, subtitle, actions, children, className = '', bodyClass = 'p-4' }) {
  return (
    <section className={`panel flex flex-col ${className}`}>
      {(title || actions) && (
        <header className="panel-header">
          <div className="min-w-0">
            {title && <h2 className="panel-title truncate">{title}</h2>}
            {subtitle && <p className="text-xs text-slate-500 mt-0.5 truncate">{subtitle}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={`${bodyClass} flex-1 min-h-0`}>{children}</div>
    </section>
  )
}

export function RiskBadge({ level, score, size = 'md' }) {
  const s = riskStyle(level)
  const pad = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded font-semibold uppercase tracking-wider
                  border ${pad} ${s.bg} ${s.text} ${s.border}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${s.solid}`} />
      {level}
      {score !== undefined && <span className="font-mono tabular-nums opacity-80">{Math.round(score)}</span>}
    </span>
  )
}

export function StatCard({ label, value, unit, hint, tone = 'default', icon: Icon }) {
  const tones = {
    default: 'text-slate-100',
    low: 'text-emerald-400',
    medium: 'text-amber-400',
    high: 'text-orange-400',
    critical: 'text-red-400',
    accent: 'text-sky-400',
  }
  return (
    <div className="panel px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <p className="label-xs">{label}</p>
        {Icon && <Icon size={14} className="text-slate-600 shrink-0" />}
      </div>
      <p className={`stat-value text-2xl mt-1.5 ${tones[tone] || tones.default}`}>
        {value}
        {unit && <span className="text-sm text-slate-500 ml-1 font-normal">{unit}</span>}
      </p>
      {hint && <p className="text-[11px] text-slate-500 mt-1 leading-snug">{hint}</p>}
    </div>
  )
}

/** Half-circle risk gauge. Pure SVG — no chart library needed for one arc. */
export function RiskGauge({ score = 0, level = 'LOW', size = 200, label = 'Mine-Wide Risk' }) {
  const s = riskStyle(level)
  const clamped = Math.max(0, Math.min(100, score))
  const r = size * 0.4
  const cx = size / 2
  const cy = size * 0.56
  const circumference = Math.PI * r // half circle
  const offset = circumference * (1 - clamped / 100)

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.68} viewBox={`0 0 ${size} ${size * 0.68}`} role="img"
           aria-label={`${label}: ${Math.round(clamped)} out of 100, ${level}`}>
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke="#222d3d" strokeWidth={size * 0.075} strokeLinecap="round"
        />
        <path
          d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
          fill="none" stroke={s.hex} strokeWidth={size * 0.075} strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 700ms ease, stroke 400ms ease' }}
        />
        <text x={cx} y={cy - size * 0.06} textAnchor="middle"
              className="fill-slate-100 font-mono font-bold" style={{ fontSize: size * 0.22 }}>
          {Math.round(clamped)}
        </text>
        <text x={cx} y={cy + size * 0.055} textAnchor="middle" fill={s.hex}
              className="font-semibold uppercase" style={{ fontSize: size * 0.075, letterSpacing: '0.14em' }}>
          {level}
        </text>
      </svg>
      <p className="label-xs -mt-1">{label} · 0–100</p>
    </div>
  )
}

/** Horizontal bar showing one factor's contribution to the current risk. */
export function FactorBar({ factor }) {
  const s = riskStyle(factor.level)
  const pct = Math.max(0, Math.min(100, factor.contribution_pct))
  return (
    <div className="py-1.5">
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <span className="text-xs text-slate-300 truncate">{factor.label}</span>
        <span className="flex items-center gap-2 shrink-0">
          <span className="font-mono text-[11px] text-slate-500">
            {factor.value}
            {factor.unit}
          </span>
          <span className={`text-[10px] font-semibold uppercase tracking-wider ${s.text}`}>
            {factor.level}
          </span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-panel-700 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: s.hex }}
        />
      </div>
    </div>
  )
}

export function SimulatedTag({ children = 'SIMULATED DATA', className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10
                  px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-amber-500/90 ${className}`}
    >
      <AlertTriangle size={9} />
      {children}
    </span>
  )
}

export function Spinner({ label = 'Loading' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-slate-500 text-sm">
      <Loader2 size={16} className="animate-spin" />
      {label}…
    </div>
  )
}

export function EmptyState({ icon: Icon, title, hint }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      {Icon && <Icon size={26} className="text-slate-700 mb-2" />}
      <p className="text-sm text-slate-400">{title}</p>
      {hint && <p className="text-xs text-slate-600 mt-1 max-w-sm">{hint}</p>}
    </div>
  )
}

export function ErrorNote({ message }) {
  if (!message) return null
  return (
    <div className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
      <AlertTriangle size={13} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}
