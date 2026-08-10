import { useCallback, useEffect, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Activity, RadioTower, RotateCcw } from 'lucide-react'

import ScenarioControls from '../components/ScenarioControls'
import { EmptyState, ErrorNote, Panel, RiskBadge, SimulatedTag, Spinner } from '../components/ui'
import { api } from '../api/client'
import { formatTime, riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'

const TRACES = [
  { key: 'rainfall', color: '#38bdf8' },
  { key: 'humidity', color: '#a78bfa' },
  { key: 'vibration', color: '#f97316' },
  { key: 'displacement', color: '#ef4444' },
  { key: 'slope_angle', color: '#10b981' },
]

/** One live channel: value, threshold-coloured bar, and a manual override slider. */
function ChannelRow({ channel, value, override, onOverride, onRelease, busy }) {
  const pct = ((value - channel.min) / (channel.max - channel.min)) * 100
  // `inverted` channels (rock quality) are dangerous when LOW, not high.
  const danger = channel.inverted ? value <= channel.danger : value >= channel.danger
  const warn = channel.inverted ? value <= channel.warn : value >= channel.warn
  const color = danger ? '#ef4444' : warn ? '#f59e0b' : '#10b981'

  return (
    <div className="rounded-md border border-panel-600/50 bg-panel-900/40 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs text-slate-300">
          {channel.label}
          {override !== undefined && (
            <span className="rounded bg-sky-500/20 px-1 py-px text-[8px] font-bold uppercase tracking-wider text-sky-400">
              pinned
            </span>
          )}
        </span>
        <span className="stat-value text-sm" style={{ color }}>
          {value?.toFixed(1)}
          <span className="ml-0.5 text-[10px] font-normal text-slate-500">{channel.unit}</span>
        </span>
      </div>

      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-panel-700">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.max(0, Math.min(100, pct))}%`, backgroundColor: color }}
        />
      </div>

      <div className="mt-2 flex items-center gap-2">
        <input
          type="range"
          className="slider flex-1"
          min={channel.min}
          max={channel.max}
          step={(channel.max - channel.min) / 100}
          value={value}
          disabled={busy}
          onChange={(e) => onOverride(channel.key, Number(e.target.value))}
          aria-label={`Override ${channel.label}`}
        />
        {override !== undefined && (
          <button
            type="button"
            onClick={() => onRelease(channel.key)}
            disabled={busy}
            className="rounded p-1 text-slate-500 hover:bg-panel-600 hover:text-slate-300"
            title="Release this override"
          >
            <RotateCcw size={11} />
          </button>
        )}
      </div>
    </div>
  )
}

export default function SensorMonitoring() {
  const { zones, simulation, refresh, busy, revision } = useApp()
  const [data, setData] = useState(null)
  const [zoneId, setZoneId] = useState('A-04')
  const [series, setSeries] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    api.sensors().then(setData).catch((e) => setError(e.message))
  }, [revision])

  useEffect(() => {
    let cancelled = false
    api
      .sensorHistory(zoneId, 80)
      .then((d) => {
        if (!cancelled) setSeries(d.points.map((p) => ({ ...p, time: formatTime(p.t) })))
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [zoneId, revision])

  const applyOverride = useCallback(
    async (key, value) => {
      // Optimistic local update so dragging the slider feels immediate; the
      // shared poller reconciles with the server a moment later.
      setData((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          zones: prev.zones.map((z) =>
            z.zone_id === zoneId ? { ...z, readings: { ...z.readings, [key]: value } } : z,
          ),
        }
      })
      try {
        await api.setOverride(zoneId, { [key]: value })
        refresh()
      } catch (e) {
        setError(e.message)
      }
    },
    [zoneId, refresh],
  )

  const releaseOverride = useCallback(
    async (key) => {
      try {
        await api.setOverride(zoneId, { [key]: null })
        refresh()
      } catch (e) {
        setError(e.message)
      }
    },
    [zoneId, refresh],
  )

  if (!data) return <Spinner label="Connecting to the sensor network" />

  const zoneData = data.zones.find((z) => z.zone_id === zoneId) ?? data.zones[0]
  const assessment = zones.find((z) => z.zone_id === zoneData?.zone_id)
  const overrides = simulation?.overrides?.[zoneId] ?? {}

  return (
    <div className="space-y-4">
      <ErrorNote message={error} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <RadioTower size={15} className="text-sky-400" />
          <span className="font-semibold">Simulated IoT Sensor Network</span>
        </div>
        <SimulatedTag>NO PHYSICAL SENSORS CONNECTED</SimulatedTag>
        <span className="ml-auto font-mono text-[10px] text-slate-600">
          Last update {formatTime(simulation?.last_update)} · tick #{simulation?.tick ?? 0}
        </span>
      </div>

      {/* Network overview */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.zones.map((z) => {
          const a = zones.find((x) => x.zone_id === z.zone_id)
          const active = z.zone_id === zoneId
          return (
            <button
              key={z.zone_id}
              type="button"
              onClick={() => setZoneId(z.zone_id)}
              className={`panel px-3 py-2.5 text-left transition-all ${
                active ? 'ring-1 ring-sky-500/50' : 'hover:border-panel-600'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-slate-200">{z.zone_id}</span>
                {a && <RiskBadge level={a.risk_level} score={a.risk_score} size="sm" />}
              </div>
              <p className="truncate text-[10px] text-slate-500">{z.name}</p>
              <div className="mt-2 grid grid-cols-4 gap-1.5 font-mono text-[10px]">
                {[
                  ['RAIN', z.readings.rainfall, 'mm'],
                  ['VIB', z.readings.vibration, ''],
                  ['DISP', z.readings.displacement, ''],
                  ['CRK', z.readings.crack_density, '%'],
                ].map(([lbl, val, unit]) => (
                  <div key={lbl} className="rounded bg-panel-900/60 px-1.5 py-1">
                    <p className="text-[8px] tracking-wider text-slate-600">{lbl}</p>
                    <p className="text-slate-300">{val?.toFixed(1)}{unit}</p>
                  </div>
                ))}
              </div>
            </button>
          )
        })}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel
          title={`Live Telemetry — ${zoneData?.zone_id}`}
          subtitle="Rolling window of recorded readings"
          actions={assessment && <RiskBadge level={assessment.risk_level} score={assessment.risk_score} />}
          bodyClass="p-3 pr-4"
        >
          {series.length < 2 ? (
            <EmptyState icon={Activity} title="Waiting for telemetry"
                        hint="Readings accumulate every few seconds as the simulation runs." />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={series} margin={{ top: 6, right: 6, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="2 4" stroke="#222d3d" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" minTickGap={44} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" width={44} />
                  <Tooltip
                    contentStyle={{ background: '#111823', border: '1px solid #222d3d', borderRadius: 6, fontSize: 12 }}
                    labelStyle={{ color: '#94a3b8' }}
                  />
                  {TRACES.map((t) => (
                    <Line key={t.key} type="monotone" dataKey={t.key} stroke={t.color} strokeWidth={1.6}
                          dot={false} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                {TRACES.map((t) => (
                  <span key={t.key} className="flex items-center gap-1.5 text-[10px] text-slate-500">
                    <span className="h-0.5 w-3 rounded" style={{ background: t.color }} />
                    {t.key.replace('_', ' ')}
                  </span>
                ))}
              </div>
            </>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="Scenario Simulator" bodyClass="p-3">
            <ScenarioControls compact />
          </Panel>

          <Panel
            title={`Channels — ${zoneData?.zone_id}`}
            subtitle="Drag a slider to inject a manual reading"
            bodyClass="p-3 space-y-2 max-h-[520px] overflow-y-auto"
          >
            {data.channels.map((c) => (
              <ChannelRow
                key={c.key}
                channel={c}
                value={zoneData?.readings?.[c.key] ?? 0}
                override={overrides[c.key]}
                onOverride={applyOverride}
                onRelease={releaseOverride}
                busy={busy}
              />
            ))}
          </Panel>
        </div>
      </div>
    </div>
  )
}
