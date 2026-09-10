import type { Geometry } from 'geojson';
import type { ScreeningRun } from './screening-context.ts';

export type BuiltWorldLayerId =
  | 'buildings'
  | 'functional_sites'
  | 'railway_tracks'
  | 'railway_stations';
export type MapLayerState =
  | 'available'
  | 'mapped_zero'
  | 'unavailable'
  | 'partial'
  | 'unsupported';

export type MapSource = {
  id: string;
  provider: string;
  dataset: string;
  release: string;
};
export type MapRelationshipMeasurements = {
  overlap_area_m2: number | null;
  parcel_overlap_fraction: number | null;
  object_overlap_fraction: number | null;
  length_within_m: number | null;
  minimum_distance_m: number | null;
};
export type MapRelationship = {
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
  measurements: MapRelationshipMeasurements;
};
export type ScreeningMapFeature = {
  type: 'Feature';
  id: string;
  geometry: Geometry;
  properties: {
    layer_id: BuiltWorldLayerId;
    object_id: string;
    object_type:
      | 'building'
      | 'functional_site'
      | 'railway_track'
      | 'railway_station';
    source: MapSource;
    source_release: string;
    feature_code: number;
    classification: string | null;
    name: string | null;
    site_theme: string | null;
    geometry_fingerprint: string;
    authoritative_geometry_crs: 'EPSG:27700';
    relationships: MapRelationship[];
  };
};
export type LayerMeasurement = {
  observation_id: string;
  definition_id: string;
  value: number;
  unit: string;
  known_zero: boolean;
  availability: 'available' | 'partial';
  coverage_status: 'full' | 'partial' | 'unrecorded_legacy';
  coverage_fraction: number | null;
  numerator: number;
  denominator: number | null;
  numerator_unit: 'm2' | 'm';
  denominator_unit: 'm2' | null;
  aggregation: string;
  supporting_object_ids: string[];
};
export type ScreeningMapLayer = {
  id: BuiltWorldLayerId;
  object_type: ScreeningMapFeature['properties']['object_type'];
  state: MapLayerState;
  feature_count: number;
  coverage_status: 'full' | 'partial' | 'unavailable' | 'unsupported';
  coverage_fraction: number | null;
  coverage_basis: string[];
  qualification: string;
  sources: MapSource[];
  measurements: LayerMeasurement[];
  observation_ids: string[];
  gap_ids: string[];
  gap_reason_codes: string[];
};
export type ScreeningMapFeatures = {
  type: 'FeatureCollection';
  contract_version: 'screening_context_map_features_v1';
  run_id: string;
  evidence_snapshot_id: string;
  evidence_content_hash: string;
  site_id: string;
  boundary_version: number;
  boundary_reference: string;
  boundary_geometry_fingerprint: string;
  evidence_as_of: string;
  presentation_crs: 'EPSG:4326';
  authoritative_geometry_crs: 'EPSG:27700';
  layers: ScreeningMapLayer[];
  features: ScreeningMapFeature[];
  limitations: string[];
};

export function screeningMapFeaturePath(runId: string) {
  return `/api/screening-context-runs/${encodeURIComponent(runId)}/map-features`;
}

function mapFeatureHeaders(): Record<string, string> {
  const token = sessionStorage.getItem('crc-token');
  return token ? { Authorization: 'Bearer ' + token } : {};
}

async function mapFeatureResponse(response: Response) {
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    const detail =
      error && typeof error === 'object' && 'detail' in error
        ? error.detail
        : null;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : `Mapped evidence request failed (${response.status})`,
    );
  }
  return response;
}

export async function readScreeningMapFeatures(
  run: ScreeningRun,
  signal?: AbortSignal,
): Promise<ScreeningMapFeatures> {
  const response = await mapFeatureResponse(
    await fetch(screeningMapFeaturePath(run.id), {
      headers: mapFeatureHeaders(),
      cache: 'no-store',
      signal,
    }),
  );
  const value = (await response.json()) as ScreeningMapFeatures;
  if (
    value.contract_version !== 'screening_context_map_features_v1' ||
    value.type !== 'FeatureCollection' ||
    value.run_id !== run.id ||
    value.site_id !== run.site_id ||
    value.boundary_version !== run.boundary_version ||
    value.evidence_snapshot_id !== run.evidence_snapshot_id ||
    value.evidence_content_hash !== run.result.evidence_content_hash ||
    value.boundary_geometry_fingerprint !==
      run.result.boundary_geometry_fingerprint ||
    value.presentation_crs !== 'EPSG:4326' ||
    value.authoritative_geometry_crs !== 'EPSG:27700'
  ) {
    throw new Error(
      'Mapped evidence does not match the selected Screening Context run.',
    );
  }
  return value;
}

const layerLabels: Record<BuiltWorldLayerId, string> = {
  buildings: 'Buildings',
  functional_sites: 'Functional sites',
  railway_tracks: 'Railway tracks',
  railway_stations: 'Railway stations',
};

export function mapLayerLabel(layer: BuiltWorldLayerId) {
  return layerLabels[layer];
}

export function mapLayerStatus(layer: ScreeningMapLayer) {
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

export function mapFeatureName(feature: ScreeningMapFeature) {
  const properties = feature.properties;
  if (properties.name) return properties.name;
  if (properties.classification)
    return properties.classification.replaceAll('_', ' ');
  if (properties.site_theme) return properties.site_theme.replaceAll('_', ' ');
  return mapLayerLabel(properties.layer_id).replace(/s$/, '');
}

export function formatMappedMeasurement(value: number, unit: string) {
  if (unit === 'fraction')
    return `${(value * 100).toLocaleString('en-GB', { maximumFractionDigits: 4 })}%`;
  const label = unit === 'm' ? 'm' : unit === 'm2' ? 'm²' : unit;
  return `${value.toLocaleString('en-GB', { maximumFractionDigits: 2 })} ${label}`;
}

export function mapRelationshipSummary(relationship: MapRelationship) {
  const measurements = relationship.measurements;
  const label = {
    contained_within: 'Contained within the parcel',
    overlaps: 'Overlaps the parcel',
    touches: 'Touches the parcel boundary',
    crosses: 'Crosses the parcel',
    intersects: 'Intersects the parcel',
    minimum_distance: 'Nearest mapped relationship',
  }[relationship.predicate];
  const values = [
    measurements.overlap_area_m2 === null
      ? null
      : `${measurements.overlap_area_m2.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m² overlap`,
    measurements.parcel_overlap_fraction === null
      ? null
      : `${(measurements.parcel_overlap_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 4 })}% of parcel`,
    measurements.object_overlap_fraction === null
      ? null
      : `${(measurements.object_overlap_fraction * 100).toLocaleString('en-GB', { maximumFractionDigits: 2 })}% of object`,
    measurements.length_within_m === null
      ? null
      : `${measurements.length_within_m.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m within parcel`,
    measurements.minimum_distance_m === null
      ? null
      : `${measurements.minimum_distance_m.toLocaleString('en-GB', { maximumFractionDigits: 2 })} m minimum mapped distance`,
  ].filter(Boolean);
  return values.length ? `${label} · ${values.join(' · ')}` : label;
}

export const builtWorldLayerIds: BuiltWorldLayerId[] = [
  'buildings',
  'functional_sites',
  'railway_tracks',
  'railway_stations',
];
