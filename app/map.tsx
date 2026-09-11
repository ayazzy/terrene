'use client';
import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Checkbox } from '@/components/ui/checkbox';
import { Layers, LocateFixed, ArrowUpRight } from 'lucide-react';
import type { Geometry, Polygon, LineString, Position } from 'geojson';
import type { OverlayFinding } from './site-evidence';
import { layerGroup, layerColor } from './site-evidence';
import type { ScreeningMapFeatures } from './screening-context';
import type { MapInspection } from './site-workspace-state';
type Props = {
  geometry: Geometry | null;
  findings?: OverlayFinding[];
  selected?: string;
  draw?: boolean;
  focusRequest?: number;
  boundaryLabel?: string;
  screeningMap?: ScreeningMapFeatures | null;
  onInspect?: (finding: MapInspection) => void;
  onDraw?: (g: Polygon) => void;
};
export default function SiteMap({
  geometry,
  findings = [],
  selected,
  draw = false,
  onDraw,
  focusRequest,
  boundaryLabel = 'Site boundary',
  screeningMap,
  onInspect,
}: Props) {
  const el = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null);
  const [projection, setProjection] = useState<maplibregl.Map | null>(null),
    [points, setPoints] = useState<number[][]>([]),
    [revision, setRevision] = useState(0),
    [base, setBase] = useState(true),
    [hiddenLayers, setHiddenLayers] = useState<
      Record<string, number | undefined>
    >({}),
    [layersOpen, setLayersOpen] = useState(false),
    [coordinates, setCoordinates] = useState(''),
    [error, setError] = useState('');
  const drawRef = useRef(draw);
  const overlay = useRef<SVGSVGElement>(null);
  const inspectRef = useRef({ findings, screeningMap, onInspect });
  useEffect(() => {
    inspectRef.current = { findings, screeningMap, onInspect };
  }, [findings, screeningMap, onInspect]);
  const ready = !!projection;
  const isVisible = (key: string) =>
    !(key in hiddenLayers) ||
    (selected === key && hiddenLayers[key] !== focusRequest);
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
        const hits = [
          ...(overlay.current?.querySelectorAll<SVGGeometryElement>(
            '[data-layer]:not([data-layer="site"])',
          ) || []),
        ]
          .reverse()
          .filter(
            (element) =>
              element.isPointInFill(new DOMPoint(e.point.x, e.point.y)) ||
              element.isPointInStroke(new DOMPoint(e.point.x, e.point.y)),
          );
        const hit = hits.find((element) => element.dataset.feature) || hits[0];
        const feature = inspectRef.current.screeningMap?.features.find(
          (item) => item.id === hit?.dataset.feature,
        );
        const finding = inspectRef.current.findings.find(
          (f) => f.key === hit?.dataset.layer,
        );
        const item = feature || finding;
        if (item) inspectRef.current.onInspect?.(item);
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
      const f = inspectRef.current.findings.find((f) => f.key === selected);
      const layerId = selected?.startsWith('context:') ? selected.slice(8) : '';
      const features =
        inspectRef.current.screeningMap?.features.filter(
          (item) => item.properties.layer_id === layerId,
        ) || [];
      if (f?.geometry) fit(f.geometry);
      else if (features.length)
        fit({
          type: 'GeometryCollection',
          geometries: features.map((item) => item.geometry),
        });
    }
  }, [selected, focusRequest, ready, projection]);
  useEffect(() => {
    if (ready && map.current?.isStyleLoaded())
      map.current.setLayoutProperty(
        'base',
        'visibility',
        base ? 'visible' : 'none',
      );
  }, [base, ready, projection]);
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
  function point(g: Geometry) {
    if (g.type !== 'Point' || !projection || !ready) return null;
    return projection.project(g.coordinates as [number, number]);
  }
  const draft: LineString | null =
    points.length > 1 ? { type: 'LineString', coordinates: points } : null;
  return (
    <div className="map-wrap">
      <div ref={el} className="map-canvas" />
      <svg
        ref={overlay}
        className="geography-overlay"
        aria-label="Site boundary and measured overlaps"
        data-revision={revision}
      >
        {screeningMap?.features
          .filter((feature) =>
            isVisible(`context:${feature.properties.layer_id}`),
          )
          .map((feature) => {
            const key = `context:${feature.properties.layer_id}`;
            const selectedLayer = activeSelection === key;
            const position = point(feature.geometry);
            const title =
              feature.properties.name ||
              feature.properties.classification ||
              feature.properties.object_type.replaceAll('_', ' ');
            return position ? (
              <circle
                key={feature.id}
                data-layer={key}
                data-feature={feature.id}
                data-selected={selectedLayer}
                cx={position.x}
                cy={position.y}
                r={selectedLayer ? 7 : 5}
                fill={layerColor(key)}
                stroke="white"
                strokeWidth="2"
              >
                <title>{title}</title>
              </circle>
            ) : (
              <path
                key={feature.id}
                data-layer={key}
                data-feature={feature.id}
                data-selected={selectedLayer}
                d={path(feature.geometry)}
                fill={layerColor(key)}
                fillOpacity={selectedLayer ? 0.42 : 0.22}
                stroke={layerColor(key)}
                strokeWidth={selectedLayer ? 3 : 1.5}
                fillRule="evenodd"
              >
                <title>{title}</title>
              </path>
            );
          })}
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
        {geometry && (
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
          aria-controls="environmental-layers"
          onClick={() => setLayersOpen((value) => !value)}
        >
          <Layers size={16} /> Layers{' '}
          <span className="layer-count">
            {findings.filter((f) => f.geometry && isVisible(f.key)).length +
              (screeningMap?.layers.filter(
                (layer) =>
                  layer.feature_count && isVisible(`context:${layer.id}`),
              ).length || 0)}
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
          id="environmental-layers"
          className="layer-control"
          aria-label="Environmental layers"
        >
          <div className="layer-control-title">
            <strong>Environmental layers</strong>
            <button className="text-btn" onClick={() => setLayersOpen(false)}>
              Close
            </button>
          </div>
          <p>Saved intersections · inside this boundary</p>
          <label className="base-layer" htmlFor="map-basemap">
            <Checkbox
              id="map-basemap"
              checked={base}
              onCheckedChange={(v) => setBase(!!v)}
            />{' '}
            OpenStreetMap basemap
          </label>
          {[...new Set(findings.map((f) => layerGroup(f.key)))].map((group) => (
            <div className="layer-group" key={group}>
              <h3>{group}</h3>
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
                          setHiddenLayers((keys) => {
                            const next = { ...keys };
                            if (value) delete next[f.key];
                            else next[f.key] = focusRequest;
                            return next;
                          })
                        }
                      />
                      <i
                        className="layer-swatch"
                        style={{ background: layerColor(f.key) }}
                      />
                      <span>
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
          ))}
          {!!screeningMap?.layers.length && (
            <div className="layer-group">
              <h3>Built world & transport</h3>
              {screeningMap.layers.map((layer) => {
                const key = `context:${layer.id}`;
                return (
                  <div className="layer-row" key={layer.id}>
                    <label htmlFor={`layer-${key}`}>
                      <Checkbox
                        id={`layer-${key}`}
                        aria-label={`Show ${layer.id.replaceAll('_', ' ')}`}
                        disabled={!layer.feature_count}
                        checked={!!layer.feature_count && isVisible(key)}
                        onCheckedChange={(value) =>
                          setHiddenLayers((keys) => {
                            const next = { ...keys };
                            if (value) delete next[key];
                            else next[key] = focusRequest;
                            return next;
                          })
                        }
                      />
                      <i
                        className="layer-swatch"
                        style={{ background: layerColor(key) }}
                      />
                      <span>
                        {layer.id.replaceAll('_', ' ')}
                        <small>
                          {layer.feature_count || 'No'} mapped object
                          {layer.feature_count === 1 ? '' : 's'} ·{' '}
                          {layer.state.replaceAll('_', ' ')}
                        </small>
                      </span>
                    </label>
                  </div>
                );
              })}
            </div>
          )}
          {!findings.length && (
            <p>
              Create a new assessment to obtain saved reference-layer
              observations.
            </p>
          )}
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
        (findings.find(
          (f) => f.key === selected && f.geometry && isVisible(f.key),
        ) ||
          screeningMap?.features.some(
            (feature) =>
              `context:${feature.properties.layer_id}` === selected &&
              isVisible(selected),
          )) && (
          <div className="map-selection">
            <i
              className="layer-swatch"
              style={{ background: layerColor(selected) }}
            />
            <span>
              Highlighted:{' '}
              {findings.find((f) => f.key === selected)?.dataset ||
                selected.replace('context:', '').replaceAll('_', ' ')}
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
