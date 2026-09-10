import type { Geometry } from 'geojson';
import type { EvidenceState } from './status-primitives';

export type OverlayFinding = {
  key: string;
  dataset: string;
  dataset_version: string;
  geometry: Geometry | null;
  measured: number | null;
  percent?: number;
};

export const humanize = (value: string) =>
  value.replaceAll('_', ' ').replaceAll('.', ' · ');
const labels: Record<string, string> = {
  'terrain.slope_deg': 'Mean slope',
  'terrain.slope_p90_deg': '90th percentile slope',
  'terrain.slope_max_deg': 'Maximum slope',
  'terrain.elevation_m': 'Mean elevation',
  'terrain.elevation_min_m': 'Minimum elevation',
  'terrain.elevation_max_m': 'Maximum elevation',
  'terrain.elevation_std_m': 'Elevation standard deviation',
  'regulatory.protected_area_fraction': 'Mapped protected-area overlap',
  'ecology.distance_to_habitat_m': 'Distance to relevant habitat',
  'ecology.habitat_proximity_index': 'Habitat proximity',
  'hydrology.groundwater_depth_m': 'Groundwater depth',
  'hydrology.flow_accumulation': 'Catchment flow accumulation',
  'climate.annual_precipitation_mm': 'Annual precipitation',
  'hydrology.distance_to_water_m': 'Distance to mapped watercourse',
  'hydrology.watercourse_intersection': 'Watercourse intersects boundary',
  'hydrology.within_100m_watercourse_fraction':
    'Within 100 m of mapped watercourse',
  'hydrology.mapped_flood_extent_fraction': 'Mapped flood-zone overlap',
  'hydrology.water_context_index': 'Water context',
  'hydrology.surface_water_fraction': 'Mapped permanent water',
  'land_use.current_cover': 'Mapped land cover',
  'land_use.developed_fraction': 'Mapped developed land',
  'soil.drainage_class': 'Soil drainage',
  'soil.retention_index': 'Soil retention',
  'ecology.mapped_wetland_fraction': 'Mapped herbaceous wetland',
  'ecology.wetland_fraction': 'Actual wetland extent',
  'ecology.habitat_condition': 'Habitat condition',
  'ecology.irreplaceable_habitat_fraction': 'Irreplaceable habitat extent',
  'human.infrastructure_fraction': 'Infrastructure footprint',
  'ecology.restoration_need_index': 'Restoration need',
  'human.unblocked_area_index': 'Implementation feasibility',
};
export const variableLabel = (variable: string) =>
  labels[variable] || humanize(variable);
export function observationState(o: {
  value: unknown;
  epistemic_status?: string;
  input_coverage?: number;
  observed_or_derived?: string;
}): EvidenceState {
  if (o.value === null || o.value === undefined) return 'unavailable';
  if (
    o.epistemic_status === 'partial' ||
    (o.input_coverage !== undefined && o.input_coverage < 1)
  )
    return 'partial';
  return o.observed_or_derived === 'derived' ? 'modelled' : 'available';
}
export function observationValue(o: {
  value: number | string | null;
  variable?: string;
  unit?: string;
}) {
  if (o.value === null) return 'Evidence unavailable';
  if (o.variable === 'hydrology.watercourse_intersection') {
    if (o.value === 'yes' || o.value === 1) return 'Yes';
    if (o.value === 'no' || o.value === 0) return 'No';
    return humanize(String(o.value));
  }
  if (typeof o.value === 'string') return humanize(o.value);
  const fraction = o.unit === 'fraction';
  return `${(fraction ? o.value * 100 : o.value).toLocaleString('en-GB', { maximumFractionDigits: 2 })}${fraction ? '%' : o.unit === 'degrees' || o.unit === 'degree' ? '°' : o.unit && o.unit !== 'normalized_index' ? ' ' + o.unit : ''}`;
}
export function componentBand(c: { band?: string; score: number | null }) {
  if (c.score === null) return 'Insufficient evidence';
  if (c.band)
    return c.band === 'INSUFFICIENT_DATA'
      ? 'Insufficient evidence'
      : humanize(c.band.toLowerCase());
  return c.score >= 85
    ? 'Very high'
    : c.score >= 65
      ? 'High'
      : c.score >= 35
        ? 'Moderate'
        : c.score >= 15
          ? 'Low'
          : 'Very low';
}
// Match saved provenance, never infer a displayable raster from a variable name.
export function linkedFindings<
  T extends { key: string; dataset_version: string },
>(o: { raw_source_ids: string[] }, findings: T[]) {
  return findings.filter((f) => o.raw_source_ids.includes(f.dataset_version));
}
export const layerGroup = (key: string) =>
  key === 'flood'
    ? 'Hydrology'
    : ['woodland', 'woodland_revised', 'sssi'].includes(key)
      ? 'Ecology & designations'
      : 'Reference layers';
export const layerColor = (key: string) =>
  key === 'flood'
    ? 'var(--water)'
    : key === 'sssi'
      ? 'var(--soil)'
      : 'var(--vegetation)';
