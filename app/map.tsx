'use client';
import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Checkbox } from '@/components/ui/checkbox';
type Props = {
  geometry: any;
  findings?: any[];
  selected?: string;
  draw?: boolean;
  onDraw?: (g: any) => void;
};
export default function SiteMap({
  geometry,
  findings = [],
  selected,
  draw = false,
  onDraw,
}: Props) {
  const el = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null),
    points = useRef<number[][]>([]);
  const [ready, setReady] = useState(false),
    [revision, setRevision] = useState(0),
    [base, setBase] = useState(true),
    [layers, setLayers] = useState(true),
    [error, setError] = useState('');
  const drawRef = useRef(draw);
  drawRef.current = draw;
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
    m.on('load', () => setReady(true));
    m.on('move', repaint);
    m.on('resize', repaint);
    m.on('error', () =>
      setError(
        'Some basemap tiles could not load. Boundary and evidence remain available.',
      ),
    );
    m.on('click', (e) => {
      if (drawRef.current) {
        points.current.push([e.lngLat.lng, e.lngLat.lat]);
        repaint();
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
    points.current = [];
    repaint();
    if (map.current)
      map.current.getCanvas().style.cursor = draw ? 'crosshair' : '';
  }, [draw]);
  function fit(g: any) {
    const m = map.current;
    if (!m || !g) return;
    const bounds = new maplibregl.LngLatBounds();
    const walk = (v: any) => {
      if (typeof v[0] === 'number') bounds.extend(v as [number, number]);
      else v.forEach(walk);
    };
    if (g.coordinates) walk(g.coordinates);
    if (!bounds.isEmpty())
      m.fitBounds(bounds, { padding: 65, maxZoom: 16, duration: 400 });
  }
  useEffect(() => {
    if (ready) fit(geometry);
  }, [geometry, ready]);
  useEffect(() => {
    if (ready) {
      const f = findings.find((f) => f.key === selected);
      if (f?.geometry) fit(f.geometry);
    }
  }, [selected, ready]);
  useEffect(() => {
    if (ready)
      map.current?.setLayoutProperty(
        'base',
        'visibility',
        base ? 'visible' : 'none',
      );
  }, [base, ready]);
  // Exact bounded server geometries rendered in screen coordinates from MapLibre's
  // projection. SVG avoids blob-worker dependence and keeps overlays inspectable.
  function path(g: any): string {
    if (!g || !map.current || !ready) return '';
    const ring = (coords: number[][], close = true) =>
      coords
        .map((p, i) => {
          const q = map.current!.project(p as [number, number]);
          return (i ? 'L' : 'M') + q.x.toFixed(2) + ',' + q.y.toFixed(2);
        })
        .join(' ') + (close ? ' Z' : '');
    if (g.type === 'Polygon')
      return g.coordinates.map((r: any) => ring(r)).join(' ');
    if (g.type === 'MultiPolygon')
      return g.coordinates
        .flatMap((p: any) => p.map((r: any) => ring(r)))
        .join(' ');
    if (g.type === 'LineString') return ring(g.coordinates, false);
    if (g.type === 'GeometryCollection')
      return g.geometries.map(path).join(' ');
    return '';
  }
  const draft =
    points.current.length > 1
      ? { type: 'LineString', coordinates: points.current }
      : null;
  return (
    <div className="map-wrap">
      <div ref={el} className="map-canvas" />
      <svg
        className="geography-overlay"
        aria-label="Site boundary and measured overlaps"
        data-revision={revision}
      >
        {geometry && (
          <path
            data-layer="site"
            d={path(geometry)}
            fill="#18785b"
            fillOpacity=".12"
            stroke="#12634a"
            strokeWidth="3"
            fillRule="evenodd"
          />
        )}
        {layers &&
          findings
            .filter((f) => f.geometry)
            .map((f) => (
              <path
                key={f.key}
                data-layer={f.key}
                data-selected={selected === f.key}
                d={path(f.geometry)}
                fill={selected === f.key ? '#df951d' : '#d59538'}
                fillOpacity={
                  selected ? (selected === f.key ? 0.68 : 0.12) : 0.38
                }
                stroke="#a36918"
                strokeWidth={selected === f.key ? 3 : 1.5}
                fillRule="evenodd"
              />
            ))}
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
          points.current.map((p, i) => {
            const q = map.current!.project(p as [number, number]);
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
      <div className="map-label">
        OXFORDSHIRE <span>England pilot</span>
      </div>
      <div className="legend">
        <b>Map layers</b>
        <label>
          <Checkbox checked={base} onCheckedChange={(v) => setBase(!!v)} />{' '}
          Basemap
        </label>
        <label>
          <Checkbox checked={layers} onCheckedChange={(v) => setLayers(!!v)} />{' '}
          Evidence overlaps
        </label>
        <div>
          <i className="swatch boundary" /> Site boundary
        </div>
        <div>
          <i className="swatch overlap" /> Mapped overlap
        </div>
      </div>
      {draw && (
        <div className="draw-bar">
          <span>Click to place vertices · {points.current.length} points</span>
          <button
            disabled={!points.current.length}
            onClick={() => {
              points.current.pop();
              repaint();
            }}
          >
            Undo
          </button>
          <button
            disabled={points.current.length < 3}
            className="primary"
            onClick={() =>
              onDraw?.({
                type: 'Polygon',
                coordinates: [[...points.current, points.current[0]]],
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
