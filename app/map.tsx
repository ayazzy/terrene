'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Layers,
  LocateFixed,
  ArrowUpRight,
  FileSearch,
  MapPin,
  Search,
  X,
} from 'lucide-react';
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
import {
  entityKey,
  infrastructureEntityLabel,
  linkedSiteDisplayAnchor,
  searchableInfrastructureEntities,
  type InfrastructureEntity,
} from './infrastructure-entities';
import { portfolioBounds } from './portfolio-geometry';
import infrastructureStyles from './infrastructure-map.module.css';

type EntitySelection = { kind: 'site' | 'project_subject'; id: string } | null;

function geometryBounds(nextGeometry: Geometry) {
  const bounds = new maplibregl.LngLatBounds();
  const walkCoordinates = (
    value: Position | Position[] | Position[][] | Position[][][],
  ) => {
    if (typeof value[0] === 'number') bounds.extend(value as [number, number]);
    else
      (value as (Position | Position[] | Position[][])[]).forEach(
        walkCoordinates,
      );
  };
  const walkGeometry = (item: Geometry): void => {
    if (item.type === 'GeometryCollection')
      item.geometries.forEach(walkGeometry);
    else if ('coordinates' in item) walkCoordinates(item.coordinates);
  };
  walkGeometry(nextGeometry);
  return bounds;
}

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
  layersOpen?: boolean;
  onLayersOpenChange?: (open: boolean) => void;
  entities?: InfrastructureEntity[];
  selectedEntity?: EntitySelection;
  onSelectEntity?: (selection: EntitySelection) => void;
  onOpenEntity?: (entity: InfrastructureEntity) => void;
  entityLoading?: boolean;
  entityUnavailable?: boolean;
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
  layersOpen,
  onLayersOpenChange,
  entities = [],
  selectedEntity = null,
  onSelectEntity,
  onOpenEntity,
  entityLoading = false,
  entityUnavailable = false,
}: Props) {
  const el = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null);
  const [projection, setProjection] = useState<maplibregl.Map | null>(null),
    [readyMs, setReadyMs] = useState<number | null>(null),
    [points, setPoints] = useState<number[][]>([]),
    [revision, setRevision] = useState(0),
    [localHiddenLayerIds, setLocalHiddenLayerIds] = useState<string[]>([]),
    [localLayersOpen, setLocalLayersOpen] = useState(false),
    [rosterOpen, setRosterOpen] = useState(false),
    [entityQuery, setEntityQuery] = useState(''),
    [coordinates, setCoordinates] = useState(''),
    [error, setError] = useState('');
  const drawRef = useRef(draw);
  const geometryRef = useRef(geometry);
  const lastOverlayFocus = useRef('');
  const overlay = useRef<SVGSVGElement>(null);
  const inspectRef = useRef({ findings, onInspect });
  const builtWorldRef = useRef({
    screeningFeatures,
    onInspectMapObject,
    selectedMapObject,
  });
  const entityRef = useRef({ entities, onSelectEntity });
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
  useEffect(() => {
    entityRef.current = { entities, onSelectEntity };
  }, [entities, onSelectEntity]);
  const ready = !!projection;
  const layerPanelOpen = layersOpen ?? localLayersOpen;
  const setLayerPanelOpen = (open: boolean) => {
    if (open) setRosterOpen(false);
    if (layersOpen === undefined) setLocalLayersOpen(open);
    onLayersOpenChange?.(open);
  };
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
  const isVisible = (key: string) => !hiddenLayerSet.has(`environment:${key}`);
  const activeSelection =
    selected && isVisible(selected) ? selected : undefined;
  const repaint = () => setRevision((v) => v + 1);
  const fit = useCallback((nextGeometry: Geometry | null) => {
    const currentMap = map.current;
    if (!currentMap || !nextGeometry) return;
    const bounds = geometryBounds(nextGeometry);
    if (!bounds.isEmpty())
      currentMap.fitBounds(bounds, {
        padding: 65,
        maxZoom: 16,
        duration: 400,
      });
  }, []);
  useEffect(() => {
    if (!el.current) return;
    const startedAt = performance.now();
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
    m.on('load', () => {
      setReadyMs(Math.round(performance.now() - startedAt));
      setProjection(m);
    });
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
            '[data-map-object], [data-entity-kind], path[data-layer]:not([data-layer="site"])',
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
        else if (hit?.dataset.entityKind && hit.dataset.entityId)
          entityRef.current.onSelectEntity?.({
            kind: hit.dataset.entityKind as 'site' | 'project_subject',
            id: hit.dataset.entityId,
          });
        else {
          const finding = inspectRef.current.findings.find(
            (f) => f.key === hit?.dataset.layer,
          );
          if (finding) inspectRef.current.onInspect?.(finding);
        }
      }
    });
    let resizeFrame = 0;
    const observer = new ResizeObserver(() => {
      m.resize();
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        if (geometryRef.current) fit(geometryRef.current);
      });
    });
    observer.observe(el.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(resizeFrame);
      m.remove();
      map.current = null;
    };
  }, [fit]);
  useEffect(() => {
    drawRef.current = draw;
    if (map.current)
      map.current.getCanvas().style.cursor = draw ? 'crosshair' : '';
  }, [draw]);
  useEffect(() => {
    geometryRef.current = geometry;
  }, [geometry]);
  const fitAllEntities = useCallback(() => {
    const m = map.current;
    const sites = entityRef.current.entities
      .filter((entity) => entity.kind === 'site')
      .map((entity) => entity.site);
    const bounds = portfolioBounds(sites);
    if (!m || !bounds) return;
    m.fitBounds(
      [
        [bounds[0], bounds[1]],
        [bounds[2], bounds[3]],
      ],
      {
        padding: { top: 90, right: 80, bottom: 90, left: 360 },
        maxZoom: 13,
        duration: 400,
      },
    );
  }, []);
  useEffect(() => {
    if (ready) fit(geometry);
  }, [geometry, ready, projection, fit]);
  useEffect(() => {
    if (ready && entities.length && !selectedEntity) fitAllEntities();
  }, [ready, entities.length, selectedEntity, fitAllEntities]);
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
    fit,
  ]);
  useEffect(() => {
    if (!ready || !mapObjectFocusRequest) return;
    const feature = builtWorldRef.current.screeningFeatures?.features.find(
      (item) => item.id === builtWorldRef.current.selectedMapObject,
    );
    if (feature) fit(feature.geometry);
  }, [mapObjectFocusRequest, ready, projection, fit]);
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
  const siteEntities = entities.filter((entity) => entity.kind === 'site');
  const linkedProjects = entities.filter(
    (entity) =>
      entity.kind === 'project_subject' &&
      entity.locationState === 'site_linked',
  );
  const unlocatedProjects = entities.filter(
    (entity) =>
      entity.kind === 'project_subject' &&
      entity.locationState !== 'site_linked',
  );
  const rosterEntities = searchableInfrastructureEntities(
    entities,
    entityQuery,
    entities.length,
  );
  const shownRosterEntities = entityQuery.trim() ? rosterEntities : entities;
  const chosenEntity = entities.find(
    (entity) =>
      entity.kind === selectedEntity?.kind && entity.id === selectedEntity.id,
  );
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
    <div
      className={`map-wrap${entities.length || entityLoading || entityUnavailable ? ` ${infrastructureStyles.operatingMap}` : ''}`}
      data-primary-map="infrastructure-operating-picture"
      data-map-ready={ready}
      data-map-ready-ms={readyMs ?? undefined}
      aria-busy={!ready}
    >
      <div ref={el} className="map-canvas" />
      <svg
        ref={overlay}
        className="geography-overlay"
        aria-label="Site boundary and measured overlaps"
        data-revision={revision}
      >
        {!hiddenLayerSet.has('site-boundary') &&
          siteEntities.map((entity) => {
            const selectedSite =
              selectedEntity?.kind === 'site' &&
              selectedEntity.id === entity.id;
            const linkedSelection =
              chosenEntity?.kind === 'project_subject' &&
              chosenEntity.subject.site_id === entity.id;
            const displayGeometry =
              selectedSite && geometry ? geometry : entity.geometry;
            if (!displayGeometry) return null;
            return (
              <path
                key={`entity-site:${entity.id}`}
                data-entity-kind="site"
                data-entity-id={entity.id}
                data-selected={selectedSite || linkedSelection}
                d={path(displayGeometry)}
                fill="#a8c0ae"
                fillOpacity={selectedSite || linkedSelection ? 0.2 : 0.07}
                stroke={selectedSite || linkedSelection ? '#b7d7c0' : '#8d9c92'}
                strokeWidth={selectedSite || linkedSelection ? 3 : 1.5}
                fillRule="evenodd"
              >
                <title>
                  {entity.name} · saved Site boundary v{entity.site.version}
                </title>
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
        {builtFeatures.map(renderBuiltFeature)}
        {!siteEntities.length &&
          geometry &&
          !hiddenLayerSet.has('site-boundary') && (
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
      {!hiddenLayerSet.has('project-subjects') && projection && (
        <div
          className={infrastructureStyles.projectMarkers}
          aria-label="Site-linked Project Subjects"
        >
          {linkedProjects.map((entity) => {
            const anchor = linkedSiteDisplayAnchor(entity.geometry);
            if (!anchor) return null;
            const point = projection.project(anchor as [number, number]);
            const isSelected =
              selectedEntity?.kind === entity.kind &&
              selectedEntity.id === entity.id;
            return (
              <button
                key={entityKey(entity)}
                className={infrastructureStyles.projectMarker}
                data-selected={isSelected}
                style={{ left: point.x, top: point.y }}
                aria-label={`Open ${entity.name}`}
                aria-pressed={isSelected}
                onClick={() => onOpenEntity?.(entity)}
              >
                <span aria-hidden="true" />
                <strong>{entity.name}</strong>
              </button>
            );
          })}
        </div>
      )}
      {error && <div className="map-error">{error}</div>}
      <div className="map-toolbar">
        {!!entities.length && (
          <button
            aria-expanded={rosterOpen}
            aria-controls="infrastructure-entity-roster"
            onClick={() => {
              const open = !rosterOpen;
              setRosterOpen(open);
              if (open) setLayerPanelOpen(false);
            }}
          >
            <Search size={16} /> Entities{' '}
            <span className="layer-count">{entities.length}</span>
          </button>
        )}
        <button
          aria-expanded={layerPanelOpen}
          aria-controls="map-layers"
          onClick={() => setLayerPanelOpen(!layerPanelOpen)}
        >
          <Layers size={16} /> Layers{' '}
          <span className="layer-count">
            {Number(
              siteEntities.some((entity) => !!entity.geometry) &&
                !hiddenLayerSet.has('site-boundary'),
            ) +
              Number(
                linkedProjects.length > 0 &&
                  !hiddenLayerSet.has('project-subjects'),
              ) +
              findings.filter((f) => f.geometry && isVisible(f.key)).length +
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
          disabled={!geometry && !siteEntities.length}
          onClick={() => (geometry ? fit(geometry) : fitAllEntities())}
        >
          <LocateFixed size={17} />
        </button>
      </div>
      {layerPanelOpen && (
        <section
          id="map-layers"
          className="layer-control"
          aria-label="Map layers"
        >
          <div className="layer-control-title">
            <strong>Map layers</strong>
            <button
              className="text-btn"
              onClick={() => setLayerPanelOpen(false)}
            >
              Close
            </button>
          </div>
          <p>
            Current entity geography and saved evidence for the selected
            immutable assessment.
          </p>
          <label className="base-layer" htmlFor="map-basemap">
            <Checkbox
              id="map-basemap"
              checked={!hiddenLayerSet.has('basemap')}
              onCheckedChange={(value) => setLayerHidden('basemap', !value)}
            />{' '}
            OpenStreetMap basemap
          </label>
          <div className="layer-group">
            <h3>Infrastructure entities</h3>
            <div className="layer-row">
              <label htmlFor="map-site-boundary">
                <Checkbox
                  id="map-site-boundary"
                  checked={!hiddenLayerSet.has('site-boundary')}
                  disabled={
                    !geometry &&
                    !siteEntities.some((entity) => !!entity.geometry)
                  }
                  onCheckedChange={(value) =>
                    setLayerHidden('site-boundary', !value)
                  }
                />
                <i className="layer-swatch boundary" />
                <span className="layer-row-copy">
                  Site boundaries
                  <small>
                    {geometry
                      ? boundaryLabel
                      : `${siteEntities.length} retained Sites`}
                  </small>
                </span>
              </label>
            </div>
            <div className="layer-row">
              <label htmlFor="map-project-subjects">
                <Checkbox
                  id="map-project-subjects"
                  checked={!hiddenLayerSet.has('project-subjects')}
                  disabled={!linkedProjects.length}
                  onCheckedChange={(value) =>
                    setLayerHidden('project-subjects', !value)
                  }
                />
                <i className={infrastructureStyles.projectSwatch} />
                <span className="layer-row-copy">
                  Project Subjects
                  <small>
                    {linkedProjects.length} Site-linked ·{' '}
                    {unlocatedProjects.length} unlocated
                  </small>
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
              : !['loading', 'failed', 'unavailable', 'unsupported'].includes(
                  screeningFeaturesState,
                ) && (
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
      {rosterOpen &&
        (entities.length > 0 || entityLoading || entityUnavailable) && (
          <aside
            id="infrastructure-entity-roster"
            className={infrastructureStyles.roster}
            aria-label="Infrastructure entity roster"
          >
            <header>
              <span>
                <strong>Entity index</strong>
                <small>Sites + Project Subjects</small>
              </span>
              <button
                aria-label="Close entity roster"
                onClick={() => setRosterOpen(false)}
              >
                <X size={15} />
              </button>
            </header>
            <label>
              <Search size={14} aria-hidden="true" />
              <span className="sr-only">Search entity roster</span>
              <input
                value={entityQuery}
                onChange={(event) => setEntityQuery(event.target.value)}
                placeholder="Filter entities"
              />
            </label>
            {entityLoading && !entities.length ? (
              <p>Loading authorized entities…</p>
            ) : entityUnavailable && !entities.length ? (
              <p role="alert">
                Project Subjects are unavailable. Saved Sites remain separate
                from missing project intelligence.
              </p>
            ) : (
              <div className={infrastructureStyles.rosterRows}>
                {shownRosterEntities
                  .filter((entity) => entity.kind === 'site')
                  .map((entity) => (
                    <button
                      key={entityKey(entity)}
                      aria-pressed={
                        entityKey(entity) ===
                        (selectedEntity
                          ? `${selectedEntity.kind}:${selectedEntity.id}`
                          : '')
                      }
                      onClick={() => onOpenEntity?.(entity)}
                    >
                      <MapPin size={15} />
                      <span>
                        <strong>{entity.name}</strong>
                        <small>{infrastructureEntityLabel(entity)}</small>
                        <em>{entity.evidenceState}</em>
                      </span>
                    </button>
                  ))}
                {!!shownRosterEntities.filter(
                  (entity) =>
                    entity.kind === 'project_subject' &&
                    entity.locationState === 'site_linked',
                ).length && <h3>Site-linked intelligence</h3>}
                {shownRosterEntities
                  .filter(
                    (entity) =>
                      entity.kind === 'project_subject' &&
                      entity.locationState === 'site_linked',
                  )
                  .map((entity) => (
                    <button
                      key={entityKey(entity)}
                      aria-pressed={
                        entityKey(entity) ===
                        (selectedEntity
                          ? `${selectedEntity.kind}:${selectedEntity.id}`
                          : '')
                      }
                      onClick={() => onOpenEntity?.(entity)}
                    >
                      <FileSearch size={15} />
                      <span>
                        <strong>{entity.name}</strong>
                        <small>{infrastructureEntityLabel(entity)}</small>
                        <em>{entity.evidenceState}</em>
                      </span>
                    </button>
                  ))}
                {!!shownRosterEntities.filter(
                  (entity) =>
                    entity.kind === 'project_subject' &&
                    entity.locationState !== 'site_linked',
                ).length && <h3>Unlocated intelligence</h3>}
                {shownRosterEntities
                  .filter(
                    (entity) =>
                      entity.kind === 'project_subject' &&
                      entity.locationState !== 'site_linked',
                  )
                  .map((entity) => (
                    <button
                      key={entityKey(entity)}
                      aria-pressed={
                        entityKey(entity) ===
                        (selectedEntity
                          ? `${selectedEntity.kind}:${selectedEntity.id}`
                          : '')
                      }
                      onClick={() => onOpenEntity?.(entity)}
                    >
                      <FileSearch size={15} />
                      <span>
                        <strong>{entity.name}</strong>
                        <small>{infrastructureEntityLabel(entity)}</small>
                        <em>{entity.evidenceState}</em>
                      </span>
                    </button>
                  ))}
                {!shownRosterEntities.length && (
                  <p>No matching infrastructure entities.</p>
                )}
              </div>
            )}
          </aside>
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
