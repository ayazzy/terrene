'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Box,
  Compass,
  Layers,
  ListTree,
  LocateFixed,
  RotateCcw,
  RotateCw,
  ArrowUpRight,
  FileSearch,
  MapPin,
  Search,
  X,
} from 'lucide-react';
import type {
  Feature,
  FeatureCollection,
  Geometry,
  Polygon,
  LineString,
  Point,
  Position,
} from 'geojson';
import type { OverlayFinding } from './site-evidence';
import { layerGroup, layerColor } from './site-evidence';
import {
  buildingHeightStateCounts,
  buildingHeightStatus,
  infrastructureLayerIds,
  mapFeatureName,
  mapLayerLabel,
  mapLayerStatus,
  type InfrastructureLayerId,
  type InfrastructureMapScene,
} from './infrastructure-map-scene';
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

const SOURCE_IDS = {
  sites: 'terrene-sites',
  projects: 'terrene-project-subjects',
  environment: 'terrene-environment',
  infrastructure: 'terrene-infrastructure',
} as const;

const NATIVE_LAYER_IDS = {
  sitesFill: 'terrene-sites-fill',
  sitesLine: 'terrene-sites-line',
  projects: 'terrene-project-subjects-points',
  environmentFill: 'terrene-environment-fill',
  environmentLine: 'terrene-environment-line',
  buildingFill: 'terrene-buildings-fill',
  buildingExtrusion: 'terrene-buildings-extrusion',
  buildingLine: 'terrene-buildings-line',
  buildingFlatLine: 'terrene-buildings-flat-line',
  functionalFill: 'terrene-functional-sites-fill',
  functionalLine: 'terrene-functional-sites-line',
  railwayTracks: 'terrene-railway-tracks-line',
  railwayStations: 'terrene-railway-stations-point',
} as const;

const HIT_LAYER_IDS = [
  NATIVE_LAYER_IDS.railwayStations,
  NATIVE_LAYER_IDS.railwayTracks,
  NATIVE_LAYER_IDS.buildingFlatLine,
  NATIVE_LAYER_IDS.buildingLine,
  NATIVE_LAYER_IDS.buildingExtrusion,
  NATIVE_LAYER_IDS.buildingFill,
  NATIVE_LAYER_IDS.functionalLine,
  NATIVE_LAYER_IDS.functionalFill,
  NATIVE_LAYER_IDS.environmentLine,
  NATIVE_LAYER_IDS.environmentFill,
  NATIVE_LAYER_IDS.projects,
  NATIVE_LAYER_IDS.sitesLine,
  NATIVE_LAYER_IDS.sitesFill,
] as const;

const emptyFeatureCollection: FeatureCollection = {
  type: 'FeatureCollection',
  features: [],
};

const MAP_PALETTE = {
  selection: '#f2b84b',
  boundary: '#45d6e8',
  boundaryFill: '#45d6e8',
  building: '#7b8994',
  buildingFlat: '#aeb8c0',
  functionalSite: '#36a99a',
  railwayMulti: '#c084fc',
  railwaySingle: '#60a5fa',
  railwayNarrow: '#fb7185',
  station: '#f5f8f6',
  project: '#f2b84b',
} as const;

const OPENFREEMAP_DARK_STYLE_URL = 'https://tiles.openfreemap.org/styles/dark';

const EVIDENCE_ONLY_DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: 'evidence-only-background',
      type: 'background',
      paint: { 'background-color': '#0a0f11' },
    },
  ],
};

type BasemapState = 'loading' | 'available' | 'degraded' | 'unavailable';

type BasemapConfiguration = {
  style: maplibregl.StyleSpecification | string;
  label: string;
  productionConfigurationMissing: boolean;
};

function basemapConfiguration(): BasemapConfiguration {
  const vectorStyleUrl = process.env.NEXT_PUBLIC_BASEMAP_STYLE_URL?.trim();
  if (vectorStyleUrl)
    return {
      style: vectorStyleUrl,
      label: 'Configured vector basemap',
      productionConfigurationMissing: false,
    };
  const legacyRasterUrl = process.env.NEXT_PUBLIC_BASEMAP_URL?.trim();
  if (legacyRasterUrl)
    return {
      style: {
        version: 8,
        sources: {
          'legacy-basemap': {
            type: 'raster',
            tiles: [legacyRasterUrl],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          {
            id: 'legacy-basemap',
            type: 'raster',
            source: 'legacy-basemap',
            paint: { 'raster-saturation': -0.75, 'raster-opacity': 0.78 },
          },
        ],
      },
      label: 'Legacy raster basemap',
      productionConfigurationMissing: false,
    };
  if (process.env.NODE_ENV === 'development')
    return {
      style: OPENFREEMAP_DARK_STYLE_URL,
      label: 'OpenFreeMap Dark · local development',
      productionConfigurationMissing: false,
    };
  return {
    style: {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'unconfigured-basemap',
          type: 'background',
          paint: { 'background-color': '#0a0f11' },
        },
      ],
    },
    label: 'Basemap unavailable',
    productionConfigurationMissing: true,
  };
}

const BASEMAP = basemapConfiguration();

