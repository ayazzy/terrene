import type {
  ContextItem,
  ScreeningFact,
  ScreeningGap,
  ScreeningResult,
} from './screening-context.ts';
import type { ScreeningMapFeatures } from './screening-map-features.ts';

export type SiteBriefFact = ScreeningFact & {
  mapKey?: string;
  briefLabel: string;
  category:
    | 'Built context'
    | 'Ecology'
    | 'Water'
    | 'Transport'
    | 'Designation'
    | 'Terrain';
};

const FACT_POLICY: Record<
  string,
  {
    priority: number;
    category: SiteBriefFact['category'];
    briefLabel: string;
    mapKey?: string;
  }
> = {
  'built.mapped_built_up_fraction': {
    priority: 120,
    category: 'Built context',
    briefLabel: 'Mapped built-up land',
  },
  'built.building.mapped_overlap_fraction': {
    priority: 116,
    category: 'Built context',
    briefLabel: 'Mapped building footprint',
    mapKey: 'context:buildings',
  },
  'built.functional_site.mapped_overlap_fraction': {
    priority: 94,
    category: 'Built context',
    briefLabel: 'Mapped functional-site footprint',
    mapKey: 'context:functional_sites',
  },
  'ecology.priority_habitat.any_mapped_overlap_fraction': {
    priority: 112,
    category: 'Ecology',
    briefLabel: 'Priority-habitat overlap',
    mapKey: 'priority_habitats',
  },
  'physical.flood.mapped_extent_fraction': {
    priority: 108,
    category: 'Water',
    briefLabel: 'Mapped flood-zone context',
    mapKey: 'flood',
  },
  'physical.watercourse.intersects': {
    priority: 106,
    category: 'Water',
    briefLabel: 'Watercourse intersects the parcel',
  },
  'physical.watercourse.distance_min': {
    priority: 100,
    category: 'Water',
    briefLabel: 'Nearest mapped watercourse',
  },
  'transport.railway_track.mapped_length_within': {
    priority: 104,
    category: 'Transport',
    briefLabel: 'Mapped railway within the parcel',
    mapKey: 'context:railway_tracks',
  },
  'transport.railway_track.distance_min': {
    priority: 91,
    category: 'Transport',
    briefLabel: 'Nearest mapped railway track',
    mapKey: 'context:railway_tracks',
  },
  'transport.railway_station.distance_min': {
    priority: 89,
    category: 'Transport',
    briefLabel: 'Nearest mapped railway station',
    mapKey: 'context:railway_stations',
  },
  'designations.overlap_fraction': {
    priority: 102,
    category: 'Designation',
    briefLabel: 'SSSI mapped overlap',
    mapKey: 'sssi',
  },
  'ecology.ancient_woodland.mapped_overlap_fraction': {
    priority: 96,
    category: 'Designation',
    briefLabel: 'Ancient Woodland mapped overlap',
  },
  'ecology.land_cover.dominant_class': {
    priority: 88,
    category: 'Ecology',
    briefLabel: 'Dominant mapped land cover',
  },
  'ecology.mapped_herbaceous_wetland_fraction': {
    priority: 84,
    category: 'Ecology',
    briefLabel: 'Mapped herbaceous wetland',
  },
  'physical.mapped_permanent_water_fraction': {
    priority: 82,
    category: 'Water',
    briefLabel: 'Mapped permanent water',
  },
  'physical.slope.mean': {
    priority: 30,
    category: 'Terrain',
    briefLabel: 'Mean slope',
  },
  'physical.slope.p90': {
    priority: 24,
    category: 'Terrain',
    briefLabel: 'Upper-range slope',
  },
};

const EVIDENCE_FACT_LABELS: Record<string, string> = {
  'physical.elevation.mean': 'Average ground elevation',
  'physical.elevation.minimum': 'Lowest ground elevation',
  'physical.elevation.maximum': 'Highest ground elevation',
  'physical.elevation.stddev': 'Ground elevation variation',
  'physical.slope.mean': 'Average ground slope',
  'physical.slope.p90': 'Upper-range ground slope',
  'physical.slope.maximum': 'Maximum ground slope',
  'physical.watercourse.distance_min': 'Nearest mapped watercourse',
  'physical.watercourse.intersects': 'Watercourse intersects the parcel',
  'physical.watercourse.proximity_area_fraction':
    'Land near a mapped watercourse',
  'ecology.land_cover.class_distribution': 'Mapped land-cover mix',
  'ecology.land_cover.dominant_class': 'Dominant mapped land cover',
  'built.mapped_built_up_fraction': 'Mapped built-up land',
  'ecology.mapped_herbaceous_wetland_fraction': 'Mapped herbaceous wetland',
  'physical.mapped_permanent_water_fraction': 'Mapped permanent water',
  'physical.flood.mapped_extent_fraction': 'Mapped flood-zone context',
  'designations.overlap_fraction': 'SSSI mapped overlap',
  'ecology.ancient_woodland.mapped_overlap_fraction':
    'Ancient Woodland mapped overlap',
  'ecology.priority_habitat.mapped_overlap_fraction':
    'Mapped priority-habitat overlap by type',
  'ecology.priority_habitat.any_mapped_overlap_fraction':
    'Priority-habitat mapped overlap',
  'built.building.mapped_overlap_fraction': 'Mapped building footprint',
  'built.functional_site.mapped_overlap_fraction':
    'Mapped functional-site footprint',
  'built.building.height_estimate': 'Historical surface-height estimate',
  'transport.railway_track.mapped_length_within':
    'Mapped railway within the parcel',
  'transport.railway_track.distance_min': 'Nearest mapped railway track',
  'transport.railway_station.distance_min': 'Nearest mapped railway station',
};

