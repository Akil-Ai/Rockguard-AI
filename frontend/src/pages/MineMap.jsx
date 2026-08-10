import { useMemo, useState } from 'react'
import { MapContainer, Polygon, Popup, TileLayer, Tooltip as LeafletTooltip } from 'react-leaflet'
import { Layers, MapPin, Users, Wrench } from 'lucide-react'

import ScenarioControls from '../components/ScenarioControls'
import { FactorBar, Panel, RiskBadge, SimulatedTag, Spinner } from '../components/ui'
import { riskStyle } from '../lib/risk'
import { useApp } from '../store/AppContext'

// Two basemaps plus a no-network option. Tile servers need internet, and a demo
// laptop on venue wifi may not have it — "Offline grid" keeps the zone geometry
// and risk colouring fully usable with no tiles at all.
const BASEMAPS = {
  satellite: {
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
  },
  street: {
    label: 'Street',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
  offline: { label: 'Offline grid', url: null, attribution: '' },
}

function ZoneDetail({ zone }) {
  const s = riskStyle(zone.risk_level)
  return (
    <div className="space-y-3">
      <div className={`rounded-md border px-3 py-2.5 ${s.bg} ${s.border}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-bold text-slate-100">{zone.zone_id}</p>
            <p className="truncate text-[11px] text-slate-400">{zone.zone_name}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className={`stat-value text-2xl ${s.text}`}>{Math.round(zone.risk_score)}</p>
            <p className={`text-[9px] font-semibold uppercase tracking-wider ${s.text}`}>{zone.risk_level}</p>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-400">
          <span className="inline-flex items-center gap-1"><Users size={10} />{zone.personnel} personnel</span>
          <span className="inline-flex items-center gap-1"><Layers size={10} />Bench {zone.bench} · {zone.wall}</span>
        </div>
        <p className="mt-1.5 inline-flex items-start gap-1 text-[10px] text-slate-500">
          <Wrench size={10} className="mt-0.5 shrink-0" />
          {zone.equipment}
        </p>
      </div>

      <div>
        <p className="label-xs mb-1.5">Live sensor readings</p>
        <div className="grid grid-cols-2 gap-1.5">
          {[
            ['Rainfall', zone.sensors.rainfall, 'mm'],
            ['Humidity', zone.sensors.humidity, '%'],
            ['Vibration', zone.sensors.vibration, 'mm/s'],
            ['Slope', zone.sensors.slope_angle, '°'],
            ['Displacement', zone.sensors.displacement, 'mm'],
            ['Crack density', zone.sensors.crack_density, '%'],
          ].map(([label, value, unit]) => (
            <div key={label} className="rounded border border-panel-600/50 bg-panel-900/50 px-2 py-1.5">
              <p className="text-[9px] uppercase tracking-wider text-slate-500">{label}</p>
              <p className="stat-value text-sm text-slate-200">
                {value?.toFixed(1)}
                <span className="ml-0.5 text-[10px] font-normal text-slate-500">{unit}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <p className="label-xs mb-1">Contributing factors</p>
        {zone.contributions.slice(0, 4).map((f) => (
          <FactorBar key={f.feature} factor={f} />
        ))}
      </div>

      <div>
        <p className="label-xs mb-1">Recommended action</p>
        <p className="rounded border border-panel-600/60 bg-panel-900/50 px-2.5 py-2 text-[11px] leading-relaxed text-slate-300">
          {zone.recommended_action}
        </p>
      </div>
    </div>
  )
}

export default function MineMap() {
  const { zones, mine, overall } = useApp()
  const [selectedId, setSelectedId] = useState(null)
  const [basemap, setBasemap] = useState('satellite')

  const selected = useMemo(
    () => zones.find((z) => z.zone_id === selectedId) ?? zones[0] ?? null,
    [zones, selectedId],
  )

  if (!mine || zones.length === 0) return <Spinner label="Loading mine geometry" />

  const tiles = BASEMAPS[basemap]

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[1fr_340px]">
      <Panel
        title="Mine Map — Hazard Zones"
        subtitle={mine.name}
        actions={
          <div className="flex items-center gap-2">
            <SimulatedTag>SIMULATED SITE</SimulatedTag>
            <select
              value={basemap}
              onChange={(e) => setBasemap(e.target.value)}
              className="rounded border border-panel-600 bg-panel-700 px-2 py-1 text-[11px] text-slate-300"
              aria-label="Basemap style"
            >
              {Object.entries(BASEMAPS).map(([key, b]) => (
                <option key={key} value={key}>{b.label}</option>
              ))}
            </select>
          </div>
        }
        bodyClass="p-0"
      >
        {/* The legend is absolutely positioned against THIS wrapper, not the
            panel — the panel stretches to match the taller right-hand column,
            which would leave the legend floating below the map. */}
        <div className="relative h-[620px] w-full overflow-hidden rounded-b-lg">
          <MapContainer
            center={mine.center}
            zoom={15}
            scrollWheelZoom
            style={{ height: '100%', width: '100%' }}
          >
            {tiles.url && <TileLayer url={tiles.url} attribution={tiles.attribution} maxZoom={19} />}

            {/* Pit outline for context */}
            <Polygon
              positions={mine.outline}
              pathOptions={{ color: '#475569', weight: 1.5, dashArray: '6 6', fill: false }}
            />

            {zones.map((zone) => {
              const s = riskStyle(zone.risk_level)
              const isSelected = selected?.zone_id === zone.zone_id
              const isHot = zone.risk_level === 'HIGH' || zone.risk_level === 'CRITICAL'
              return (
                <Polygon
                  key={zone.zone_id}
                  positions={zone.polygon}
                  eventHandlers={{ click: () => setSelectedId(zone.zone_id) }}
                  pathOptions={{
                    color: s.hex,
                    weight: isSelected ? 3.5 : isHot ? 2.5 : 1.5,
                    fillColor: s.hex,
                    fillOpacity: isHot ? 0.45 : 0.22,
                    dashArray: zone.risk_level === 'CRITICAL' ? '8 5' : undefined,
                  }}
                >
                  <LeafletTooltip direction="center" permanent className="!border-0 !bg-transparent !shadow-none">
                    <span
                      className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
                      style={{ background: 'rgba(11,16,23,0.85)', color: s.hex }}
                    >
                      {zone.zone_id} · {Math.round(zone.risk_score)}
                    </span>
                  </LeafletTooltip>
                  <Popup>
                    <div className="min-w-[190px]">
                      <p className="text-sm font-bold">{zone.zone_id}</p>
                      <p className="text-[11px] text-slate-400">{zone.zone_name}</p>
                      <p className="my-1.5 font-mono text-lg" style={{ color: s.hex }}>
                        {Math.round(zone.risk_score)}/100 · {zone.risk_level}
                      </p>
                      <p className="text-[11px] leading-snug text-slate-300">{zone.recommended_action}</p>
                    </div>
                  </Popup>
                </Polygon>
              )
            })}
          </MapContainer>

          {/* Legend */}
          <div className="pointer-events-none absolute bottom-4 left-4 z-[400] rounded-md border border-panel-600/70 bg-panel-900/90 px-3 py-2 backdrop-blur">
            <p className="label-xs mb-1.5">Hazard level</p>
            <div className="space-y-1">
              {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((lvl) => {
                const s = riskStyle(lvl)
                const count = zones.filter((z) => z.risk_level === lvl).length
                return (
                  <div key={lvl} className="flex items-center gap-2 text-[10px]">
                    <span className="h-2.5 w-4 rounded-sm" style={{ background: s.hex, opacity: 0.65 }} />
                    <span className="text-slate-400">{lvl}</span>
                    <span className="ml-auto font-mono text-slate-500">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </Panel>

      <div className="space-y-4">
        <Panel title="Zone Detail" subtitle="Click a zone on the map" bodyClass="p-3">
          {selected ? <ZoneDetail zone={selected} /> : <Spinner />}
        </Panel>

        <Panel title="Zone Index" bodyClass="p-2 space-y-1">
          {[...zones].sort((a, b) => b.risk_score - a.risk_score).map((z) => {
            const s = riskStyle(z.risk_level)
            const active = selected?.zone_id === z.zone_id
            return (
              <button
                key={z.zone_id}
                type="button"
                onClick={() => setSelectedId(z.zone_id)}
                className={`flex w-full items-center gap-2 rounded px-2.5 py-2 text-left transition-colors ${
                  active ? 'bg-panel-600/60 ring-1 ring-inset ring-sky-500/30' : 'hover:bg-panel-700/60'
                }`}
              >
                <MapPin size={12} style={{ color: s.hex }} className="shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold text-slate-200">{z.zone_id}</span>
                  <span className="block truncate text-[10px] text-slate-500">{z.zone_name}</span>
                </span>
                <RiskBadge level={z.risk_level} score={z.risk_score} size="sm" />
              </button>
            )
          })}
        </Panel>

        <Panel title="Scenario Simulator" bodyClass="p-3">
          <ScenarioControls compact />
          {overall && (
            <p className="mt-3 text-[10px] leading-relaxed text-slate-600">
              Mine-wide risk is currently {Math.round(overall.risk_score)}/100 ({overall.risk_level}).
              Zone colours update automatically as the simulated conditions change.
            </p>
          )}
        </Panel>
      </div>
    </div>
  )
}
