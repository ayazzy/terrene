import type { Geometry } from 'geojson';
import type { ScreeningRun } from './screening-context.ts';

export type InfrastructureLayerId =
  | 'buildings'
  | 'functional_sites'
  | 'railway_tracks'
  | 'railway_stations';
export type InfrastructureLayerState =
  | 'available'
  | 'mapped_zero'
  | 'unavailable'
  | 'partial'
  | 'unsupported';

export type SceneSource = {
  id: string;
  provider: string;
  dataset: string;
  release: string;
  source_url: string;
  retrieved_at: string;
  reference_period: {
    status: 'recorded' | 'not_recorded_legacy';
    value: string | null;
    qualification: string | null;
  };
  attribution: string | null;
};

export type SceneRelationshipMeasurements = {
  overlap_area_m2: number | null;
  parcel_overlap_fraction: number | null;
  object_overlap_fraction: number | null;
  length_within_m: number | null;
  minimum_distance_m: number | null;
};

export type SceneRelationship = {
  id: string;
  predicate:
    | 'overlaps'
    | 'touches'
    | 'contained_within'
    | 'crosses'
    | 'intersects'
    | 'minimum_distance';
  geometry_semantics: string;
  support_crs: 'EPSG:27700';
  measurements: SceneRelationshipMeasurements;
};

export type SceneHeight = {
  state: 'available' | 'partial' | 'gap' | 'unsupported';
  observation_id: string | null;
  gap_id: string | null;
  gap_state: string | null;
  reason_code: string | null;
  p50_height_m: number | null;
  p90_height_m: number | null;
  extrusion_height_m: number | null;
  sample_count: number | null;
  coverage_fraction: number | null;
  evidence_time: string | null;
  source_reference_ids: string[];
  qualification: string;
};

export type InfrastructureSceneFeature = {
  type: 'Feature';
  id: string;
  geometry: Geometry;
  properties: {
    layer_id: InfrastructureLayerId;
    object_id: string;
    object_type:
      | 'building'
      | 'functional_site'
      | 'railway_track'
      | 'railway_station';
    object_source_id: string;
    source_release: string;
    feature_code: number;
    classification: string | null;
    name: string | null;
    site_theme: string | null;
    geometry_fingerprint: string;
    authoritative_geometry_crs: 'EPSG:27700';
    relationships: SceneRelationship[];
    height: SceneHeight | null;
  };
};

export type InfrastructureSceneLayer = {
  id: InfrastructureLayerId;
  object_type: InfrastructureSceneFeature['properties']['object_type'];
  state: InfrastructureLayerState;
  feature_count: number;
  source_reference_ids: string[];
  height_available_count: number;
  height_gap_count: number;
  height_unsupported_count: number;
  qualification: string;
};

export type InfrastructureMapScene = {
  type: 'FeatureCollection';
  contract_version: 'infrastructure_map_scene_v1';
  snapshot: {
    id: string;
    schema_version: string;
    registry_version: string;
    content_hash: string;
    created: string;
  };
  site: { id: string; name: string | null; geography: string };
  boundary: {
    version: number;
    reference: string;
    geometry_fingerprint: string;
    authoritative_crs: 'EPSG:27700';
  };
  evidence_as_of: string;
  presentation_crs: 'EPSG:4326';
  authoritative_geometry_crs: 'EPSG:27700';
  sources: SceneSource[];
  layers: InfrastructureSceneLayer[];
  capabilities: {
    id:
      | 'native_geojson_selection'
      | 'parcel_relationships'
      | 'evidence_backed_building_extrusion';
    state: 'available' | 'partial' | 'unavailable' | 'unsupported';
    qualification: string;
  }[];
  features: InfrastructureSceneFeature[];
  limitations: string[];
};

export type BuildingHeightStateCounts = {
  available: number;
  partial: number;
  gap: number;
  unsupported: number;
  unrecorded: number;
};

export function buildingHeightStateCounts(
  scene: InfrastructureMapScene | null | undefined,
): BuildingHeightStateCounts {
  const counts: BuildingHeightStateCounts = {
    available: 0,
    partial: 0,
    gap: 0,
    unsupported: 0,
    unrecorded: 0,
  };
  for (const feature of scene?.features || []) {
    if (feature.properties.layer_id !== 'buildings') continue;
    const state = feature.properties.height?.state;
    if (state) counts[state] += 1;
    else counts.unrecorded += 1;
  }
  return counts;
}

export function buildingHeightStatus(
  counts: BuildingHeightStateCounts,
): string | null {
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  if (!total) return null;
  const extruded = counts.available + counts.partial;
  const flat = counts.gap + counts.unsupported + counts.unrecorded;
  if (counts.unsupported === total)
    return `Historical snapshot · ${total} ${total === 1 ? 'building remains' : 'buildings remain'} flat because height evidence is unsupported`;
  if (!extruded)
    return `Height unavailable · ${flat} ${flat === 1 ? 'building remains' : 'buildings remain'} flat; missing evidence is not zero`;
  if (counts.partial && !flat)
    return `Partial evidence · ${counts.partial} of ${extruded} building ${extruded === 1 ? 'estimate' : 'estimates'} ${counts.partial === 1 ? 'has' : 'have'} a partial state`;
  if (counts.partial || flat)
    return `Partial height coverage · ${extruded} evidence-backed · ${flat} flat`;
  return null;
}

