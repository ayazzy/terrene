'use client';
import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ArrowUpRight, LocateFixed, Minus, Plus, X } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  geometryPositions,
  portfolioBounds,
  projectedBoundary,
  type SavedMapSite,
} from './portfolio-geometry';

function siteArea(site: SavedMapSite) {
  const area = site.assessment?.result?.area_ha;
  if (
    site.assessment?.version !== site.version ||
    typeof area !== 'number' ||
    !Number.isFinite(area)
  )
    return 'Area unavailable';
  return `${area.toLocaleString('en-GB', { maximumFractionDigits: 1 })} ha`;
}

type Props = {
  sites: SavedMapSite[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  onOpen: (site: SavedMapSite) => void;
  loading: boolean;
  unavailable: boolean;
};

export default function PortfolioMap({
  sites,
  selected,
  onSelect,
  onOpen,
  loading,
  unavailable,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const overlay = useRef<SVGSVGElement>(null);
  const handlers = useRef({ onSelect, sites });
  const [projection, setProjection] = useState<maplibregl.Map | null>(null);
  const [revision, setRevision] = useState(0);
  const [hovered, setHovered] = useState<string | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    handlers.current = { onSelect, sites };
  }, [onSelect, sites]);
  const bounds = portfolioBounds(sites);
  const boundsKey = JSON.stringify(bounds);
  function fit(m = map.current) {
    const extent = portfolioBounds(handlers.current.sites);
    if (!m || !extent) return;
    const narrow = m.getContainer().clientWidth < 650;
    m.fitBounds(
      [
        [extent[0], extent[1]],
        [extent[2], extent[3]],
      ],
      {
        padding: {
          top: narrow ? 185 : 155,
          bottom: narrow ? 350 : 170,
          left: 65,
          right: 65,
        },
        maxZoom: 12,
        duration: 0,
      },
    );
  }
  useEffect(() => {
    if (!container.current) return;
    let m: maplibregl.Map;
    try {
      m = new maplibregl.Map({
        container: container.current,
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
              attribution:
                '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>',
            },
          },
          layers: [
            {
              id: 'background',
              type: 'background',
              paint: { 'background-color': '#eeeeee' },
            },
            {
              id: 'base',
              type: 'raster',
              source: 'base',
              // The configured source is raster, so global tone and opacity are
              // the only honest controls available without changing providers.
              paint: {
                'raster-saturation': -1,
                'raster-contrast': -0.12,
                'raster-opacity': 0.7,
                'raster-fade-duration': 0,
              },
            },
          ],
        },
        center: [-1.29, 51.78],
        zoom: 10,
        minZoom: 6,
        maxZoom: 18,
        renderWorldCopies: false,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        attributionControl: { compact: true },
      });
    } catch {
      queueMicrotask(() =>
        setError(
          'The map could not start. Choose a saved site below or use List view.',
        ),
      );
      return;
    }
    map.current = m;
    m.touchZoomRotate.disableRotation();
    const repaint = () => setRevision((value) => value + 1);
    function hit(point: { x: number; y: number }) {
      return [
        ...(overlay.current?.querySelectorAll<SVGPathElement>(
          'path[data-site-id]',
        ) || []),
      ]
        .reverse()
        .find(
          (path) =>
            path.isPointInFill(new DOMPoint(point.x, point.y)) ||
            path.isPointInStroke(new DOMPoint(point.x, point.y)),
        )?.dataset.siteId;
    }
    m.on('load', () => {
      setProjection(m);
      fit(m);
    });
    m.on('move', repaint);
    m.on('resize', repaint);
    m.on('click', (event) =>
      handlers.current.onSelect(hit(event.point) || null),
    );
    m.on('mousemove', (event) => {
      const id = hit(event.point);
      setHovered(id || null);
      m.getCanvas().style.cursor = id ? 'pointer' : '';
    });
    m.on('mouseout', () => setHovered(null));
    m.on('error', () =>
      setError(
        'Some basemap tiles could not load. Saved boundaries and site selection remain available.',
      ),
    );
    const observer = new ResizeObserver(() => m.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      m.remove();
      map.current = null;
    };
  }, []);
  useEffect(() => {
    if (projection) fit(projection);
  }, [boundsKey, projection]);
  const chosen = sites.find((site) => site.id === selected);
  const missing = sites.filter(
    (site) => !geometryPositions(site.geometry).length,
  ).length;
  // Paint selection last so overlapping parcels remain easy to distinguish.
  const ordered = [...sites].sort(
    (a, b) => Number(a.id === selected) - Number(b.id === selected),
  );
  return (
    <section
      className="portfolio-map"
      aria-label="Saved sites geographic overview"
    >
      <div ref={container} className="portfolio-canvas" />
      <svg
        ref={overlay}
        className="geography-overlay portfolio-boundaries"
        aria-label="Current saved site boundaries"
        data-revision={revision}
      >
        {projection &&
          ordered.map((site) => (
            <path
              key={site.id}
              data-site-id={site.id}
              data-selected={site.id === selected}
              data-hovered={site.id === hovered}
              d={projectedBoundary(site.geometry, (p) =>
                projection.project(p as [number, number]),
              )}
              fillRule="evenodd"
            >
              <title>
                {site.name} · {site.status} · Boundary v{site.version}
              </title>
            </path>
          ))}
      </svg>
      <div className="portfolio-pins" aria-label="Sites on map">
        {projection &&
          sites.map((site, index) => {
            // A real boundary vertex anchors the locator, including for concave parcels.
            const anchor = geometryPositions(site.geometry)[0];
            if (!anchor) return null;
            const p = projection.project(anchor as [number, number]);
            const mapWidth = projection.getContainer().clientWidth;
            const narrowLabel = mapWidth < 600;
            const contextVisible =
              hovered === site.id || selected === site.id;
            return (
              <button
                key={site.id}
                className="portfolio-pin"
                data-selected={site.id === selected}
                style={{ left: p.x, top: p.y }}
                aria-label={`Select ${site.name}`}
                aria-pressed={site.id === selected}
                aria-describedby={`portfolio-pin-context-${site.id}`}
                onClick={() => onSelect(site.id)}
                onFocus={() => setHovered(site.id)}
                onBlur={() => setHovered(null)}
                onMouseEnter={() => setHovered(site.id)}
                onMouseLeave={() => setHovered(null)}
              >
                <span>{String(index + 1).padStart(2, '0')}</span>
                <span
                  id={`portfolio-pin-context-${site.id}`}
                  className={`portfolio-pin-label${narrowLabel ? ' is-narrow' : ''}`}
                  data-visible={contextVisible}
                  data-side={
                    narrowLabel
                      ? 'below'
                      : p.x > mapWidth - 280
                        ? 'left'
                        : 'right'
                  }
                  data-align={
                    p.x < 128
                      ? 'start'
                      : p.x > mapWidth - 128
                        ? 'end'
                        : 'center'
                  }
                >
                  <strong>{site.name}</strong>
                  <small>
                    {siteArea(site)} <i>·</i> {site.status}
                  </small>
                </span>
              </button>
            );
          })}
      </div>
      <div className="portfolio-context">
        <h1>Oxfordshire pilot</h1>
        <p>
          {loading ? (
            'Loading saved sites…'
          ) : unavailable ? (
            'Saved sites unavailable'
          ) : (
            <>
              {sites.length} {sites.length === 1 ? 'site' : 'sites'}{' '}
              <span>·</span>{' '}
              {sites.filter((s) => s.status === 'Investigate').length} to
              investigate
            </>
          )}
        </p>
      </div>
      <div className="portfolio-controls" aria-label="Portfolio map controls">
        <button
          aria-label="Fit to saved sites"
          title="Fit to saved sites"
          disabled={!bounds || !projection}
          onClick={() => fit()}
        >
          <LocateFixed size={18} />
        </button>
        <button
          aria-label="Zoom in"
          title="Zoom in"
          disabled={!projection}
          onClick={() => map.current?.zoomIn({ duration: 0 })}
        >
          <Plus size={18} />
        </button>
        <button
          aria-label="Zoom out"
          title="Zoom out"
          disabled={!projection}
          onClick={() => map.current?.zoomOut({ duration: 0 })}
        >
          <Minus size={18} />
        </button>
      </div>
      <div className="portfolio-selection">
        {!!sites.length && (
          <Select
            value={selected || ''}
            onValueChange={(id) => id && onSelect(id)}
          >
            <SelectTrigger aria-label="Choose saved site">
              <SelectValue>
                {chosen ? chosen.name : 'Choose a saved site'}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {sites.map((site, index) => (
                <SelectItem value={site.id} key={site.id}>
                  {String(index + 1).padStart(2, '0')} · {site.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {chosen && (
          <article className="portfolio-site-card" aria-label="Selected site">
            <div className="portfolio-site-meta">
              <span>SELECTED SITE</span>
              <button
                aria-label="Clear site selection"
                onClick={() => onSelect(null)}
              >
                <X size={16} />
              </button>
            </div>
            <h2>{chosen.name}</h2>
            <p>
              Boundary v{chosen.version} <span>·</span>{' '}
              <span className="portfolio-review">{chosen.status}</span>
            </p>
            <button className="primary" onClick={() => onOpen(chosen)}>
              Open site analysis <ArrowUpRight size={16} />
            </button>
          </article>
        )}
        {!loading && !unavailable && !sites.length && (
          <div className="portfolio-site-card">
            <h2>No saved sites yet</h2>
            <p>Use New site to draw or upload your first land boundary.</p>
          </div>
        )}
        {!!missing && (
          <p className="portfolio-notice">
            {missing} {missing === 1 ? 'site has' : 'sites have'} no mapped
            boundary. All sites remain available in the selector and List view.
          </p>
        )}
        {error && <output className="portfolio-notice">{error}</output>}
      </div>
      <div className="portfolio-legend">
        <i /> Saved boundary <span>WGS84</span>
      </div>
    </section>
  );
}
