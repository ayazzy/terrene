"""Offline, deterministic human-review context. Pilot rules, not a decision model."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, model_validator

from backend.earth import fingerprint
from backend.land_evidence import (
    BUILDING_HEIGHT_REGISTRY_VERSION, BuildingHeightEvidenceGap,
    BuildingHeightObservation, BuiltWorldMeasurement, BuiltWorldObject,
    CapabilityDisposition, DimensionValue, EvidenceGap, LandEvidenceProjection,
    NumericValue, ObservationDefinition, ParcelObjectRelationship, Record,
    PriorityHabitatMeasurement, SourceFeatureReference, SpatialSupport, TemporalReference, TypedValue,
    validate_land_evidence,
)

MODULE_ID = 'site_screening_context'
MODULE_VERSION = 'site_screening_context_v1'
BINDING_VERSION = 'screening_context_binding_v1'
GROUPS = (
    ('physical_hydrological', 'Physical and hydrological evidence'),
    ('ecology_designations', 'Ecology, habitat and designation evidence'),
    ('built_transport', 'Built-world and transport evidence'),
)
LIMITATIONS = [
    'Pilot learning instrument: these rules are not externally validated requirements.',
    'Source-bounded review context only. It does not establish suitability or make a site-progression decision.',
    'Mapped absence does not prove real-world absence. Evidence completeness is not predictive confidence.',
    'Evidence is fixed to this snapshot; source age, acquired coverage and inventory limitations still apply.',
]
CROSS_RULES = (
    ('built_semantics', ('built.mapped_built_up_fraction', 'built.building.mapped_overlap_fraction'),
     'WorldCover built-up and OpenMap Local buildings',
     'WorldCover class 50 describes classified raster sample area. OpenMap Local describes generalized building polygon overlap with the parcel. Their denominators, dates, resolution and represented objects differ; neither replaces the other or establishes complete infrastructure.',
     'Which source definition and spatial support are relevant to the intended site use, and what additional evidence is needed?'),
    ('habitat_semantics', ('ecology.mapped_herbaceous_wetland_fraction', 'ecology.priority_habitat.any_mapped_overlap_fraction'),
     'Mapped land cover and Priority Habitats Inventory',
     'WorldCover herbaceous wetland is a land-cover class. PHI is an inventory of declared main priority habitats, including habitats other than wetland. Neither establishes current habitat condition, complete wetland extent or restoration need.',
     'What current habitat survey or condition evidence is material to this review?'),
    ('woodland_editions', ('ecology.ancient_woodland.mapped_overlap_fraction',),
     'Ancient Woodland inventory editions',
     'Legacy and revised Ancient Woodland inventories retain distinct source scopes and dates. Coexisting mapped overlaps are not added together and do not establish complete irreplaceable-habitat coverage.',
     'Which inventory edition and further habitat evidence are applicable to this boundary?'),
)


class ScreeningConfig(Record):
    include_cross_source_context: bool = True


class EvidenceRefs(Record):
    observation_ids: list[str] = Field(default_factory=list)
    gap_ids: list[str] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)
    relationship_ids: list[str] = Field(default_factory=list)
    source_feature_reference_ids: list[str] = Field(default_factory=list)
    source_reference_ids: list[str] = Field(default_factory=list)
    raw_reference_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)


class Fact(Record):
    id: str  # Original observation identity, never a new measurement.
    definition_id: str
    label: str
    dimensions: dict[str, DimensionValue]
    value: TypedValue
    unit: str
    availability: Literal['available', 'partial']
    known_zero: bool
    support: SpatialSupport
    method: str
    retrieved_at: datetime
    observation_period: TemporalReference | None
    legacy_observation_id: str | None
    limitations: str
    measurement: PriorityHabitatMeasurement | BuiltWorldMeasurement | None
    mapped_habitat_name: str | None
    references: EvidenceRefs


class ContextItem(Record):
    id: str
    label: str
    text: str
    references: EvidenceRefs


class ReviewGroup(Record):
    id: Literal['physical_hydrological', 'ecology_designations', 'built_transport']
    label: str
    facts: list[Fact]
    gaps: list[EvidenceGap]


class PublicSource(Record):
    id: str
    provider: str
    dataset: str
    source_version: str
    source_url: str | None
    reference_period: TemporalReference
    retrieved_at: datetime
    raw_reference_ids: list[str]
    licence_or_attribution: str | None
    licence_metadata_status: str


class PublicRawReference(Record):
    id: str
    legacy_raw_id: str
    retention_status: str
    checksum: str | None
    original_semantics: str


class ScreeningResult(Record):
    module_id: Literal['site_screening_context'] = MODULE_ID
    model_version: Literal['site_screening_context_v1'] = MODULE_VERSION
    input_binding_version: Literal['screening_context_binding_v1'] = BINDING_VERSION
    signature: str
    site_id: str
    boundary_version: int
    boundary_reference: str
    boundary_geometry_fingerprint: str
    evidence_snapshot_id: str
    evidence_content_hash: str
    evidence_schema_version: Literal['land_evidence_v1']
    evidence_registry_version: str
    evidence_as_of: datetime
    groups: list[ReviewGroup]
    unconnected_capabilities: list[CapabilityDisposition]
    mapped_zero_qualifications: list[ContextItem]
    cross_source_contexts: list[ContextItem]
    review_questions: list[ContextItem]
    definitions: list[ObservationDefinition]
    sources: list[PublicSource]
    raw_references: list[PublicRawReference]
    source_features: list[SourceFeatureReference]
    objects: list[BuiltWorldObject]
    relationships: list[ParcelObjectRelationship]
    limitations: list[str]

    @model_validator(mode='after')
    def references_resolve(self):
        facts = [f for g in self.groups for f in g.facts]
        gaps = [gap for g in self.groups for gap in g.gaps]
        catalogues = {
            'observation_ids': facts, 'gap_ids': gaps, 'object_ids': self.objects,
            'relationship_ids': self.relationships,
            'source_feature_reference_ids': self.source_features,
            'source_reference_ids': self.sources, 'raw_reference_ids': self.raw_references,
        }
        ids = {}
        for key, records in catalogues.items():
            ids[key] = {r.id for r in records}
            if len(ids[key]) != len(records):
                raise ValueError('Duplicate screening reference: ' + key)
        capabilities = self.unconnected_capabilities
        ids['capability_ids'] = {c.legacy_variable for c in capabilities}
        if [g.id for g in self.groups] != [g[0] for g in GROUPS]:
            raise ValueError('Unexpected screening groups or ordering')
        for item in facts + self.mapped_zero_qualifications + self.cross_source_contexts + self.review_questions:
            refs = item.references.model_dump()
            if not any(refs.values()):
                raise ValueError('Review items require direct evidence references')
            for key, values in refs.items():
                if not set(values) <= ids[key]:
                    raise ValueError('Unresolved screening reference: ' + key)
        for fact in facts:
            if fact.known_zero != (isinstance(fact.value, NumericValue) and fact.value.value == 0):
                raise ValueError('Contradictory known-zero fact')
            if fact.definition_id.startswith('transport.') and fact.definition_id.endswith('.distance_min'):
                if fact.support.coverage_status != 'full':
                    raise ValueError('Rail minimum distance requires complete search coverage')
        return self


def public_source_url(value: str) -> str | None:
    """Only public catalogue URLs; never forward credentials or signed queries."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            return None
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    except ValueError:
        return None