const GAP_REASON_LABELS: Record<string, string> = {
  absent_legacy_finding: 'Earlier assessment did not retain this finding',
  absent_observation: 'Observation was not retained',
  acquisition_failure: 'Source acquisition failed',
  category_uninterpretable: 'Saved category could not be interpreted',
  incomplete_inventory: 'Source inventory is incomplete',
  legacy_distribution_format_unrecognized:
    'Earlier distribution format is unsupported',
  legacy_distribution_malformed: 'Earlier distribution record is invalid',
  legacy_finding_required: 'Earlier mapped finding is required',
  missing_object_outcome: 'Building estimate was not produced',
  no_mapped_object_within_search_radius:
    'No mapped object found within the retained search area',
  outside_acquired_coverage: 'Parcel is outside acquired source coverage',
  outside_acquired_extent: 'Parcel is outside the retained source extent',
  partial_acquired_coverage: 'Only part of the parcel has source coverage',
  partial_search_coverage: 'Mapped search coverage is incomplete',
  processing_unavailable: 'Processing result is unavailable',
  source_not_connected: 'Required source is not connected',
  source_unavailable: 'Source data is unavailable',
  source_unconnected: 'Required source is not connected',
  value_uninterpretable: 'Saved value could not be interpreted',
};

const GAP_DEFINITION_LABELS: Record<string, string> = {
  'physical.flood.mapped_extent_fraction': 'Flood-zone evidence',
  'built.infrastructure.complete_footprint_fraction':
    'Complete infrastructure footprint',
};