export const infrastructureLayerIds: InfrastructureLayerId[] = [
  'buildings',
  'functional_sites',
  'railway_tracks',
  'railway_stations',
];

const layerLabels: Record<InfrastructureLayerId, string> = {
  buildings: 'Buildings',
  functional_sites: 'Functional sites',
  railway_tracks: 'Railway tracks',
  railway_stations: 'Railway stations',
};

export function infrastructureMapScenePath(snapshotId: string) {
  return `/api/land-evidence-snapshots/${encodeURIComponent(snapshotId)}/map-scene`;
}

function sceneHeaders(): Record<string, string> {
  const token = sessionStorage.getItem('crc-token');
  return token ? { Authorization: 'Bearer ' + token } : {};
}

export async function readInfrastructureMapScene(
  run: ScreeningRun,
  signal?: AbortSignal,
): Promise<InfrastructureMapScene> {
  const response = await fetch(
    infrastructureMapScenePath(run.evidence_snapshot_id),
    { headers: sceneHeaders(), cache: 'no-store', signal },
  );
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    const detail =
      error && typeof error === 'object' && 'detail' in error
        ? error.detail
        : null;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : `Infrastructure scene request failed (${response.status})`,
    );
  }
  const value = (await response.json()) as InfrastructureMapScene;
  if (
    value.contract_version !== 'infrastructure_map_scene_v1' ||
    value.type !== 'FeatureCollection' ||
    value.snapshot.id !== run.evidence_snapshot_id ||
    value.snapshot.content_hash !== run.result.evidence_content_hash ||
    value.site.id !== run.site_id ||
    value.boundary.version !== run.boundary_version ||
    value.boundary.geometry_fingerprint !==
      run.result.boundary_geometry_fingerprint ||
    value.presentation_crs !== 'EPSG:4326' ||
    value.authoritative_geometry_crs !== 'EPSG:27700'
  ) {
    throw new Error(
      'Infrastructure scene does not match the selected immutable evidence snapshot.',
    );
  }
  return value;
}

export function mapLayerLabel(layer: InfrastructureLayerId) {
  return layerLabels[layer];
}

export function mapLayerStatus(layer: InfrastructureSceneLayer) {
  if (layer.state === 'available')
    return `${layer.feature_count} mapped ${layer.feature_count === 1 ? 'object' : 'objects'}`;
  if (layer.state === 'mapped_zero') return 'Mapped zero · source-bounded';
  if (layer.state === 'partial')
    return layer.feature_count
      ? `Partial coverage · ${layer.feature_count} mapped ${layer.feature_count === 1 ? 'object' : 'objects'}`
      : 'Partial coverage · no complete zero claim';
  if (layer.state === 'unsupported') return 'Unsupported historical evidence';
  return 'Unavailable';
}

export function mapFeatureName(feature: InfrastructureSceneFeature) {
  const properties = feature.properties;
  if (properties.name) return properties.name;
  if (properties.classification)
    return properties.classification.replaceAll('_', ' ');
  if (properties.site_theme) return properties.site_theme.replaceAll('_', ' ');
  return mapLayerLabel(properties.layer_id).replace(/s$/, '');
}

export function mapRelationshipSummary(relationship: SceneRelationship) {
  const presentation = mapRelationshipPresentation(relationship);
  return presentation.metrics.length
    ? `${presentation.label} · ${presentation.metrics
        .map((metric) => metric.summary)
        .join(' · ')}`
    : presentation.label;
}

export function mapRelationshipPresentation(relationship: SceneRelationship) {
  const measurements = relationship.measurements;
  const label = {
    contained_within: 'Contained within the parcel',
    overlaps: 'Overlaps the parcel',
    touches: 'Touches the parcel boundary',
    crosses: 'Crosses the parcel',
    intersects: 'Intersects the parcel',
    minimum_distance: 'Nearest mapped relationship',
  }[relationship.predicate];
  const metrics = [
    measurements.overlap_area_m2 === null
      ? null
      : {
          key: 'overlap-area',
          label: 'Overlap area',
          value: `${measurements.overlap_area_m2.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m²`,
          summary: `${measurements.overlap_area_m2.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m² overlap`,
        },
    measurements.parcel_overlap_fraction === null
      ? null
      : {
          key: 'parcel-overlap',
          label: 'Parcel overlap',
          value: `${(measurements.parcel_overlap_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 4 })}%`,
          summary: `${(measurements.parcel_overlap_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 4 })}% of parcel`,
        },
    measurements.object_overlap_fraction === null
      ? null
      : {
          key: 'object-overlap',
          label: 'Object overlap',
          value: `${(measurements.object_overlap_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 2 })}%`,
          summary: `${(measurements.object_overlap_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 2 })}% of object`,
        },
    measurements.length_within_m === null
      ? null
      : {
          key: 'length-within',
          label: 'Length in parcel',
          value: `${measurements.length_within_m.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m`,
          summary: `${measurements.length_within_m.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m within parcel`,
        },
    measurements.minimum_distance_m === null
      ? null
      : {
          key: 'minimum-distance',
          label: 'Mapped distance',
          value: `${measurements.minimum_distance_m.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m`,
          summary: `${measurements.minimum_distance_m.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m minimum mapped distance`,
        },
  ].filter((metric) => metric !== null);
  return { label, metrics };
}