def screening_spec(config: ScreeningConfig | None = None) -> dict:
    config = config or ScreeningConfig()
    spec = {
        'module_id': MODULE_ID, 'model_version': MODULE_VERSION,
        'input_binding_version': BINDING_VERSION, 'config': config.model_dump(),
        'result_contract_hash': fingerprint(ScreeningResult.model_json_schema()),
        'rules': {'groups': list(GROUPS), 'cross_source': list(CROSS_RULES),
                  'limitations': LIMITATIONS, 'fact_policy': 'all_source_bounded_observations_v1',
                  'gap_policy': 'preserve_and_ask_materiality_v1',
                  'zero_policy': 'source_support_qualified_zero_v1'},
    }
    # Normalize tuples as JSON before signing and storing.
    import json
    spec = json.loads(json.dumps(spec))
    return {**spec, 'signature': fingerprint(spec)}


def _group(definition: str) -> str:
    if definition.startswith(('built.', 'transport.', 'human.')):
        return 'built_transport'
    if definition.startswith(('ecology.', 'designations.', 'regulatory.', 'land_use.')):
        return 'ecology_designations'
    return 'physical_hydrological'


def _merge_refs(facts: list[Fact]) -> EvidenceRefs:
    return EvidenceRefs(**{
        key: sorted({value for f in facts for value in getattr(f.references, key)})
        for key in EvidenceRefs.model_fields
    })


