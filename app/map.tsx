'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Checkbox } from '@/components/ui/checkbox';
import { Layers, LocateFixed, ArrowUpRight } from 'lucide-react';
import type { Geometry, Polygon, LineString, Position } from 'geojson';
import type { OverlayFinding } from './site-evidence';
import { layerGroup, layerColor } from './site-evidence';
import {
  builtWorldLayerIds,
  mapFeatureName,
  mapLayerLabel,
  mapLayerStatus,
  type BuiltWorldLayerId,
  type ScreeningMapFeatures,
} from './screening-map-features';
type Props = {
  geometry: Geometry | null;
  findings?: OverlayFinding[];
  selected?: string;
  draw?: boolean;
  focusRequest?: number;
  boundaryLabel?: string;
  onInspect?: (finding: OverlayFinding) => void;
  onDraw?: (g: Polygon) => void;
  screeningFeatures?: ScreeningMapFeatures | null;
  screeningFeaturesState?:
    | 'idle'
    | 'loading'
    | 'available'
    | 'failed'
    | 'unavailable'
    | 'unsupported';
  screeningFeaturesError?: string;
  selectedMapObject?: string | null;
  mapObjectFocusRequest?: number;
  onInspectMapObject?: (id: string) => void;
  onClearMapObject?: () => void;
  hiddenLayerIds?: string[];
  onHiddenLayerIdsChange?: (ids: string[]) => void;
};
export default function SiteMap({
  geometry,
  findings = [],
  selected,
  draw = false,
  onDraw,
  focusRequest,
  boundaryLabel = 'Site boundary',
  onInspect,
  screeningFeatures,
  screeningFeaturesState = 'idle',
  screeningFeaturesError = '',
  selectedMapObject,
  mapObjectFocusRequest = 0,
  onInspectMapObject,
  onClearMapObject,
  hiddenLayerIds,
  onHiddenLayerIdsChange,
}: Props) {
  const el = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null);
  const [projection, setProjection] = useState<maplibregl.Map | null>(null),
    [points, setPoints] = useState<number[][]>([]),
    [revision, setRevision] = useState(0),
    [localHiddenLayerIds, setLocalHiddenLayerIds] = useState<string[]>([]),
    [layersOpen, setLayersOpen] = useState(false),
    [coordinates, setCoordinates] = useState(''),
    [error, setError] = useState('');
  const drawRef = useRef(draw);
  const lastOverlayFocus = useRef('');
  const overlay = useRef<SVGSVGElement>(null);
  const inspectRef = useRef({ findings, onInspect });
  const builtWorldRef = useRef({
    screeningFeatures,
    onInspectMapObject,
    selectedMapObject,
  });
  useEffect(() => {
    inspectRef.current = { findings, onInspect };
  }, [findings, onInspect]);
  useEffect(() => {
    builtWorldRef.current = {
      screeningFeatures,
      onInspectMapObject,
      selectedMapObject,
    };
  }, [screeningFeatures, onInspectMapObject, selectedMapObject]);
  const ready = !!projection;
  const effectiveHiddenLayerIds = hiddenLayerIds ?? localHiddenLayerIds;
  const hiddenLayerSet = useMemo(
    () => new Set(effectiveHiddenLayerIds),
    [effectiveHiddenLayerIds],
  );
  const setLayerHidden = useCallback(
    (id: string, hidden: boolean) => {
      const next = hidden
        ? [...new Set([...effectiveHiddenLayerIds, id])]
        : effectiveHiddenLayerIds.filter((item) => item !== id);
      if (hiddenLayerIds === undefined) setLocalHiddenLayerIds(next);
      onHiddenLayerIdsChange?.(next);
    },
    [effectiveHiddenLayerIds, hiddenLayerIds, onHiddenLayerIdsChange],
  );
  const isVisible = (key: string) =>
    !hiddenLayerSet.has(`environment:${key}`);
  const activeSelection =
    selected && isVisible(selected) ? selected : undefined;
  const repaint = () => setRevision((v) => v + 1);
  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: {
        version: 8,
        sources: {
          base: {
            type: 'raster',
            tiles: [
              process.env.NEXT_PUBLIC_BASEMAP_URL ||
                'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#e9efec' },
          },
          {
            id: 'base',
            type: 'raster',
            source: 'base',
            paint: { 'raster-saturation': -0.7, 'raster-opacity': 0.8 },
          },
        ],
      },
      center: [-1.29, 51.78],
      zoom: 10,
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl(), 'top-right');
    m.addControl(
      new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }),
      'bottom-right',
    );
    m.on('mousemove', (e) =>
      setCoordinates(
        `${Math.abs(e.lngLat.lat).toFixed(5)}° ${e.lngLat.lat >= 0 ? 'N' : 'S'} · ${Math.abs(e.lngLat.lng).toFixed(5)}° ${e.lngLat.lng >= 0 ? 'E' : 'W'}`,
      ),
    );
    m.on('load', () => setProjection(m));
    m.on('move', repaint);
    m.on('resize', repaint);
    m.on('error', () =>
      setError(
        'Some basemap tiles could not load. Boundary and evidence remain available.',
      ),
    );
    m.on('click', (e) => {
      if (drawRef.current) {
        setPoints((vertices) => [...vertices, [e.lngLat.lng, e.lngLat.lat]]);
      } else {
        // Hit-test the projected evidence on click without intercepting map drag/zoom.
        const hit = [
          ...(overlay.current?.querySelectorAll<SVGGeometryElement>(
            '[data-map-object], path[data-layer]:not([data-layer="site"])',
          ) || []),
        ]
          .reverse()
          .find(
            (element) =>
              element.isPointInFill(new DOMPoint(e.point.x, e.point.y)) ||
              element.isPointInStroke(new DOMPoint(e.point.x, e.point.y)),
          );
        const objectId = hit?.dataset.mapObject;
        if (objectId) builtWorldRef.current.onInspectMapObject?.(objectId);
        else {
          const finding = inspectRef.current.findings.find(
            (f) => f.key === hit?.dataset.layer,
          );
          if (finding) inspectRef.current.onInspect?.(finding);
        }
      }
    });
    const observer = new ResizeObserver(() => m.resize());
    observer.observe(el.current);
    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    drawRef.current = draw;
    if (map.current)
      map.current.getCanvas().style.cursor = draw ? 'crosshair' : '';
  }, [draw]);
  function fit(g: Geometry | null) {
    const m = map.current;
    if (!m || !g) return;
    const bounds = new maplibregl.LngLatBounds();
    const walk = (v: Position | Position[] | Position[][] | Position[][][]) => {
      if (typeof v[0] === 'number') bounds.extend(v as [number, number]);
      else (v as (Position | Position[] | Position[][])[]).forEach(walk);
    };
    if ('coordinates' in g) walk(g.coordinates);
    if (!bounds.isEmpty())
      m.fitBounds(bounds, { padding: 65, maxZoom: 16, duration: 400 });
  }
  useEffect(() => {
    if (ready) fit(geometry);
  }, [geometry, ready, projection]);
  useEffect(() => {
    if (ready) {
      const focusKey = `${selected ?? ''}:${focusRequest}`;
      if (lastOverlayFocus.current === focusKey) return;
      lastOverlayFocus.current = focusKey;
      const f = inspectRef.current.findings.find((f) => f.key === selected);
      if (f?.geometry) {
        const layerId = `environment:${f.key}`;
        if (hiddenLayerSet.has(layerId)) setLayerHidden(layerId, false);
        fit(f.geometry);
      }
    }
    // A new focus request intentionally reveals the exact retained overlay.
    // The external URL state is updated through setLayerHidden when controlled.
  }, [
    selected,
    focusRequest,
    ready,
    projection,
    hiddenLayerSet,
    setLayerHidden,
  ]);
  useEffect(() => {
    if (!ready || !mapObjectFocusRequest) return;
    const feature = builtWorldRef.current.screeningFeatures?.features.find(
      (item) => item.id === builtWorldRef.current.selectedMapObject,
    );
    if (feature) fit(feature.geometry);
  }, [mapObjectFocusRequest, ready, projection]);
  useEffect(() => {
    if (ready && map.current?.isStyleLoaded())
      map.current.setLayoutProperty(
        'base',
        'visibility',
        hiddenLayerSet.has('basemap') ? 'none' : 'visible',
      );
  }, [hiddenLayerSet, ready, projection]);
  // Exact bounded server geometries rendered in screen coordinates from MapLibre's
  // projection. SVG avoids blob-worker dependence and keeps overlays inspectable.
  function path(g: Geometry | null): string {
    if (!g || !projection || !ready) return '';
    const ring = (coords: number[][], close = true) =>
      coords
        .map((p, i) => {
          const q = projection!.project(p as [number, number]);
          return (i ? 'L' : 'M') + q.x.toFixed(2) + ',' + q.y.toFixed(2);
        })
        .join(' ') + (close ? ' Z' : '');
    if (g.type === 'Polygon')
      return g.coordinates.map((r) => ring(r)).join(' ');
    if (g.type === 'MultiPolygon')
      return g.coordinates.flatMap((p) => p.map((r) => ring(r))).join(' ');
    if (g.type === 'LineString') return ring(g.coordinates, false);
    if (g.type === 'MultiLineString')
      return g.coordinates.map((r: number[][]) => ring(r, false)).join(' ');
    if (g.type === 'GeometryCollection')
      return g.geometries.map(path).join(' ');
    return '';
  }
  const draft: LineString | null =
    points.length > 1 ? { type: 'LineString', coordinates: points } : null;
  const builtFeatures = (screeningFeatures?.features || []).filter((feature) =>
    screeningFeatures?.layers.some(
      (layer) =>
        layer.id === feature.properties.layer_id &&
        (layer.state === 'available' || layer.state === 'partial'),
    ),
  );
  const builtLayerColor = (layer: BuiltWorldLayerId) =>
    ({
      buildings: '#8a633e',
      functional_sites: '#65756b',
      railway_tracks: '#7b4654',
      railway_stations: '#304f47',
    })[layer];
  const builtLayerVisible = (layer: BuiltWorldLayerId) =>
    !hiddenLayerSet.has(`built:${layer}`);
  function renderBuiltFeature(feature: (typeof builtFeatures)[number]) {
    const layer = feature.properties.layer_id;
    if (!builtLayerVisible(layer)) return null;
    const isSelected = selectedMapObject === feature.id;
    const geometry = feature.geometry;
    if (geometry.type === 'Point' || geometry.type === 'MultiPoint') {
      const positions =
        geometry.type === 'Point'
          ? [geometry.coordinates]
          : geometry.coordinates;
      return positions.map((position, index) => {
        if (!projection) return null;
        const point = projection.project(position as [number, number]);
        return (
          <circle
            key={`${feature.id}:${index}`}
            data-map-object={feature.id}
            cx={point.x}
            cy={point.y}
            r={isSelected ? 7 : 5}
            fill={builtLayerColor(layer)}
            stroke="white"
            strokeWidth={isSelected ? 3 : 2}
          >
            <title>
              {mapFeatureName(feature)} · Terrene Earth mapped object
            </title>
          </circle>
        );
      });
    }
    return (
      <path
        key={feature.id}
        data-map-object={feature.id}
        data-map-layer={layer}
        data-selected={isSelected}
        d={path(geometry)}
        fill={
          geometry.type.includes('Polygon') ? builtLayerColor(layer) : 'none'
        }
        fillOpacity={isSelected ? 0.5 : 0.3}
        stroke={builtLayerColor(layer)}
        strokeWidth={isSelected ? 4 : layer === 'railway_tracks' ? 2.5 : 1.75}
        strokeDasharray={layer === 'railway_tracks' ? '5 3' : undefined}
        fillRule="evenodd"
      >
        <title>{mapFeatureName(feature)} · Terrene Earth mapped object</title>
      </path>
    );
  }
  return (
    <div className="map-wrap">
      <div ref={el} className="map-canvas" />
      <svg
        ref={overlay}
        className="geography-overlay"
        aria-label="Site boundary and measured overlaps"
        data-revision={revision}
      >
        {findings
          .filter((f) => f.geometry && isVisible(f.key))
          .map((f) => (
            <path
              key={f.key}
              data-layer={f.key}
              data-selected={activeSelection === f.key}
              d={path(f.geometry)}
              fill={layerColor(f.key)}
              fillOpacity={
                activeSelection
                  ? activeSelection === f.key
                    ? 0.36
                    : 0.08
                  : 0.2
              }
              stroke={layerColor(f.key)}
              strokeWidth={activeSelection === f.key ? 3 : 1.5}
              fillRule="evenodd"
            >
              <title>
                {f.dataset} · {f.percent ?? 0}% overlap
              </title>
            </path>
          ))}
        {builtFeatures.map(renderBuiltFeature)}
        {geometry && !hiddenLayerSet.has('site-boundary') && (
          <path
            data-layer="site"
            d={path(geometry)}
            fill="var(--wetland)"
            fillOpacity=".05"
            stroke="var(--action-primary)"
            strokeWidth="3"
            fillRule="evenodd"
          />
        )}
        {draft && (
          <path
            d={path(draft)}
            fill="none"
            stroke="#2549b4"
            strokeWidth="3"
            strokeDasharray="6 3"
          />
        )}
        {draw &&
          ready &&
          points.map((p, i) => {
            const q = projection!.project(p as [number, number]);
            return (
              <circle
                key={i}
                cx={q.x}
                cy={q.y}
                r="4"
                fill="#2549b4"
                stroke="white"
                strokeWidth="2"
              />
            );
          })}
      </svg>
      {error && <div className="map-error">{error}</div>}
      <div className="map-toolbar">
        <button
          aria-expanded={layersOpen}
          aria-controls="map-layers"
          onClick={() => setLayersOpen((value) => !value)}
        >
          <Layers size={16} /> Layers{' '}
          <span className="layer-count">
            {findings.filter((f) => f.geometry && isVisible(f.key)).length +
              builtWorldLayerIds.filter((layer) =>
                builtFeatures.some(
                  (feature) =>
                    feature.properties.layer_id === layer &&
                    builtLayerVisible(layer),
                ),
              ).length}
          </span>
        </button>
        <button
          aria-label="Fit site boundary"
          title="Fit site boundary"
          disabled={!geometry}
          onClick={() => fit(geometry)}
        >
          <LocateFixed size={17} />
        </button>
      </div>
      {layersOpen && (
        <section
          id="map-layers"
          className="layer-control"
          aria-label="Map layers"
        >
          <div className="layer-control-title">
            <strong>Map layers</strong>
            <button className="text-btn" onClick={() => setLayersOpen(false)}>
              Close
            </button>
          </div>
          <p>Saved evidence for the selected immutable assessment.</p>
          <label className="base-layer" htmlFor="map-basemap">
            <Checkbox
              id="map-basemap"
              checked={!hiddenLayerSet.has('basemap')}
              onCheckedChange={(value) => setLayerHidden('basemap', !value)}
            />{' '}
            OpenStreetMap basemap
          </label>
          <div className="layer-group">
            <h3>Site</h3>
            <div className="layer-row">
              <label htmlFor="map-site-boundary">
                <Checkbox
                  id="map-site-boundary"
                  checked={!hiddenLayerSet.has('site-boundary')}
                  disabled={!geometry}
                  onCheckedChange={(value) =>
                    setLayerHidden('site-boundary', !value)
                  }
                />
                <i className="layer-swatch boundary" />
                <span className="layer-row-copy">
                  Site boundary
                  <small>{geometry ? boundaryLabel : 'Unavailable'}</small>
                </span>
              </label>
            </div>
          </div>
          <div className="layer-group">
            <h3>Environmental evidence</h3>
            {[...new Set(findings.map((f) => layerGroup(f.key)))].map(
              (group) => (
                <div className="layer-subgroup" key={group}>
                  <h4>{group}</h4>
                  {findings
                    .filter((f) => layerGroup(f.key) === group)
                    .map((f) => (
                      <div className="layer-row" key={f.key}>
                        <label htmlFor={`layer-${f.key}`}>
                          <Checkbox
                            id={`layer-${f.key}`}
                            aria-label={`Show ${f.dataset}`}
                            disabled={!f.geometry}
                            checked={!!f.geometry && isVisible(f.key)}
                            onCheckedChange={(value) =>
                              setLayerHidden(`environment:${f.key}`, !value)
                            }
                          />
                          <i
                            className="layer-swatch"
                            style={{ background: layerColor(f.key) }}
                          />
                          <span className="layer-row-copy">
                            {f.dataset}
                            <small>
                              {f.measured === null
                                ? 'Evidence unavailable'
                                : !f.geometry
                                  ? 'No mapped overlap'
                                  : `${f.percent ?? 0}% overlap`}
                            </small>
                          </span>
                        </label>
                        <button
                          className="icon-btn"
                          aria-label={`Inspect ${f.dataset} evidence`}
                          onClick={() => onInspect?.(f)}
                        >
                          <ArrowUpRight size={14} />
                        </button>
                      </div>
                    ))}
                </div>
              ),
            )}
            {!findings.length && (
              <p>No saved displayable environmental overlays.</p>
            )}
          </div>
          <div className="layer-group terrene-map-layers">
            <h3>Terrene Earth · built world</h3>
            {screeningFeaturesState === 'loading' && (
              <p>Loading persisted mapped objects…</p>
            )}
            {screeningFeaturesState === 'failed' && (
              <p role="alert">
                Built-world layers could not be loaded. Missing map data is not
                reported as zero. {screeningFeaturesError}
              </p>
            )}
            {screeningFeaturesState === 'unsupported' && (
              <p>
                This historical evidence does not support persisted built-world
                objects. Current objects are not substituted.
              </p>
            )}
            {screeningFeaturesState === 'unavailable' && (
              <p>
                No built-world map evidence is stored for this assessment.
                Missing evidence is not reported as zero.
              </p>
            )}
            {screeningFeatures
              ? screeningFeatures.layers.map((layer) => {
                  const enabled =
                    layer.feature_count > 0 &&
                    (layer.state === 'available' || layer.state === 'partial');
                  return (
                    <div className="layer-row" key={layer.id}>
                      <label htmlFor={`map-built-${layer.id}`}>
                        <Checkbox
                          id={`map-built-${layer.id}`}
                          aria-label={`Show ${mapLayerLabel(layer.id)}`}
                          disabled={!enabled}
                          checked={enabled && builtLayerVisible(layer.id)}
                          onCheckedChange={(value) => {
                            setLayerHidden(`built:${layer.id}`, !value);
                            if (
                              !value &&
                              builtFeatures.some(
                                (feature) =>
                                  feature.id === selectedMapObject &&
                                  feature.properties.layer_id === layer.id,
                              )
                            )
                              onClearMapObject?.();
                          }}
                        />
                        <i
                          className="layer-swatch terrene-layer-swatch"
                          style={{ background: builtLayerColor(layer.id) }}
                        />
                        <span className="layer-row-copy">
                          {mapLayerLabel(layer.id)}
                          <small className={`layer-state state-${layer.state}`}>
                            {mapLayerStatus(layer)}
                          </small>
                        </span>
                      </label>
                    </div>
                  );
                })
              : ![
                    'loading',
                    'failed',
                    'unavailable',
                    'unsupported',
                  ].includes(screeningFeaturesState) && (
                  <p>
                    {screeningFeaturesState === 'idle'
                      ? 'Prepare or select a supported Screening Context run to inspect built-world layers.'
                      : 'Layer availability is unavailable.'}
                  </p>
                )}
            {screeningFeatures && (
              <p className="terrene-source-note">
                Generalised source mapping—not surveyed, cadastral, legal or
                engineering geometry.
              </p>
            )}
          </div>
          <p className="layer-footnote">
            Terrain, watercourse and land-cover measurements are inspectable in
            analysis. No displayable layers are retained for those inputs.
          </p>
        </section>
      )}
      <div className="map-boundary-label">
        <i className="swatch boundary" />
        {boundaryLabel}
        <small>{coordinates || 'WGS84 · EPSG:4326'}</small>
      </div>
      {selected &&
        findings.find(
          (f) => f.key === selected && f.geometry && isVisible(f.key),
        ) && (
          <div className="map-selection">
            <i
              className="layer-swatch"
              style={{ background: layerColor(selected) }}
            />
            <span>
              Highlighted: {findings.find((f) => f.key === selected)?.dataset}
            </span>
          </div>
        )}
      {selectedMapObject &&
        builtFeatures.some(
          (feature) =>
            feature.id === selectedMapObject &&
            builtLayerVisible(feature.properties.layer_id),
        ) && (
          <div className="map-selection map-object-selection">
            <i
              className="layer-swatch terrene-layer-swatch"
              style={{
                background: builtLayerColor(
                  builtFeatures.find(
                    (feature) => feature.id === selectedMapObject,
                  )!.properties.layer_id,
                ),
              }}
            />
            <span>
              Selected:{' '}
              {mapFeatureName(
                builtFeatures.find(
                  (feature) => feature.id === selectedMapObject,
                )!,
              )}
            </span>
          </div>
        )}
      {draw && (
        <div className="draw-bar">
          <span>Click to place vertices · {points.length} points</span>
          <button
            disabled={!points.length}
            onClick={() => {
              setPoints((vertices) => vertices.slice(0, -1));
            }}
          >
            Undo
          </button>
          <button
            disabled={points.length < 3}
            className="primary"
            onClick={() =>
              onDraw?.({
                type: 'Polygon',
                coordinates: [[...points, points[0]]],
              })
            }
          >
            Finish boundary
          </button>
        </div>
      )}
    </div>
  );
}