function readableToken(value: string) {
  const text = value.replaceAll('_', ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const GAP_PRIORITY: Array<[string, number, string]> = [
  ['soil.drainage', 120, 'Soil drainage evidence'],
  ['groundwater', 116, 'Groundwater evidence'],
  ['habitat_condition', 112, 'Current habitat condition'],
  ['wetland', 108, 'Actual wetland extent'],
  ['water_quality', 104, 'Water quality evidence'],
  ['hydroperiod', 100, 'Seasonal water regime'],
  ['railway', 94, 'Complete railway search coverage'],
  ['priority_habitat', 90, 'Priority-habitat evidence'],
  ['designation', 88, 'Designation evidence'],
  ['irreplaceable_habitat', 86, 'Complete irreplaceable-habitat context'],
];

function allFacts(result: ScreeningResult) {
  return result.groups.flatMap((group) => group.facts);
}

function factPriority(fact: ScreeningFact) {
  const policy = FACT_POLICY[fact.definition_id];
  if (!policy) return -1;
  let priority = policy.priority;
  if (fact.known_zero) priority -= 4;
  if (fact.availability === 'partial') priority += 3;
  return priority;
}

export function siteBriefValue(fact: ScreeningFact) {
  const value = fact.value;
  if (value.kind === 'distribution')
    return value.entries
      .slice(0, 2)
      .map(
        (entry) =>
          `${entry.category}: ${(entry.value * 100).toLocaleString('en-GB', { maximumFractionDigits: 1 })}%`,
      )
      .join(' · ');
  if (typeof value.value === 'boolean') return value.value ? 'Yes' : 'No';
  if (typeof value.value === 'string') return value.value.replaceAll('_', ' ');
  const multiplier = fact.unit === 'fraction' ? 100 : 1;
  const suffix =
    fact.unit === 'fraction'
      ? '%'
      : fact.unit === 'degree'
        ? '°'
        : ` ${fact.unit}`;
  return `${(value.value * multiplier).toLocaleString('en-GB', { maximumFractionDigits: 1 })}${suffix}`;
}

export function siteBriefLabel(
  fact: SiteBriefFact,
  map?: ScreeningMapFeatures | null,
) {
  const layerId = fact.mapKey?.startsWith('context:')
    ? fact.mapKey.slice(8)
    : '';
  const layer = map?.layers.find((item) => item.id === layerId);
  if (!layer) return fact.briefLabel;
  const plural = layer.feature_count === 1 ? '' : 's';
  if (fact.definition_id === 'built.building.mapped_overlap_fraction')
    return `${layer.feature_count} mapped building${plural}`;
  if (fact.definition_id === 'built.functional_site.mapped_overlap_fraction')
    return `${layer.feature_count} mapped functional site${plural}`;
  if (fact.definition_id === 'transport.railway_track.mapped_length_within') {
    const crosses = map?.features.some(
      (feature) =>
        feature.properties.layer_id === 'railway_tracks' &&
        feature.properties.relationships.some(
          (relationship) => relationship.predicate === 'crosses',
        ),
    );
    return crosses
      ? 'Railway crosses the parcel'
      : `${layer.feature_count} mapped railway track object${plural}`;
  }
  return fact.briefLabel;
}

export function evidenceFactLabel(
  fact: ScreeningFact,
  map?: ScreeningMapFeatures | null,
) {
  const policy = FACT_POLICY[fact.definition_id];
  if (policy) return siteBriefLabel({ ...fact, ...policy }, map);
  return EVIDENCE_FACT_LABELS[fact.definition_id] || fact.label;
}

export function evidenceAvailabilityLabel(fact: ScreeningFact) {
  if (fact.availability === 'partial') return 'Partial source coverage';
  if (fact.known_zero) {
    if (fact.unit === 'fraction') return 'No overlap mapped in retained source';
    if (fact.value.kind === 'boolean')
      return 'No intersection mapped in retained source';
    if (fact.definition_id.endsWith('.distance_min'))
      return 'Zero mapped distance in retained source';
    return 'Known zero in retained source';
  }
  return 'Retained source evidence';
}

export function evidenceGapReasonLabel(gap: ScreeningGap) {
  return GAP_REASON_LABELS[gap.reason_code] || readableToken(gap.reason_code);
}

export function evidenceGapStateLabel(gap: ScreeningGap) {
  if (gap.state === 'source_not_connected') return 'Source not connected';
  if (gap.state === 'incomplete_inventory') return 'Inventory incomplete';
  if (gap.state === 'absent_observation') return 'Not retained';
  if (gap.state === 'unavailable') return 'Not established';
  return readableToken(gap.state);
}

export function sitePictureFacts(result: ScreeningResult): SiteBriefFact[] {
  const ranked = prioritizeFacts(result, 20);
  const meaningful = ranked.filter((fact) => !fact.known_zero);
  const chosen: SiteBriefFact[] = [];
  for (const fact of meaningful.length ? meaningful : ranked) {
    if (!chosen.some((item) => item.category === fact.category))
      chosen.push(fact);
    if (chosen.length === 3) break;
  }
  return chosen.length ? chosen : ranked.slice(0, 3);
}

export function prioritizeFacts(
  result: ScreeningResult,
  limit = 6,
): SiteBriefFact[] {
  return allFacts(result)
    .filter((fact) => factPriority(fact) >= 0)
    .map((fact) => ({ ...fact, ...FACT_POLICY[fact.definition_id] }))
    .sort(
      (a, b) => factPriority(b) - factPriority(a) || a.id.localeCompare(b.id),
    )
    .slice(0, limit);
}

function gapIdentity(gap: ScreeningGap) {
  return `${gap.definition_id || ''} ${gap.legacy_variable || ''} ${gap.reason_code}`.toLowerCase();
}

export function gapLabel(gap: ScreeningGap) {
  const identity = gapIdentity(gap);
  return (
    GAP_DEFINITION_LABELS[gap.definition_id || ''] ||
    GAP_DEFINITION_LABELS[gap.legacy_variable || ''] ||
    GAP_PRIORITY.find(([term]) => identity.includes(term))?.[2] ||
    (gap.definition_id || gap.legacy_variable || gap.reason_code)
      .replaceAll('.', ' · ')
      .replaceAll('_', ' ')
  );
}

export function prioritizeGaps(
  result: ScreeningResult,
  limit = 4,
): ScreeningGap[] {
  return result.groups
    .flatMap((group) => group.gaps)
    .map((gap) => ({
      gap,
      priority:
        GAP_PRIORITY.find(([term]) => gapIdentity(gap).includes(term))?.[1] ||
        1,
    }))
    .sort((a, b) => b.priority - a.priority || a.gap.id.localeCompare(b.gap.id))
    .slice(0, limit)
    .map(({ gap }) => gap);
}

export function prioritizeQuestions(
  result: ScreeningResult,
  limit = 4,
): ContextItem[] {
  const importantGapIds = new Set(
    prioritizeGaps(result, 8).map((gap) => gap.id),
  );
  const ranked = [...result.review_questions].sort((a, b) => {
    const score = (item: ContextItem) =>
      (item.id.startsWith('question:') ? 30 : 0) +
      (item.references.gap_ids.some((id) => importantGapIds.has(id)) ? 20 : 0) +
      (item.id.startsWith('capability-question:') ? -20 : 0);
    return score(b) - score(a) || a.id.localeCompare(b.id);
  });
  const seen = new Set<string>();
  return ranked
    .filter((item) => {
      const visibleText = item.text
        .trim()
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .replace(/[.?!]+$/, '');
      if (seen.has(visibleText)) return false;
      seen.add(visibleText);
      return true;
    })
    .slice(0, limit);
}
