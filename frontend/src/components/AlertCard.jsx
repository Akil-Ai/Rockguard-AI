import { BellRing, Check, Send } from 'lucide-react'

import { relativeTime, riskStyle } from '../lib/risk'

export default function AlertCard({ alert, onAcknowledge, busy, compact = false }) {
  const s = riskStyle(alert.risk_level)
  const isCritical = alert.risk_level === 'CRITICAL'

  return (
    <article
      className={`rounded-md border ${s.border} ${s.bg} p-3 ${
        !alert.acknowledged && isCritical ? 'animate-pulse-fast' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className={`text-sm font-semibold ${s.text} flex items-center gap-1.5`}>
            <BellRing size={13} className="shrink-0" />
            <span className="truncate">{alert.title}</span>
          </h3>
          <p className="mt-1.5 whitespace-pre-line font-mono text-[11px] leading-relaxed text-slate-300">
            {alert.message}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p className={`stat-value text-xl ${s.text}`}>{Math.round(alert.risk_score)}</p>
          <p className="label-xs">/100</p>
        </div>
      </div>

      {!compact && (
        <p className="mt-2.5 rounded border border-panel-600/70 bg-panel-900/60 px-2.5 py-2 text-[11px] leading-relaxed text-slate-400">
          <span className="font-semibold uppercase tracking-wider text-slate-500">Action · </span>
          {alert.recommended_action}
        </p>
      )}

      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[10px] text-slate-500">
        <span className="font-mono">{relativeTime(alert.created_at)}</span>
        <span className="inline-flex items-center gap-1">
          <Send size={9} />
          {alert.channel} · {alert.dispatch_status}
        </span>
        {alert.acknowledged ? (
          <span className="ml-auto inline-flex items-center gap-1 text-emerald-500/80">
            <Check size={10} /> Acknowledged by {alert.acknowledged_by || 'operator'}
          </span>
        ) : (
          onAcknowledge && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onAcknowledge(alert.id)}
              className="btn-ghost ml-auto px-2 py-1 text-[10px]"
            >
              <Check size={10} /> Acknowledge
            </button>
          )
        )}
      </div>
    </article>
  )
}