def build_screening_context(projection: LandEvidenceProjection, *, snapshot_id: str,
                            content_hash: str, config: ScreeningConfig | None = None) -> ScreeningResult:
    """Pure rule execution; caller must resolve a validated committed snapshot."""
    projection = validate_land_evidence(projection)
    config = config or ScreeningConfig()
    definitions = {d.id: d for d in projection.definitions}
    groups = {key: ReviewGroup(id=key, label=label, facts=[], gaps=[]) for key, label in GROUPS}
    zeroes, questions, contexts = [], [], []
    for observation in sorted(projection.observations, key=lambda o: (o.definition_id, o.id)):
        # The v1 screening workflow remains unchanged. Object-level height is
        # exposed by the later map-scene contract, not reinterpreted here.
        if isinstance(observation, BuildingHeightObservation):
            continue
        object_ids = sorted(getattr(observation, 'supporting_object_ids', []))
        relationships = [r for r in projection.relationships if r.object_id in object_ids]
        refs = EvidenceRefs(
            observation_ids=sorted({observation.id, *observation.parent_observation_ids}),
            source_reference_ids=sorted(observation.source_reference_ids),
            raw_reference_ids=sorted(observation.raw_reference_ids), object_ids=object_ids,
            relationship_ids=sorted(r.id for r in relationships),
            source_feature_reference_ids=sorted(getattr(observation, 'source_feature_reference_ids', [])),
        )
        fact = Fact(
            id=observation.id, definition_id=observation.definition_id,
            label=definitions[observation.definition_id].description,
            dimensions=observation.dimensions, value=observation.value, unit=observation.unit,
            availability=observation.availability, known_zero=observation.known_zero,
            support=observation.support, method=observation.provenance.derivation_method,
            retrieved_at=observation.provenance.retrieved_at,
            observation_period=getattr(observation.provenance, 'observation_period', None),
            legacy_observation_id=getattr(observation.provenance, 'legacy_observation_id', None),
            limitations=observation.limitations, references=refs,
            measurement=getattr(observation, 'measurement', None),
            mapped_habitat_name=getattr(observation, 'mapped_habitat_name', None),
        )
        groups[_group(fact.definition_id)].facts.append(fact)
        if fact.known_zero:
            distance = fact.definition_id.endswith('.distance_min')
            zeroes.append(ContextItem(
                id='zero:' + fact.id, label=fact.label, references=refs,
                text=('Zero mapped distance indicates intersection or contact with the mapped object; it is not absence.'
                      if distance else 'Zero is recorded only for this source, definition and spatial support. It does not prove real-world absence.'),
            ))
        if fact.availability == 'partial' or fact.support.coverage_status != 'full':
            questions.append(ContextItem(
                id='support:' + fact.id, label=fact.label, references=refs,
                text='Is this partial or historically unrecorded spatial support adequate for the current review, or is further evidence material?',
            ))
    for gap in sorted(projection.gaps, key=lambda g: (g.definition_id or g.legacy_variable or '', g.id)):
        if isinstance(gap, BuildingHeightEvidenceGap):
            continue
        label = gap.definition_id or gap.legacy_variable or gap.reason_code
        groups[_group(label)].gaps.append(gap)
        questions.append(ContextItem(
            id='gap-question:' + gap.id, label=label,
            text='Establish whether this evidence gap is material to the current review and what evidence would resolve it.',
            references=EvidenceRefs(gap_ids=[gap.id], source_reference_ids=sorted(gap.source_reference_ids),
                                    raw_reference_ids=sorted(gap.raw_reference_ids)),
        ))
    unconnected = sorted((c for c in projection.capabilities if c.disposition == 'registered_unconnected'),
                         key=lambda c: c.legacy_variable)
    for capability in unconnected:
        questions.append(ContextItem(
            id='capability-question:' + capability.legacy_variable, label=capability.legacy_variable,
            text='Establish whether this unconnected evidence capability is material to the current review.',
            references=EvidenceRefs(capability_ids=[capability.legacy_variable]),
        ))
    facts = [f for g in groups.values() for f in g.facts]
    if config.include_cross_source_context:
        for rule_id, definition_ids, label, text, question in CROSS_RULES:
            matches = [f for f in facts if f.definition_id in definition_ids]
            if not all(any(f.definition_id == d for f in matches) for d in definition_ids):
                continue
            if rule_id == 'woodland_editions' and len({str(f.dimensions.get('inventory')) for f in matches}) < 2:
                continue
            refs = _merge_refs(matches)
            contexts.append(ContextItem(id=rule_id, label=label, text=text, references=refs))
            questions.append(ContextItem(id='question:' + rule_id, label=label, text=question, references=refs))
    identity = projection.identity
    limitations = list(LIMITATIONS)
    if not projection.objects and identity.registry_version not in (
        'land_evidence_registry_v3', BUILDING_HEIGHT_REGISTRY_VERSION,
    ):
        limitations.append('This historical evidence registry predates built-world representation. Missing objects here do not mean mapped zero; prepare a new assessment to acquire newer evidence.')
    return ScreeningResult(
        signature=screening_spec(config)['signature'], site_id=identity.legacy_location_id,
        boundary_version=identity.boundary_version, boundary_reference=identity.boundary_reference,
        boundary_geometry_fingerprint=identity.boundary_geometry_fingerprint,
        evidence_snapshot_id=snapshot_id, evidence_content_hash=content_hash,
        evidence_schema_version=identity.schema_version, evidence_registry_version=identity.registry_version,
        evidence_as_of=identity.evidence_as_of, groups=list(groups.values()),
        unconnected_capabilities=unconnected,
        mapped_zero_qualifications=zeroes, cross_source_contexts=contexts,
        review_questions=sorted(questions, key=lambda q: q.id),
        definitions=sorted(projection.definitions, key=lambda d: d.id),
        sources=[PublicSource(**{**s.model_dump(), 'source_url': public_source_url(s.source_url)})
                 for s in sorted(projection.source_references, key=lambda s: s.id)],
        raw_references=[PublicRawReference(**r.model_dump(exclude={'storage_reference', 'assets'}))
                        for r in sorted(projection.raw_references, key=lambda r: r.id)],
        source_features=sorted(projection.source_feature_references, key=lambda f: f.id),
        objects=sorted(projection.objects, key=lambda o: o.id),
        relationships=sorted(projection.relationships, key=lambda r: r.id), limitations=limitations,
    )
