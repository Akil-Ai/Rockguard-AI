import { useCallback, useEffect, useState } from 'react'
import {
  Bar, BarChart, Cell, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Brain, Gauge, Play, RotateCcw } from 'lucide-react'

import { ErrorNote, Panel, RiskBadge, RiskGauge, SimulatedTag, Spinner } from '../components/ui'
import { api } from '../api/client'
import { riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'

const PRESET_LABELS = {
  NORMAL: 'Normal conditions',
  HEAVY_RAIN_CRACKS: 'Heavy rainfall + cracks',
  BLAST_SEVERE_CRACKS: 'Blasting + severe cracks',
}

export default function RiskPrediction() {
  const { zones } = useApp()
  const [schema, setSchema] = useState(null)
  const [values, setValues] = useState(null)
  const [result, setResult] = useState(null)
  const [modelMeta, setModelMeta] = useState(null)
  const [zoneId, setZoneId] = useState('')
  const [error, setError] = useState(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    api
      .features()
      .then((d) => {
        setSchema(d)
        setValues(d.presets.NORMAL)
      })
      .catch((e) => setError(e.message))
    api.modelInfo().then(setModelMeta).catch(() => {})
  }, [])

  const run = useCallback(
    async (payload) => {
      setRunning(true)
      setError(null)
      try {
        setResult(await api.predict({ ...payload, zone_id: zoneId || null, persist: true }))
      } catch (e) {
        setError(e.message)
      } finally {
        setRunning(false)
      }
    },
    [zoneId],
  )

  // Score the default preset once the schema arrives so the page is never blank.
  useEffect(() => {
    if (values && !result && !running) run(values)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values])

  const loadZone = useCallback(
    (id) => {
      const z = zones.find((x) => x.zone_id === id)
      if (!z) return
      setValues(z.features)
      run(z.features)
    },
    [zones, run],
  )

  if (!schema || !values) {
    return (
      <div className="space-y-3">
        <ErrorNote message={error} />
        <Spinner label="Loading model schema" />
      </div>
    )
  }

  const contributions = result?.contributions ?? []
  const positive = contributions.filter((c) => c.contribution_points > 0)
  const radarData = contributions.map((c) => ({
    factor: c.label.split(' ')[0],
    share: c.contribution_pct,
  }))

  return (
    <div className="grid gap-4 xl:grid-cols-[400px_1fr]">
      {/* ---- Inputs ---- */}
      <div className="space-y-4">
        <Panel
          title="Risk Prediction — What-If"
          subtitle="Set conditions and score them against the model"
          bodyClass="p-3 space-y-3"
        >
          <div>
            <p className="label-xs mb-1.5">Scenario presets</p>
            <div className="grid grid-cols-1 gap-1.5">
              {Object.entries(schema.presets).map(([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => { setValues(preset); run(preset) }}
                  disabled={running}
                  className="rounded border border-panel-600 bg-panel-700/50 px-2.5 py-2 text-left text-[11px] text-slate-300 transition-colors hover:bg-panel-600 disabled:opacity-40"
                >
                  {PRESET_LABELS[key] ?? key}
                </button>
              ))}
            </div>
          </div>

          <div className="border-t border-panel-600/70 pt-3">
            <p className="label-xs mb-1.5">Or load a live zone's readings</p>
            <div className="flex gap-2">
              <select
                value={zoneId}
                onChange={(e) => setZoneId(e.target.value)}
                className="flex-1 rounded border border-panel-600 bg-panel-700 px-2 py-1.5 text-xs text-slate-200"
              >
                <option value="">Manual (unattributed)</option>
                {zones.map((z) => (
                  <option key={z.zone_id} value={z.zone_id}>{z.zone_id} — {z.zone_name}</option>
                ))}
              </select>
              <button
                type="button"
                className="btn-ghost text-xs"
                disabled={!zoneId || running}
                onClick={() => loadZone(zoneId)}
              >
                Load
              </button>
            </div>
          </div>

          <div className="space-y-2.5 border-t border-panel-600/70 pt-3">
            {schema.features.map((f) => (
              <div key={f.name}>
                <div className="flex items-baseline justify-between gap-2">
                  <label htmlFor={`f-${f.name}`} className="text-[11px] text-slate-400">{f.label}</label>
                  <span className="stat-value text-xs text-slate-200">
                    {Number(values[f.name]).toFixed(1)}
                    <span className="ml-0.5 text-[10px] font-normal text-slate-500">{f.unit}</span>
                  </span>
                </div>
                <input
                  id={`f-${f.name}`}
                  type="range"
                  className="slider mt-1"
                  min={f.min}
                  max={f.max}
                  step={f.step}
                  value={values[f.name]}
                  onChange={(e) => setValues((v) => ({ ...v, [f.name]: Number(e.target.value) }))}
                />
              </div>
            ))}
          </div>

          <div className="flex gap-2 border-t border-panel-600/70 pt-3">
            <button type="button" className="btn-primary flex-1 text-xs" onClick={() => run(values)} disabled={running}>
              <Play size={12} /> {running ? 'Scoring…' : 'Run Prediction'}
            </button>
            <button
              type="button"
              className="btn-ghost text-xs"
              onClick={() => { setValues(schema.presets.NORMAL); run(schema.presets.NORMAL) }}
              disabled={running}
            >
              <RotateCcw size={12} />
            </button>
          </div>

          <ErrorNote message={error} />
        </Panel>

        {modelMeta && (
          <Panel title="Model" bodyClass="p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              {[
                ['Algorithm', modelMeta.metrics?.model ?? modelMeta.engine?.engine ?? '—'],
                ['Calibration', modelMeta.metrics?.calibration ?? '—'],
                ['ROC-AUC*', modelMeta.metrics?.roc_auc ? modelMeta.metrics.roc_auc.toFixed(3) : '—'],
                ['Brier*', modelMeta.metrics?.brier ? modelMeta.metrics.brier.toFixed(3) : '—'],
              ].map(([k, v]) => (
                <div key={k} className="rounded border border-panel-600/50 bg-panel-900/50 px-2 py-1.5">
                  <p className="text-[9px] uppercase tracking-wider text-slate-500">{k}</p>
                  <p className="stat-value truncate text-xs text-slate-200">{v}</p>
                </div>
              ))}
            </div>
            <p className="text-[10px] leading-relaxed text-amber-500/80">
              * Measured on a held-out <strong>synthetic</strong> dataset. These numbers describe how well the
              model recovered the artificial hazard function it was trained on — they are not evidence of
              real-world rockfall prediction accuracy.
            </p>
          </Panel>
        )}
      </div>

      {/* ---- Results ---- */}
      <div className="space-y-4">
        {result ? (
          <>
            <div className="grid gap-4 md:grid-cols-[280px_1fr]">
              <Panel title="Predicted Risk" bodyClass="p-4 flex flex-col items-center justify-center">
                <RiskGauge score={result.risk_score} level={result.risk_level} size={190} label="Risk Score" />
                <div className="mt-3 w-full space-y-1.5">
                  <div className="flex items-center justify-between rounded border border-panel-600/50 bg-panel-900/50 px-2.5 py-1.5">
                    <span className="text-[10px] uppercase tracking-wider text-slate-500">Failure probability</span>
                    <span className="stat-value text-xs text-slate-200">{(result.probability * 100).toFixed(2)}%</span>
                  </div>
                  <div className="flex items-center justify-between rounded border border-panel-600/50 bg-panel-900/50 px-2.5 py-1.5">
                    <span className="text-[10px] uppercase tracking-wider text-slate-500">Level</span>
                    <RiskBadge level={result.risk_level} size="sm" />
                  </div>
                </div>
              </Panel>

              <Panel
                title="Explainable AI — Factor Contributions"
                subtitle="Counterfactual ablation: risk points each factor is adding"
                actions={<SimulatedTag>SYNTHETIC MODEL</SimulatedTag>}
                bodyClass="p-3"
              >
                <ResponsiveContainer width="100%" height={230}>
                  <BarChart
                    data={positive.map((c) => ({ ...c, name: c.label }))}
                    layout="vertical"
                    margin={{ top: 4, right: 16, left: 26, bottom: 0 }}
                  >
                    <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} stroke="#222d3d" />
                    <YAxis
                      type="category" dataKey="name" width={104}
                      tick={{ fill: '#94a3b8', fontSize: 10 }} stroke="#222d3d"
                    />
                    <Tooltip
                      cursor={{ fill: '#ffffff08' }}
                      contentStyle={{ background: '#111823', border: '1px solid #222d3d', borderRadius: 6, fontSize: 12 }}
                      formatter={(v, _n, p) => [`${v} pts (${p.payload.contribution_pct}%)`, p.payload.level]}
                    />
                    <Bar dataKey="contribution_points" radius={[0, 3, 3, 0]}>
                      {positive.map((c) => (
                        <Cell key={c.feature} fill={riskStyle(c.level).hex} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Panel>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
              <Panel title="Factor Breakdown" bodyClass="p-0">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-panel-600/70 text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="px-3 py-2 font-medium">Factor</th>
                      <th className="px-3 py-2 font-medium">Value</th>
                      <th className="px-3 py-2 font-medium">Level</th>
                      <th className="px-3 py-2 text-right font-medium">Risk pts</th>
                      <th className="px-3 py-2 text-right font-medium">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contributions.map((c) => {
                      const s = riskStyle(c.level)
                      return (
                        <tr key={c.feature} className="border-b border-panel-700/50 last:border-0">
                          <td className="px-3 py-2 text-slate-300">{c.label}</td>
                          <td className="px-3 py-2 font-mono text-slate-400">{c.value}{c.unit}</td>
                          <td className="px-3 py-2">
                            <span className={`text-[10px] font-semibold uppercase tracking-wider ${s.text}`}>
                              {c.level}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-300">
                            {c.contribution_points > 0 ? '+' : ''}{c.contribution_points}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-slate-500">{c.contribution_pct}%</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </Panel>

              <div className="space-y-4">
                <Panel title="Contribution Profile" bodyClass="p-2">
                  <ResponsiveContainer width="100%" height={210}>
                    <RadarChart data={radarData} outerRadius="72%">
                      <PolarGrid stroke="#222d3d" />
                      <PolarAngleAxis dataKey="factor" tick={{ fill: '#64748b', fontSize: 9 }} />
                      <PolarRadiusAxis tick={false} axisLine={false} domain={[0, 'auto']} />
                      <Radar dataKey="share" stroke={riskStyle(result.risk_level).hex}
                             fill={riskStyle(result.risk_level).hex} fillOpacity={0.35} />
                    </RadarChart>
                  </ResponsiveContainer>
                </Panel>

                <Panel title="Recommended Action" bodyClass="p-3">
                  <div className={`rounded border px-3 py-2.5 ${riskStyle(result.risk_level).bg} ${riskStyle(result.risk_level).border}`}>
                    <p className="text-[11px] leading-relaxed text-slate-200">{result.recommended_action}</p>
                  </div>
                  <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-relaxed text-slate-600">
                    <Brain size={11} className="mt-0.5 shrink-0" />
                    Explanations come from re-scoring the same inputs with one factor reset to a safe reference
                    value, so each bar is literally the risk points that factor is adding right now.
                  </p>
                </Panel>
              </div>
            </div>
          </>
        ) : (
          <Panel bodyClass="p-10">
            <div className="text-center">
              <Gauge size={26} className="mx-auto text-slate-700" />
              <p className="mt-2 text-sm text-slate-400">Set the conditions and run a prediction</p>
            </div>
          </Panel>
        )}
      </div>
    </div>
  )
}
