"""Existing England overlay outputs -> CRC concepts; no source names in models."""
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass

from backend.earth import EarthState, Observation, RawSource, SpatialReference, fingerprint, normalize_unit

ADAPTER_VERSION = 'crc_england_overlay_v0_1'


@dataclass(frozen=True)
class OverlayAdapter:
    key: str
    variable: str
    publisher: str
    priority: int
    quality: float
    absence_is_unknown: bool = False

    def normalize(self, finding: dict, state: EarthState) -> Observation:
        covered = finding['coverage'] == 'covered'
        value = finding.get('fraction') if covered else None
        if value is None and covered and finding.get('percent') is not None:
            value = normalize_unit(finding['percent'], '%', self.variable)
        reason = None if value is not None else 'Source unavailable or parcel outside the imported extent.'
        if self.absence_is_unknown and value == 0:
            value = None
            reason = 'No mapped overlap; inventory completeness is not established. Absence remains unknown.'
        return Observation(
            id=fingerprint([ADAPTER_VERSION, finding['dataset_version'], state.location_id,
                            state.boundary_version, self.variable]),
            variable=self.variable, value=value, unit='fraction', source=self.publisher,
            source_dataset=finding['dataset'], source_version=finding['dataset_version'],
            source_url=finding['source_url'], timestamp=finding.get('observed_at'),
            retrieved_at=finding['retrieved'],
            spatial=SpatialReference(
                geometry_or_cell_reference=f'{state.location_id}/boundary/{state.boundary_version}',
                spatial_resolution_m=finding.get('spatial_resolution_m'),
                aggregation='Union within this layer, intersect parcel in EPSG:27700, overlap area / parcel area'),
            method=ADAPTER_VERSION + ' / ' + finding['method'], observed_or_derived='derived',
            epistemic_status=('modelled' if self.key == 'flood' else 'inferred') if value is not None else 'unknown',
            confidence=self.quality if value is not None else 0,
            uncertainty=finding['limitations'] + ' Source acquisition time and effective spatial resolution may be unknown. Confidence is a provisional data-quality judgement, not a probability of correctness.',
            raw_source_ids=[finding['dataset_version']], missing_reason=reason,
            synthetic=finding.get('synthetic', False),
        )


ENGLAND_ADAPTERS = (
    OverlayAdapter('flood', 'hydrology.mapped_flood_extent_fraction', 'Environment Agency', 100, .65),
    OverlayAdapter('sssi', 'regulatory.protected_area_fraction', 'Natural England', 100, .75),
    OverlayAdapter('woodland_revised', 'ecology.irreplaceable_habitat_fraction', 'Natural England', 100, .6, True),
    OverlayAdapter('woodland', 'ecology.irreplaceable_habitat_fraction', 'Natural England', 50, .5, True),
)
# Future countries register adapters with the same normalize() contract here.
COUNTRIES = {'England': ENGLAND_ADAPTERS}


def select_observations(state: EarthState, candidates: list[tuple[int, Observation]]) -> None:
    groups = defaultdict(list)
    for priority, observation in candidates:
        groups[observation.variable].append((priority, observation))
    for variable, group in sorted(groups.items()):
        ordered = sorted(group, key=lambda pair: (-pair[0], pair[1].source_version, pair[1].id))
        domain, name = variable.split('.', 1)
        state.normalized.setdefault(domain, {})[name] = [o for _, o in ordered]
        known = [(p, o) for p, o in ordered if o.value is not None]
        if variable == 'ecology.irreplaceable_habitat_fraction' and known:
            # A later incomplete inventory must never erase a known positive overlap.
            chosen = max(known, key=lambda pair: (pair[1].value, pair[0]))[1]
            note = 'Largest known mapped overlap retained as a conservative lower bound; overlapping inventories are never summed. Zero in an incomplete inventory remains unknown.'
        else:
            chosen = (known or ordered)[0][1]
            note = 'Highest-priority available provider; fall back only to a registered covered provider. All candidates retained.'
        state.selected[variable] = chosen.id
        state.selection_notes[variable] = note


def normalize_findings(job: dict, findings: list[dict]) -> EarthState:
    state = EarthState(location_id=job['site_id'], boundary_version=job['version'],
                       geography='England', as_of=job['created'], geometry=deepcopy(job['geometry']))
    adapters = {a.key: a for a in COUNTRIES[state.geography]}
    candidates = []
    for f in findings:
        adapter = adapters.get(f['key'])
        state.raw.append(RawSource(
            id=f['dataset_version'], source=adapter.publisher if adapter else f['dataset'],
            source_dataset=f['dataset'], source_version=f['dataset_version'],
            source_url=f['source_url'], retrieved_at=f['retrieved'], timestamp=f.get('observed_at'),
            storage_reference=f.get('raw_storage_reference'), checksum=f.get('raw_sha256'),
            raw_semantics=f.get('raw_semantics', 'Legacy snapshot: attributes retained; repaired original geometries, when present, are retained in metadata. Not an untouched source response.'),
            synthetic=f.get('synthetic', False),
        ))
        if adapter:
            candidates.append((adapter.priority, adapter.normalize(f, state)))
    select_observations(state, candidates)
    return state
