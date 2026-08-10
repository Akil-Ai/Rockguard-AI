/** Single source of truth for how risk levels look across the whole UI. */

export const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

export const RISK_STYLES = {
  LOW: {
    hex: '#10b981',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/40',
    ring: 'ring-emerald-500/30',
    solid: 'bg-emerald-500',
    label: 'Low',
  },
  MEDIUM: {
    hex: '#f59e0b',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/40',
    ring: 'ring-amber-500/30',
    solid: 'bg-amber-500',
    label: 'Medium',
  },
  HIGH: {
    hex: '#f97316',
    text: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/40',
    ring: 'ring-orange-500/30',
    solid: 'bg-orange-500',
    label: 'High',
  },
  CRITICAL: {
    hex: '#ef4444',
    text: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/40',
    ring: 'ring-red-500/30',
    solid: 'bg-red-500',
    label: 'Critical',
  },
}

export const riskStyle = (level) => RISK_STYLES[level] || RISK_STYLES.LOW

export const isAlertable = (level) => level === 'HIGH' || level === 'CRITICAL'

/** Format an ISO timestamp as a control-room clock reading. */
export function formatTime(iso) {
  if (!iso) return '--:--:--'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return '--:--:--'
  return d.toLocaleTimeString('en-GB', { hour12: false })
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function relativeTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  const secs = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000))
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}