const terreneLayerDefinitions = [
  {
    id: NATIVE_LAYER_IDS.sitesFill,
    type: 'fill',
    source: SOURCE_IDS.sites,
    paint: {
      'fill-color': [
        'case',
        ['boolean', ['feature-state', 'related'], false],
        MAP_PALETTE.selection,
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.boundaryFill,
      ],
      'fill-opacity': [
        'case',
        ['boolean', ['feature-state', 'related'], false],
        0.28,
        ['boolean', ['feature-state', 'selected'], false],
        0.24,
        0.08,
      ],
    },
  },
  {
    id: NATIVE_LAYER_IDS.sitesLine,
    type: 'line',
    source: SOURCE_IDS.sites,
    paint: {
      'line-color': [
        'case',
        ['boolean', ['feature-state', 'related'], false],
        MAP_PALETTE.selection,
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.boundary,
      ],
      'line-width': [
        'case',
        ['boolean', ['feature-state', 'related'], false],
        5.5,
        ['boolean', ['feature-state', 'selected'], false],
        3.5,
        2,
      ],
    },
  },
  {
    id: NATIVE_LAYER_IDS.environmentFill,
    type: 'fill',
    source: SOURCE_IDS.environment,
    paint: {
      'fill-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        ['get', 'color'],
      ],
      'fill-opacity': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        0.4,
        0.22,
      ],
    },
  },
  {
    id: NATIVE_LAYER_IDS.environmentLine,
    type: 'line',
    source: SOURCE_IDS.environment,
    paint: {
      'line-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        ['get', 'color'],
      ],
      'line-width': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        3.5,
        1.5,
      ],
    },
  },
  {
    id: NATIVE_LAYER_IDS.functionalFill,
    type: 'fill',
    source: SOURCE_IDS.infrastructure,
    filter: ['==', ['get', 'layer_id'], 'functional_sites'],
    paint: {
      'fill-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.functionalSite,
      ],
      'fill-opacity': 0.38,
    },
  },
  {
    id: NATIVE_LAYER_IDS.functionalLine,
    type: 'line',
    source: SOURCE_IDS.infrastructure,
    filter: ['==', ['get', 'layer_id'], 'functional_sites'],
    paint: {
      'line-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.functionalSite,
      ],
      'line-width': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        4,
        2,
      ],
    },
  },
  {
    id: NATIVE_LAYER_IDS.buildingFill,
    type: 'fill',
    source: SOURCE_IDS.infrastructure,
    filter: ['==', ['get', 'layer_id'], 'buildings'],
    paint: {
      'fill-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.building,
      ],
      'fill-opacity': 0.38,
    },
  },
  {
    id: NATIVE_LAYER_IDS.buildingExtrusion,
    type: 'fill-extrusion',
    source: SOURCE_IDS.infrastructure,
    filter: [
      'all',
      ['==', ['get', 'layer_id'], 'buildings'],
      ['==', ['get', 'height_backed'], true],
    ],
    layout: { visibility: 'none' },
    paint: {
      'fill-extrusion-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.building,
      ],
      'fill-extrusion-height': ['get', 'extrusion_height_m'],
      'fill-extrusion-opacity': 0.86,
      'fill-extrusion-vertical-gradient': true,
    },
  },
  {
    id: NATIVE_LAYER_IDS.buildingLine,
    type: 'line',
    source: SOURCE_IDS.infrastructure,
    filter: ['==', ['get', 'layer_id'], 'buildings'],
    paint: {
      'line-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.building,
      ],
      'line-width': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        4,
        1.75,
      ],
    },
  },
  {
    id: NATIVE_LAYER_IDS.buildingFlatLine,
    type: 'line',
    source: SOURCE_IDS.infrastructure,
    filter: [
      'all',
      ['==', ['get', 'layer_id'], 'buildings'],
      ['==', ['get', 'height_backed'], false],
    ],
    paint: {
      'line-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.buildingFlat,
      ],
      'line-width': 2,
      'line-dasharray': [2, 1],
    },
  },
  {
    id: NATIVE_LAYER_IDS.railwayTracks,
    type: 'line',
    source: SOURCE_IDS.infrastructure,
    filter: ['==', ['get', 'layer_id'], 'railway_tracks'],
    paint: {
      'line-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        [
          'match',
          ['get', 'classification'],
          'Multi Track',
          MAP_PALETTE.railwayMulti,
          'Single Track',
          MAP_PALETTE.railwaySingle,
          'Narrow Gauge',
          MAP_PALETTE.railwayNarrow,
          MAP_PALETTE.railwaySingle,
        ],
      ],
      'line-width': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        4.5,
        2.75,
      ],
      'line-dasharray': [2, 1.2],
    },
  },
  {
    id: NATIVE_LAYER_IDS.railwayStations,
    type: 'circle',
    source: SOURCE_IDS.infrastructure,
    filter: ['==', ['get', 'layer_id'], 'railway_stations'],
    paint: {
      'circle-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.station,
      ],
      'circle-radius': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        8,
        5.5,
      ],
      'circle-stroke-color': '#071012',
      'circle-stroke-width': 2.5,
    },
  },
  {
    id: NATIVE_LAYER_IDS.projects,
    type: 'circle',
    source: SOURCE_IDS.projects,
    paint: {
      'circle-color': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        MAP_PALETTE.selection,
        MAP_PALETTE.project,
      ],
      'circle-radius': [
        'case',
        ['boolean', ['feature-state', 'selected'], false],
        8,
        5.5,
      ],
      'circle-stroke-color': '#071012',
      'circle-stroke-width': 2.5,
    },
  },
] satisfies maplibregl.LayerSpecification[];

