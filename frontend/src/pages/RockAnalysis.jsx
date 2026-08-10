import { useCallback, useEffect, useRef, useState } from 'react'
import {
  FileImage, Info, ScanLine, Upload, X,
} from 'lucide-react'

import { EmptyState, ErrorNote, FactorBar, Panel, RiskBadge, SimulatedTag, Spinner } from '../components/ui'
import { api } from '../api/client'
import { formatDateTime, riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'

// Bundled synthetic faces so the demo always has an input, even with no network
// and no photos on the presenting machine.
const SAMPLES = [
  { file: 'rockface_stable.png', label: 'Stable face', hint: 'Sparse jointing' },
  { file: 'rockface_moderate.png', label: 'Moderate', hint: 'Developing fracture set' },
  { file: 'rockface_fractured.png', label: 'Fractured', hint: 'Dense intersecting joints' },
]

function MetricTile({ label, value, unit, tone }) {
  return (
    <div className="rounded border border-panel-600/50 bg-panel-900/50 px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`stat-value text-base ${tone || 'text-slate-200'}`}>
        {value}
        {unit && <span className="ml-0.5 text-[10px] font-normal text-slate-500">{unit}</span>}
      </p>
    </div>
  )
}

export default function RockAnalysis() {
  const { zones, refresh } = useApp()
  const [zoneId, setZoneId] = useState('A-04')
  const [applyToZone, setApplyToZone] = useState(true)
  const [result, setResult] = useState(null)
  const [preview, setPreview] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const loadHistory = useCallback(() => {
    api.visionHistory(12).then((d) => setHistory(d.analyses)).catch(() => {})
  }, [])

  useEffect(loadHistory, [loadHistory])

  // Object URLs for the local preview must be released or they leak.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const analyze = useCallback(
    async (file) => {
      if (!file) return
      setRunning(true)
      setError(null)
      setResult(null)
      setPreview((old) => {
        if (old) URL.revokeObjectURL(old)
        return URL.createObjectURL(file)
      })
      try {
        const data = await api.analyzeImage(file, zoneId, applyToZone)
        setResult(data)
        loadHistory()
        if (applyToZone) refresh()
      } catch (err) {
        setError(err.message)
      } finally {
        setRunning(false)
      }
    },
    [zoneId, applyToZone, loadHistory, refresh],
  )

  const analyzeSample = useCallback(
    async (name) => {
      setRunning(true)
      setError(null)
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}samples/${name}`)
        if (!res.ok) throw new Error(`Sample image "${name}" not found.`)
        const blob = await res.blob()
        await analyze(new File([blob], name, { type: blob.type || 'image/png' }))
      } catch (err) {
        setError(err.message)
        setRunning(false)
      }
    },
    [analyze],
  )

  const onDrop = useCallback(
    (e) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files?.[0]
      if (file) analyze(file)
    },
    [analyze],
  )

  const metrics = result?.metrics
  const band = metrics?.severity_band ?? 'LOW'
  const bandStyle = riskStyle(band)

  return (
    <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
      {/* ---- Left: controls ---- */}
      <div className="space-y-4">
        <Panel title="Rock-Face Image Analysis" subtitle="Upload a bench or drone photo" bodyClass="p-3 space-y-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-7 text-center transition-colors ${
              dragging ? 'border-sky-500 bg-sky-500/10' : 'border-panel-600 hover:border-slate-600 hover:bg-panel-700/40'
            }`}
          >
            <Upload size={22} className="mx-auto text-slate-600" />
            <p className="mt-2 text-sm text-slate-300">Drop an image or click to browse</p>
            <p className="mt-0.5 text-[10px] text-slate-600">JPG · PNG · BMP · WEBP · TIFF — up to 12 MB</p>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                e.target.value = '' // allow re-selecting the same file
                analyze(f)
              }}
            />
          </div>

          <div>
            <p className="label-xs mb-1.5">Or run a bundled synthetic sample</p>
            <div className="grid grid-cols-3 gap-1.5">
              {SAMPLES.map((s) => (
                <button
                  key={s.file}
                  type="button"
                  disabled={running}
                  onClick={() => analyzeSample(s.file)}
                  className="rounded border border-panel-600 bg-panel-700/50 px-2 py-2 text-left transition-colors hover:bg-panel-600 disabled:opacity-40"
                >
                  <span className="block text-[11px] font-semibold text-slate-300">{s.label}</span>
                  <span className="block text-[9px] leading-tight text-slate-600">{s.hint}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2 border-t border-panel-600/70 pt-3">
            <label className="block">
              <span className="label-xs">Attribute to zone</span>
              <select
                value={zoneId}
                onChange={(e) => setZoneId(e.target.value)}
                className="mt-1 w-full rounded border border-panel-600 bg-panel-700 px-2 py-1.5 text-xs text-slate-200"
              >
                {zones.map((z) => (
                  <option key={z.zone_id} value={z.zone_id}>{z.zone_id} — {z.zone_name}</option>
                ))}
              </select>
            </label>
            <label className="flex items-start gap-2 text-[11px] text-slate-400">
              <input
                type="checkbox"
                checked={applyToZone}
                onChange={(e) => setApplyToZone(e.target.checked)}
                className="mt-0.5 accent-sky-500"
              />
              <span>
                Feed results into the live risk engine
                <span className="block text-[10px] text-slate-600">
                  Pushes measured crack density, severity and rock quality into that zone's sensor state.
                </span>
              </span>
            </label>
          </div>

          <ErrorNote message={error} />
        </Panel>

        <Panel title="Method" bodyClass="p-3">
          <div className="flex items-start gap-2 rounded border border-amber-500/25 bg-amber-500/5 px-2.5 py-2">
            <Info size={13} className="mt-0.5 shrink-0 text-amber-500" />
            <div className="space-y-1.5 text-[11px] leading-relaxed text-slate-400">
              <p>
                Detection uses a <strong className="text-slate-300">classical OpenCV pipeline</strong> — CLAHE
                contrast equalisation, black-hat morphology to isolate dark thin structures, percentile
                thresholding, then contour filtering by elongation.
              </p>
              <p>
                No trained crack model is bundled: there was no labelled open-pit dataset to train one on.
                Shadows, drill marks and wet streaks <em>can</em> be misread as fractures. Treat the numbers as
                indicative measurements, not verified geotechnical observations.
              </p>
            </div>
          </div>
        </Panel>

        <Panel title="Recent Analyses" bodyClass="p-2 space-y-1 max-h-64 overflow-y-auto">
          {history.length === 0 ? (
            <EmptyState icon={FileImage} title="No scans yet" />
          ) : (
            history.map((h) => (
              <div key={h.id} className="flex items-center gap-2 rounded px-2 py-1.5 hover:bg-panel-700/50">
                <ScanLine size={12} className="shrink-0 text-slate-600" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[11px] text-slate-300">{h.filename}</p>
                  <p className="font-mono text-[9px] text-slate-600">
                    {h.zone_id} · {formatDateTime(h.created_at)}
                  </p>
                </div>
                <span className={`shrink-0 font-mono text-xs ${riskStyle(h.metrics?.severity_band || 'LOW').text}`}>
                  {Math.round(h.crack_severity)}
                </span>
              </div>
            ))
          )}
        </Panel>
      </div>

      {/* ---- Right: results ---- */}
      <div className="space-y-4">
        <Panel
          title="Detection Output"
          subtitle={result ? `${result.filename} · detector: ${result.detector}` : 'Annotated rock face'}
          actions={result && <SimulatedTag>HEURISTIC CV</SimulatedTag>}
          bodyClass="p-3"
        >
          {running ? (
            <div className="relative overflow-hidden rounded-md border border-panel-600 bg-panel-900/60">
              {preview && <img src={preview} alt="Uploaded rock face" className="w-full opacity-30" />}
              <div className="absolute inset-0 grid place-items-center">
                <div className="text-center">
                  <ScanLine size={26} className="mx-auto animate-pulse text-sky-400" />
                  <p className="mt-2 text-xs text-slate-400">Running crack detection…</p>
                </div>
              </div>
              <div className="pointer-events-none absolute inset-x-0 top-0 h-0.5 animate-scan bg-sky-400/70" />
            </div>
          ) : result ? (
            <img
              src={result.annotated_image}
              alt="Rock face with detected cracks outlined"
              className="w-full rounded-md border border-panel-600"
            />
          ) : (
            <EmptyState
              icon={ScanLine}
              title="No image analysed yet"
              hint="Upload a rock-face photo or pick one of the bundled synthetic samples to run the detector."
            />
          )}
        </Panel>

        {result && (
          <>
            <Panel
              title="Fracture Measurements"
              actions={<RiskBadge level={band} score={metrics.crack_severity} size="sm" />}
              bodyClass="p-3"
            >
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <MetricTile label="Crack Severity" value={metrics.crack_severity.toFixed(1)} unit="/100" tone={bandStyle.text} />
                <MetricTile label="Crack Density" value={metrics.crack_density.toFixed(2)} unit="%" />
                <MetricTile label="Traces Found" value={metrics.crack_count} />
                <MetricTile label="Rock Quality" value={metrics.rock_condition.toFixed(0)} unit="/100" />
                <MetricTile label="Longest Trace" value={metrics.max_crack_length.toFixed(1)} unit="% frame" />
                <MetricTile label="Total Length" value={metrics.total_crack_length.toFixed(0)} unit="% frame" />
                <MetricTile label="Mean Width" value={metrics.mean_crack_width.toFixed(1)} unit="px" />
                <MetricTile label="Orientation Spread" value={metrics.orientation_spread.toFixed(0)} unit="/100" />
              </div>

              <ul className="mt-3 space-y-1">
                {result.notes.map((n) => (
                  <li key={n} className="flex items-start gap-1.5 text-[10px] leading-relaxed text-slate-500">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
                    {n}
                  </li>
                ))}
              </ul>
            </Panel>

            {result.zone_assessment && (
              <Panel
                title={`Resulting Risk — ${result.zone_assessment.zone_id}`}
                subtitle="Fed straight into the risk engine"
                actions={
                  <RiskBadge
                    level={result.zone_assessment.risk_level}
                    score={result.zone_assessment.risk_score}
                  />
                }
                bodyClass="p-3"
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="label-xs mb-1">Contributing factors</p>
                    {result.zone_assessment.contributions.slice(0, 5).map((f) => (
                      <FactorBar key={f.feature} factor={f} />
                    ))}
                  </div>
                  <div className="space-y-2">
                    <div>
                      <p className="label-xs mb-1">Recommended action</p>
                      <p className="rounded border border-panel-600/60 bg-panel-900/50 px-2.5 py-2 text-[11px] leading-relaxed text-slate-300">
                        {result.zone_assessment.recommended_action}
                      </p>
                    </div>
                    {result.alerts_raised.length > 0 && (
                      <div className="rounded border border-red-500/40 bg-red-500/10 px-2.5 py-2">
                        <p className="text-[11px] font-semibold text-red-300">
                          {result.alerts_raised.length} alert(s) raised from this analysis
                        </p>
                        <p className="mt-0.5 text-[10px] text-slate-400">{result.alerts_raised[0].title}</p>
                      </div>
                    )}
                  </div>
                </div>
              </Panel>
            )}
          </>
        )}

        {result && (
          <button
            type="button"
            onClick={() => { setResult(null); setError(null) }}
            className="btn-ghost w-full text-xs"
          >
            <X size={12} /> Clear result
          </button>
        )}
      </div>
    </div>
  )
}
