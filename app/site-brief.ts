import type {
  ContextItem,
  ScreeningFact,
  ScreeningGap,
  ScreeningMapFeatures,
  ScreeningResult,
} from './screening-context.ts';

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