function installTerreneLayers(currentMap: maplibregl.Map) {
  for (const sourceId of Object.values(SOURCE_IDS))
    if (!currentMap.getSource(sourceId))
      currentMap.addSource(sourceId, {
        type: 'geojson',
        data: emptyFeatureCollection,
      });
  for (const layer of terreneLayerDefinitions)
    if (!currentMap.getLayer(layer.id)) currentMap.addLayer(layer);
}

function setGeoJSONData(
  currentMap: maplibregl.Map,
  sourceId: string,
  data: FeatureCollection,
) {
  const source = currentMap.getSource(sourceId);
  if (source?.type === 'geojson')
    void (source as maplibregl.GeoJSONSource).setData(data);
}

function sourceDate(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf())
    ? 'Time not recorded'
    : new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      }).format(parsed);
}

function hoverLabel(properties: Record<string, unknown>) {
  const name = properties.name;
  if (typeof name === 'string' && name) return name;
  const classification = properties.classification;
  if (typeof classification === 'string' && classification)
    return classification;
  const kind = properties.object_type;
  if (typeof kind === 'string' && kind) return kind.replaceAll('_', ' ');
  if (typeof properties.environment_key === 'string') return 'Saved evidence';
  if (properties.entity_kind === 'site') return 'Site boundary';
  if (properties.entity_kind === 'project_subject') return 'Project Subject';
  return '';
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
  mapScene?: InfrastructureMapScene | null;
  mapSceneState?:
    | 'idle'
    | 'loading'
    | 'available'
    | 'failed'
    | 'unavailable'
    | 'unsupported';
  mapSceneError?: string;
  selectedMapObject?: string | null;
  showRelatedObjects?: boolean;
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
  workflowLevel?: 'portfolio' | 'site' | 'asset';
  workflowAssetLabel?: string;
  onOpenPortfolio?: () => void;
  onOpenSiteDiligence?: () => void;
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
  mapScene,
  mapSceneState = 'idle',
  mapSceneError = '',
  selectedMapObject,
  showRelatedObjects = false,
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
  workflowLevel,
  workflowAssetLabel,
  onOpenPortfolio,
  onOpenSiteDiligence,
}: Props) {
  const el = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null);
  const basemapLayerIds = useRef<string[]>([]);
  const relatedNativeFeatures = useRef<{ source: string; id: string }[]>([]);
  const [projection, setProjection] = useState<maplibregl.Map | null>(null),
    [readyMs, setReadyMs] = useState<number | null>(null),
    [points, setPoints] = useState<number[][]>([]),
    [revision, setRevision] = useState(0),
    [localHiddenLayerIds, setLocalHiddenLayerIds] = useState<string[]>([]),
    [localLayersOpen, setLocalLayersOpen] = useState(false),
    [rosterOpen, setRosterOpen] = useState(false),
    [legendOpen, setLegendOpen] = useState(false),
    [perspectiveSceneId, setPerspectiveSceneId] = useState<string | null>(null),
    [entityQuery, setEntityQuery] = useState(''),
    [coordinates, setCoordinates] = useState(''),
    [error, setError] = useState('');
  const [basemapState, setBasemapState] = useState<BasemapState>('loading');
  const drawRef = useRef(draw);
  const geometryRef = useRef(geometry);
  const lastOverlayFocus = useRef('');
  const selectedNativeFeatures = useRef<{ source: string; id: string }[]>([]);
  const inspectRef = useRef({ findings, onInspect });
  const builtWorldRef = useRef({
    mapScene,
    onInspectMapObject,
    selectedMapObject,
  });
  const entityRef = useRef({ entities, onSelectEntity });
  useEffect(() => {
    inspectRef.current = { findings, onInspect };
  }, [findings, onInspect]);
  useEffect(() => {
    builtWorldRef.current = {
      mapScene,
      onInspectMapObject,
      selectedMapObject,
    };
  }, [mapScene, onInspectMapObject, selectedMapObject]);
  useEffect(() => {
    entityRef.current = { entities, onSelectEntity };
  }, [entities, onSelectEntity]);
  const ready = !!projection;
  const layerPanelOpen = layersOpen ?? localLayersOpen;
  const setLayerPanelOpen = (open: boolean) => {
    if (open) {
      setRosterOpen(false);
      setLegendOpen(false);
    }
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
  const chosenEntity = entities.find(
    (entity) =>
      entity.kind === selectedEntity?.kind && entity.id === selectedEntity.id,
  );
  const heightCounts = useMemo(
    () => buildingHeightStateCounts(mapScene),
    [mapScene],
  );
  const heightAvailableCount = heightCounts.available + heightCounts.partial;
  const heightStatus = buildingHeightStatus(heightCounts);
  const canPerspective = heightAvailableCount > 0;
  const perspectiveActive =
    canPerspective && perspectiveSceneId === mapScene?.snapshot.id;
  useEffect(() => {
    map.current?.easeTo({
      pitch: perspectiveActive ? 55 : 0,
      bearing: 0,
      duration: 500,
    });
  }, [perspectiveActive]);
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
      style: BASEMAP.style,
      center: [-1.29, 51.78],
      zoom: 10,
      dragRotate: true,
      pitchWithRotate: true,
      touchPitch: true,
    });
    map.current = m;
    let evidenceOnlyFallback = BASEMAP.productionConfigurationMissing;
    m.setMissingStyleImageResolver((imageId) => {
      if (m.hasImage(imageId)) return;
      // Optional third-party basemap patterns are context, not Terrene
      // evidence. A transparent pixel prevents a missing decorative sprite
      // from polluting the evidence failure channel.
      m.addImage(imageId, {
        width: 1,
        height: 1,
        data: new Uint8Array([0, 0, 0, 0]),
      });
    });
    m.addControl(new maplibregl.NavigationControl(), 'top-right');
    m.addControl(
      new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }),
      'bottom-right',
    );
    const hoverPopup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
      className: 'terrene-map-hover',
    });
    m.on('mousemove', (e) => {
      setCoordinates(
        `${Math.abs(e.lngLat.lat).toFixed(5)}° ${e.lngLat.lat >= 0 ? 'N' : 'S'} · ${Math.abs(e.lngLat.lng).toFixed(5)}° ${e.lngLat.lng >= 0 ? 'E' : 'W'}`,
      );
      if (drawRef.current) {
        hoverPopup.remove();
        return;
      }
      const hit = m.queryRenderedFeatures(e.point, {
        layers: [...HIT_LAYER_IDS],
      })[0];
      const label = hit ? hoverLabel(hit.properties) : '';
      m.getCanvas().style.cursor = label ? 'pointer' : '';
      if (!label) {
        hoverPopup.remove();
        return;
      }
      const content = document.createElement('span');
      content.textContent = label;
      hoverPopup.setLngLat(e.lngLat).setDOMContent(content).addTo(m);
    });
    m.on('mouseout', () => hoverPopup.remove());
    const handleStyleLoad = () => {
      basemapLayerIds.current = (m.getStyle().layers || []).map(
        (layer) => layer.id,
      );
      installTerreneLayers(m);
      if (evidenceOnlyFallback) {
        setBasemapState('unavailable');
        setError(
          BASEMAP.productionConfigurationMissing
            ? 'Basemap is not configured for production. Evidence geometry remains available.'
            : 'Basemap could not load. Terrene boundary and evidence geometry remain available on an evidence-only background.',
        );
      } else {
        setBasemapState('available');
      }
      setReadyMs(Math.round(performance.now() - startedAt));
      setProjection(m);
    };
    m.on('style.load', handleStyleLoad);
    m.on('move', repaint);
    m.on('resize', repaint);
    m.on('error', (event) => {
      const sourceId = (event as { sourceId?: string }).sourceId;
      if (
        sourceId &&
        Object.values(SOURCE_IDS).includes(
          sourceId as (typeof SOURCE_IDS)[keyof typeof SOURCE_IDS],
        )
      ) {
        setError(
          'A retained evidence layer could not render. The layer is unavailable rather than empty.',
        );
        return;
      }
      if (
        !m.isStyleLoaded() &&
        typeof BASEMAP.style === 'string' &&
        !evidenceOnlyFallback
      ) {
        evidenceOnlyFallback = true;
        setBasemapState('unavailable');
        setError(
          'Basemap could not load. Terrene boundary and evidence geometry remain available on an evidence-only background.',
        );
        m.setStyle(EVIDENCE_ONLY_DARK_STYLE, { diff: false });
        return;
      }
      setBasemapState('degraded');
      setError(
        'Some basemap tiles could not load. Boundary and evidence remain available.',
      );
    });
    m.on('click', (e) => {
      if (drawRef.current) {
        setPoints((vertices) => [...vertices, [e.lngLat.lng, e.lngLat.lat]]);
      } else {
        const hit = m.queryRenderedFeatures(e.point, {
          layers: [...HIT_LAYER_IDS],
        })[0];
        const objectId = hit?.properties?.object_id;
        if (objectId) builtWorldRef.current.onInspectMapObject?.(objectId);
        else if (hit?.properties?.entity_kind && hit.properties.entity_id)
          entityRef.current.onSelectEntity?.({
            kind: hit.properties.entity_kind as 'site' | 'project_subject',
            id: hit.properties.entity_id,
          });
        else {
          const finding = inspectRef.current.findings.find(
            (f) => f.key === hit?.properties?.environment_key,
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
      hoverPopup.remove();
      m.setMissingStyleImageResolver(null);
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
  useEffect(() => {
    const currentMap = map.current;
    if (!ready || !currentMap?.isStyleLoaded()) return;
    const siteFeatures: Feature[] = siteEntities.flatMap((entity) => {
      const selectedSite =
        selectedEntity?.kind === 'site' && selectedEntity.id === entity.id;
      const displayGeometry =
        selectedSite && geometry ? geometry : entity.geometry;
      if (!displayGeometry) return [];
      return [
        {
          type: 'Feature',
          id: `site:${entity.id}`,
          geometry: displayGeometry,
          properties: {
            entity_kind: 'site',
            entity_id: entity.id,
            name: entity.name,
            boundary_version: entity.site.version,
          },
        },
      ];
    });
    if (!siteFeatures.length && geometry) {
      siteFeatures.push({
        type: 'Feature',
        id: 'site:current-boundary',
        geometry,
        properties: { entity_kind: null, entity_id: null },
      });
    }
    const projectFeatures: Feature<Point>[] = linkedProjects.flatMap(
      (entity) => {
        const anchor = linkedSiteDisplayAnchor(entity.geometry);
        if (!anchor) return [];
        return [
          {
            type: 'Feature',
            id: `project_subject:${entity.id}`,
            geometry: { type: 'Point', coordinates: anchor },
            properties: {
              entity_kind: 'project_subject',
              entity_id: entity.id,
              name: entity.name,
            },
          },
        ];
      },
    );
    const environmentFeatures: Feature[] = findings.flatMap((finding) => {
      if (!finding.geometry || hiddenLayerSet.has(`environment:${finding.key}`))
        return [];
      return [
        {
          type: 'Feature',
          id: `environment:${finding.key}`,
          geometry: finding.geometry,
          properties: {
            environment_key: finding.key,
            name: finding.dataset,
            color: layerColor(finding.key),
          },
        },
      ];
    });
    const sceneFeatures: Feature[] = (mapScene?.features || []).flatMap(
      (feature) => {
        const layer = mapScene?.layers.find(
          (item) => item.id === feature.properties.layer_id,
        );
        if (!layer || !['available', 'partial'].includes(layer.state))
          return [];
        const height = feature.properties.height;
        const heightBacked =
          height !== null &&
          (height.state === 'available' || height.state === 'partial') &&
          height.extrusion_height_m !== null;
        return [
          {
            type: 'Feature',
            id: feature.id,
            geometry: feature.geometry,
            properties: {
              object_id: feature.id,
              layer_id: feature.properties.layer_id,
              object_type: feature.properties.object_type,
              name: mapFeatureName(feature),
              classification: feature.properties.classification,
              height_state: height?.state || null,
              height_backed: heightBacked,
              extrusion_height_m: heightBacked ? height.extrusion_height_m : 0,
            },
          },
        ];
      },
    );
    setGeoJSONData(currentMap, SOURCE_IDS.sites, {
      type: 'FeatureCollection',
      features: siteFeatures,
    });
    setGeoJSONData(currentMap, SOURCE_IDS.projects, {
      type: 'FeatureCollection',
      features: projectFeatures,
    });
    setGeoJSONData(currentMap, SOURCE_IDS.environment, {
      type: 'FeatureCollection',
      features: environmentFeatures,
    });
    setGeoJSONData(currentMap, SOURCE_IDS.infrastructure, {
      type: 'FeatureCollection',
      features: sceneFeatures,
    });
  }, [
    ready,
    geometry,
    siteEntities,
    linkedProjects,
    selectedEntity,
    findings,
    mapScene,
    hiddenLayerSet,
  ]);
  useEffect(() => {
    const currentMap = map.current;
    if (!ready || !currentMap) return;
    const synchronizeFeatureState = () => {
      for (const feature of selectedNativeFeatures.current)
        currentMap.removeFeatureState(feature, 'selected');
      for (const feature of relatedNativeFeatures.current)
        currentMap.removeFeatureState(feature, 'related');
      const next: { source: string; id: string }[] = [];
      const related: { source: string; id: string }[] = [];
      if (selectedMapObject)
        next.push({
          source: SOURCE_IDS.infrastructure,
          id: selectedMapObject,
        });
      if (activeSelection)
        next.push({
          source: SOURCE_IDS.environment,
          id: `environment:${activeSelection}`,
        });
      if (selectedEntity?.kind === 'site')
        next.push({
          source: SOURCE_IDS.sites,
          id: `site:${selectedEntity.id}`,
        });
      if (selectedEntity?.kind === 'project_subject') {
        next.push({
          source: SOURCE_IDS.projects,
          id: `project_subject:${selectedEntity.id}`,
        });
        if (
          chosenEntity?.kind === 'project_subject' &&
          chosenEntity.subject.site_id
        )
          next.push({
            source: SOURCE_IDS.sites,
            id: `site:${chosenEntity.subject.site_id}`,
          });
      }
      if (showRelatedObjects && selectedMapObject) {
        const relatedSiteId =
          selectedEntity?.kind === 'site'
            ? `site:${selectedEntity.id}`
            : geometry
              ? 'site:current-boundary'
              : null;
        if (relatedSiteId)
          related.push({ source: SOURCE_IDS.sites, id: relatedSiteId });
      }
      for (const feature of next)
        currentMap.setFeatureState(feature, { selected: true });
      for (const feature of related)
        currentMap.setFeatureState(feature, { related: true });
      selectedNativeFeatures.current = next;
      relatedNativeFeatures.current = related;
    };
    if (currentMap.isStyleLoaded()) synchronizeFeatureState();
    else currentMap.once('idle', synchronizeFeatureState);
    return () => {
      currentMap.off('idle', synchronizeFeatureState);
    };
  }, [
    ready,
    selectedMapObject,
    showRelatedObjects,
    activeSelection,
    selectedEntity,
    chosenEntity,
    geometry,
    mapScene,
    findings,
    entities,
  ]);
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
    const feature = builtWorldRef.current.mapScene?.features.find(
      (item) => item.id === builtWorldRef.current.selectedMapObject,
    );
    if (feature) fit(feature.geometry);
  }, [mapObjectFocusRequest, ready, projection, fit]);
  useEffect(() => {
    const currentMap = map.current;
    if (!ready || !currentMap) return;
    const synchronizeVisibility = () => {
      const visibility = (layerId: string, hidden: boolean) =>
        currentMap.setLayoutProperty(
          layerId,
          'visibility',
          hidden ? 'none' : 'visible',
        );
      for (const layerId of basemapLayerIds.current)
        visibility(layerId, hiddenLayerSet.has('basemap'));
      visibility(
        NATIVE_LAYER_IDS.sitesFill,
        hiddenLayerSet.has('site-boundary'),
      );
      visibility(
        NATIVE_LAYER_IDS.sitesLine,
        hiddenLayerSet.has('site-boundary'),
      );
      visibility(
        NATIVE_LAYER_IDS.projects,
        hiddenLayerSet.has('project-subjects'),
      );
      const semanticLayers: Record<InfrastructureLayerId, string[]> = {
        buildings: [
          NATIVE_LAYER_IDS.buildingFill,
          NATIVE_LAYER_IDS.buildingLine,
          NATIVE_LAYER_IDS.buildingFlatLine,
        ],
        functional_sites: [
          NATIVE_LAYER_IDS.functionalFill,
          NATIVE_LAYER_IDS.functionalLine,
        ],
        railway_tracks: [NATIVE_LAYER_IDS.railwayTracks],
        railway_stations: [NATIVE_LAYER_IDS.railwayStations],
      };
      for (const [layerId, renderedLayers] of Object.entries(semanticLayers))
        for (const renderedLayer of renderedLayers)
          visibility(renderedLayer, hiddenLayerSet.has(`built:${layerId}`));
      visibility(
        NATIVE_LAYER_IDS.buildingExtrusion,
        hiddenLayerSet.has('built:buildings') || !perspectiveActive,
      );
    };
    if (currentMap.isStyleLoaded()) synchronizeVisibility();
    else currentMap.once('idle', synchronizeVisibility);
    return () => {
      currentMap.off('idle', synchronizeVisibility);
    };
  }, [hiddenLayerSet, ready, projection, perspectiveActive]);
  // The isolated boundary editor retains its temporary SVG drawing surface.
  // The primary operating picture uses only native GeoJSON sources and layers.
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
  const builtFeatures = (mapScene?.features || []).filter((feature) =>
    mapScene?.layers.some(
      (layer) =>
        layer.id === feature.properties.layer_id &&
        (layer.state === 'available' || layer.state === 'partial'),
    ),
  );
  const builtLayerColor = (layer: InfrastructureLayerId) =>
    ({
      buildings: MAP_PALETTE.building,
      functional_sites: MAP_PALETTE.functionalSite,
      railway_tracks: MAP_PALETTE.railwayMulti,
      railway_stations: MAP_PALETTE.station,
    })[layer];
  const builtLayerVisible = (layer: InfrastructureLayerId) =>
    !hiddenLayerSet.has(`built:${layer}`);
  const selectedBuiltFeature = builtFeatures.find(
    (feature) => feature.id === selectedMapObject,
  );
  const selectedRelationshipTypes = [
    ...new Set(
      (selectedBuiltFeature?.properties.relationships || []).map(
        (relationship) => relationship.predicate,
      ),
    ),
  ];
  const featureSwatchColor = (feature: (typeof builtFeatures)[number]) => {
    if (feature.properties.layer_id !== 'railway_tracks')
      return builtLayerColor(feature.properties.layer_id);
    return (
      {
        'Multi Track': MAP_PALETTE.railwayMulti,
        'Single Track': MAP_PALETTE.railwaySingle,
        'Narrow Gauge': MAP_PALETTE.railwayNarrow,
      }[feature.properties.classification || ''] || MAP_PALETTE.railwaySingle
    );
  };
  const legendFeatures = builtFeatures.filter((feature) =>
    builtLayerVisible(feature.properties.layer_id),
  );
  const legendObjectRows = (() => {
    const totals = new Map<string, number>();
    const positions = new Map<string, number>();
    for (const feature of legendFeatures) {
      const label = mapFeatureName(feature);
      totals.set(label, (totals.get(label) || 0) + 1);
    }
    return legendFeatures.map((feature) => {
      const label = mapFeatureName(feature);
      const position = (positions.get(label) || 0) + 1;
      const total = totals.get(label) || 1;
      positions.set(label, position);
      return {
        feature,
        label: total > 1 ? `${label} ${position} of ${total}` : label,
      };
    });
  })();
  const railClassifications = [
    ...new Set(
      legendFeatures
        .filter((feature) => feature.properties.layer_id === 'railway_tracks')
        .map((feature) => feature.properties.classification)
        .filter((value): value is string => !!value),
    ),
  ];
  const rosterEntities = searchableInfrastructureEntities(
    entities,
    entityQuery,
    entities.length,
  );
  const shownRosterEntities = entityQuery.trim() ? rosterEntities : entities;
  return (
    <div
      className={`map-wrap${entities.length || entityLoading || entityUnavailable ? ` ${infrastructureStyles.operatingMap}` : ''}`}
      data-primary-map="infrastructure-operating-picture"
      data-map-ready={ready}
      data-map-ready-ms={readyMs ?? undefined}
      data-basemap-state={basemapState}
      aria-busy={!ready}
    >
      <div ref={el} className="map-canvas" />
      {!ready && (
        <output className={infrastructureStyles.sceneStatus}>
          Initialising spatial evidence…
        </output>
      )}
      {draw && (
        <svg
          className="geography-overlay"
          aria-label="Boundary editor"
          data-revision={revision}
        >
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
          {ready &&
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
      )}
      {error && <div className="map-error">{error}</div>}
      {ready &&
        (mapSceneState === 'loading' ||
          mapSceneState === 'failed' ||
          mapSceneState === 'unsupported' ||
          mapSceneState === 'unavailable' ||
          heightStatus) && (
          <output
            className={infrastructureStyles.sceneStatus}
            data-state={
              mapSceneState === 'failed'
                ? 'failed'
                : mapSceneState === 'loading'
                  ? 'loading'
                  : heightStatus?.startsWith('Partial')
                    ? 'partial'
                    : 'unavailable'
            }
            role={mapSceneState === 'failed' ? 'alert' : undefined}
          >
            {mapSceneState === 'loading'
              ? 'Loading saved infrastructure evidence…'
              : mapSceneState === 'failed'
                ? `Infrastructure evidence unavailable. Missing data is not zero.${mapSceneError ? ` ${mapSceneError}` : ''}`
                : mapSceneState === 'unsupported'
                  ? 'This historical assessment predates persisted infrastructure evidence. Current objects were not substituted.'
                  : mapSceneState === 'unavailable'
                    ? 'No persisted infrastructure evidence is stored for this assessment. Missing data is not zero.'
                    : heightStatus}
          </output>
        )}
      <div className="map-toolbar">
        {!!entities.length && (
          <button
            aria-expanded={rosterOpen}
            aria-controls="infrastructure-entity-roster"
            onClick={() => {
              const open = !rosterOpen;
              setRosterOpen(open);
              if (open) {
                setLegendOpen(false);
                setLayerPanelOpen(false);
              }
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
              infrastructureLayerIds.filter((layer) =>
                builtFeatures.some(
                  (feature) =>
                    feature.properties.layer_id === layer &&
                    builtLayerVisible(layer),
                ),
              ).length}
          </span>
        </button>
        <button
          aria-expanded={legendOpen}
          aria-controls="map-legend"
          onClick={() => {
            const open = !legendOpen;
            setLegendOpen(open);
            if (open) {
              setRosterOpen(false);
              setLayerPanelOpen(false);
            }
          }}
        >
          <ListTree size={16} /> Legend
        </button>
        {canPerspective && (
          <button
            aria-pressed={perspectiveActive}
            title={
              perspectiveActive
                ? 'Return to top-down analysis'
                : `View ${heightAvailableCount} evidence-backed building ${heightAvailableCount === 1 ? 'height' : 'heights'}`
            }
            onClick={() => {
              const next = !perspectiveActive;
              setPerspectiveSceneId(
                next ? mapScene?.snapshot.id || null : null,
              );
            }}
          >
            <Box size={16} /> {perspectiveActive ? '2D' : 'Perspective'}
          </button>
        )}
        <button
          aria-label="Rotate map anticlockwise"
          title="Rotate map 15° anticlockwise. Right-drag or Control-drag the map for free rotation."
          onClick={() =>
            map.current?.easeTo({
              bearing: map.current.getBearing() - 15,
              duration: 250,
            })
          }
        >
          <RotateCcw size={16} />
          <span className="sr-only">Rotate left</span>
        </button>
        <button
          aria-label="Reset map to north"
          title="Reset map to north"
          onClick={() => map.current?.easeTo({ bearing: 0, duration: 250 })}
        >
          <Compass size={16} />
          <span className="sr-only">North</span>
        </button>
        <button
          aria-label="Rotate map clockwise"
          title="Rotate map 15° clockwise. Right-drag or Control-drag the map for free rotation."
          onClick={() =>
            map.current?.easeTo({
              bearing: map.current.getBearing() + 15,
              duration: 250,
            })
          }
        >
          <RotateCw size={16} />
          <span className="sr-only">Rotate right</span>
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
      {workflowLevel && (
        <nav
          className={infrastructureStyles.workflowPath}
          aria-label="Spatial intelligence level"
        >
          {workflowLevel === 'portfolio' ? (
            <strong aria-current="page">All sites</strong>
          ) : (
            <button
              title="Return to the all-sites map"
              onClick={onOpenPortfolio}
            >
              All sites
            </button>
          )}
          {workflowLevel !== 'portfolio' && (
            <>
              <span aria-hidden="true">›</span>
              {workflowLevel === 'site' ? (
                <strong aria-current="page">Site diligence</strong>
              ) : (
                <button onClick={onOpenSiteDiligence}>Site diligence</button>
              )}
            </>
          )}
          {workflowLevel === 'asset' && (
            <>
              <span aria-hidden="true">›</span>
              <strong aria-current="page">
                Asset intelligence
                {workflowAssetLabel && <small>{workflowAssetLabel}</small>}
              </strong>
            </>
          )}
        </nav>
      )}
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
            {basemapState === 'unavailable'
              ? 'Evidence-only background · basemap unavailable'
              : `${BASEMAP.label}${basemapState === 'degraded' ? ' · degraded' : ''}`}
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
            {mapSceneState === 'loading' && (
              <p>Loading persisted mapped objects…</p>
            )}
            {mapSceneState === 'failed' && (
              <p role="alert">
                Built-world layers could not be loaded. Missing map data is not
                reported as zero. {mapSceneError}
              </p>
            )}
            {mapSceneState === 'unsupported' && (
              <p>
                This historical evidence does not support persisted built-world
                objects. Current objects are not substituted.
              </p>
            )}
            {mapSceneState === 'unavailable' && (
              <p>
                No built-world map evidence is stored for this assessment.
                Missing evidence is not reported as zero.
              </p>
            )}
            {mapScene
              ? mapScene.layers.map((layer) => {
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
                          {layer.id === 'buildings' &&
                            layer.feature_count > 0 && (
                              <small className="layer-state">
                                {buildingHeightStatus(heightCounts) ||
                                  `${heightAvailableCount} evidence-backed`}
                              </small>
                            )}
                        </span>
                      </label>
                    </div>
                  );
                })
              : !['loading', 'failed', 'unavailable', 'unsupported'].includes(
                  mapSceneState,
                ) && (
                  <p>
                    {mapSceneState === 'idle'
                      ? 'Prepare or select a supported Screening Context run to inspect built-world layers.'
                      : 'Layer availability is unavailable.'}
                  </p>
                )}
            {mapScene && (
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
      {legendOpen && !layerPanelOpen && (
        <section
          id="map-legend"
          className={infrastructureStyles.legendPanel}
          aria-label="Map legend"
        >
          <header>
            <span>
              <strong>Operating legend</strong>
              <small>Visible evidence and object states</small>
            </span>
            <button
              aria-label="Close map legend"
              onClick={() => setLegendOpen(false)}
            >
              <X size={15} />
            </button>
          </header>
          <div className={infrastructureStyles.legendBody}>
            <section>
              <h3>Geography</h3>
              <div className={infrastructureStyles.legendRow}>
                <i
                  className={infrastructureStyles.legendLine}
                  style={{ background: MAP_PALETTE.boundary }}
                />
                <span>Site boundary</span>
              </div>
              {!!linkedProjects.length && (
                <div className={infrastructureStyles.legendRow}>
                  <i
                    className={infrastructureStyles.legendPoint}
                    style={{ background: MAP_PALETTE.project }}
                  />
                  <span>Site-linked Project Subject</span>
                </div>
              )}
            </section>
            <section>
              <h3>Terrene Earth</h3>
              {mapScene ? (
                mapScene.layers.map((layer) => (
                  <div
                    className={infrastructureStyles.legendLayer}
                    data-state={layer.state}
                    key={layer.id}
                  >
                    <span>
                      <i
                        className={
                          layer.id === 'railway_stations'
                            ? infrastructureStyles.legendPoint
                            : infrastructureStyles.legendLine
                        }
                        style={{ background: builtLayerColor(layer.id) }}
                      />
                      <b>{mapLayerLabel(layer.id)}</b>
                    </span>
                    <small>{mapLayerStatus(layer)}</small>
                    {layer.id === 'buildings' && layer.feature_count > 0 && (
                      <small>
                        {buildingHeightStatus(heightCounts) ||
                          `${heightAvailableCount} evidence-backed`}
                      </small>
                    )}
                  </div>
                ))
              ) : (
                <p>
                  {mapSceneState === 'failed'
                    ? 'Scene unavailable; missing evidence is not zero.'
                    : mapSceneState === 'loading'
                      ? 'Loading saved scene…'
                      : 'No saved infrastructure scene selected.'}
                </p>
              )}
              {!!railClassifications.length && (
                <div className={infrastructureStyles.railKey}>
                  {railClassifications.map((classification) => (
                    <span key={classification}>
                      <i
                        style={{
                          background:
                            classification === 'Multi Track'
                              ? MAP_PALETTE.railwayMulti
                              : classification === 'Narrow Gauge'
                                ? MAP_PALETTE.railwayNarrow
                                : MAP_PALETTE.railwaySingle,
                        }}
                      />{' '}
                      {classification}
                    </span>
                  ))}
                </div>
              )}
            </section>
            {!!legendFeatures.length && (
              <section>
                <h3>Objects in this snapshot</h3>
                <p className={infrastructureStyles.objectIndexNote}>
                  One row per retained mapped object. Repeated classifications
                  can form one apparent line on the map.
                </p>
                <div className={infrastructureStyles.legendObjects}>
                  {legendObjectRows.map(({ feature, label }) => (
                    <button
                      key={feature.id}
                      aria-pressed={feature.id === selectedMapObject}
                      onClick={() => onInspectMapObject?.(feature.id)}
                    >
                      <i style={{ background: featureSwatchColor(feature) }} />
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}
            {!!mapScene?.sources.length && (
              <section>
                <h3>Evidence sources</h3>
                <ul className={infrastructureStyles.sourceList}>
                  {mapScene.sources.map((source) => (
                    <li key={source.id}>
                      <strong>{source.provider}</strong>
                      <span>{source.release}</span>
                      <time dateTime={source.retrieved_at}>
                        Retrieved {sourceDate(source.retrieved_at)}
                      </time>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        </section>
      )}
      {rosterOpen &&
        !layerPanelOpen &&
        !legendOpen &&
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
        <small>
          {perspectiveActive ? 'Perspective · 55°' : '2D · top-down'} ·{' '}
          {coordinates || 'WGS84 · EPSG:4326'}
        </small>
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
              {showRelatedObjects && selectedRelationshipTypes.length
                ? ` · Related parcel: ${selectedRelationshipTypes
                    .map((value) => value.replaceAll('_', ' '))
                    .join(', ')}`
                : ''}
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
