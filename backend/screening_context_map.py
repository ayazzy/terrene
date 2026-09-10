"""Read-only WGS84 presentation of persisted Screening Context built-world evidence."""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

from backend.land_evidence import (
    BUILT_WORLD_REGISTRY_VERSION, BuiltWorldMeasurement, NumericValue,
)
from backend.module_runs import ModuleRunRecord
from backend.openmap_local import LIMITATIONS as OPENMAP_LOCAL_LIMITATIONS
from backend.screening_context import Fact, PublicSource, ScreeningResult


CONTRACT_VERSION = 'screening_context_map_features_v1'
PRESENTATION_CRS = 'EPSG:4326'
AUTHORITATIVE_CRS = 'EPSG:27700'
TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True).transform

LayerState = Literal['available', 'mapped_zero', 'unavailable', 'partial', 'unsupported']


class MapRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MapSource(MapRecord):
    id: str
    provider: str
    dataset: str
    release: str


class MapRelationshipMeasurements(MapRecord):
    overlap_area_m2: float | None = Field(default=None, ge=0)
    parcel_overlap_fraction: float | None = Field(default=None, ge=0, le=1)
    object_overlap_fraction: float | None = Field(default=None, ge=0, le=1)
    length_within_m: float | None = Field(default=None, ge=0)
    minimum_distance_m: float | None = Field(default=None, ge=0)


class MapRelationship(MapRecord):
    id: str
    predicate: Literal[
        'overlaps', 'touches', 'contained_within', 'crosses', 'intersects',
        'minimum_distance',
    ]
    geometry_semantics: str
    support_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS
    measurements: MapRelationshipMeasurements


class MapFeatureProperties(MapRecord):
    layer_id: Literal['buildings', 'functional_sites', 'railway_tracks', 'railway_stations']
    object_id: str
    object_type: Literal['building', 'functional_site', 'railway_track', 'railway_station']
    source: MapSource
    source_release: str
    feature_code: int
    classification: str | None = None
    name: str | None = None
    site_theme: str | None = None
    geometry_fingerprint: str
    authoritative_geometry_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS
    relationships: list[MapRelationship]


class GeoJSONFeature(MapRecord):
    type: Literal['Feature'] = 'Feature'
    id: str
    geometry: dict[str, Any]
    properties: MapFeatureProperties


class LayerMeasurement(MapRecord):
    observation_id: str
    definition_id: str
    value: float
    unit: str
    known_zero: bool
    availability: Literal['available', 'partial']
    coverage_status: Literal['full', 'partial', 'unrecorded_legacy']
    coverage_fraction: float | None = Field(default=None, ge=0, le=1)
    numerator: float = Field(ge=0)
    denominator: float | None = Field(default=None, gt=0)
    numerator_unit: Literal['m2', 'm']
    denominator_unit: Literal['m2'] | None = None
    aggregation: Literal[
        'clipped_source_polygon_spatial_union',
        'clipped_source_line_spatial_union',
        'minimum_euclidean_distance_within_complete_5000m_search',
    ]
    supporting_object_ids: list[str]


class MapLayer(MapRecord):
    id: Literal['buildings', 'functional_sites', 'railway_tracks', 'railway_stations']
    object_type: Literal['building', 'functional_site', 'railway_track', 'railway_station']
    state: LayerState
    feature_count: int = Field(ge=0)
    coverage_status: Literal['full', 'partial', 'unavailable', 'unsupported']
    coverage_fraction: float | None = Field(default=None, ge=0, le=1)
    coverage_basis: list[str]
    qualification: str
    sources: list[MapSource]
    measurements: list[LayerMeasurement]
    observation_ids: list[str]
    gap_ids: list[str]
    gap_reason_codes: list[str]


class ScreeningMapFeatureCollection(MapRecord):
    type: Literal['FeatureCollection'] = 'FeatureCollection'
    contract_version: Literal['screening_context_map_features_v1'] = CONTRACT_VERSION
    run_id: str
    evidence_snapshot_id: str
    evidence_content_hash: str
    site_id: str
    boundary_version: int
    boundary_reference: str
    boundary_geometry_fingerprint: str
    evidence_as_of: str
    presentation_crs: Literal['EPSG:4326'] = PRESENTATION_CRS
    authoritative_geometry_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS
    layers: list[MapLayer]
    features: list[GeoJSONFeature]
    limitations: list[str]


LAYER_DEFINITIONS = (
    ('buildings', 'building', ('built.building.mapped_overlap_fraction',), (
        'whole_parcel_within_acquired_openmap_local_extract',
    )),
    ('functional_sites', 'functional_site', ('built.functional_site.mapped_overlap_fraction',), (
        'whole_parcel_within_acquired_openmap_local_extract',
    )),
    ('railway_tracks', 'railway_track', (
        'transport.railway_track.mapped_length_within',
        'transport.railway_track.distance_min',
    ), (
        'whole_parcel_within_acquired_openmap_local_extract',
        'complete_mapped_railway_search_within_5000m',
    )),
    ('railway_stations', 'railway_station', (
        'transport.railway_station.distance_min',
    ), (
        'complete_mapped_railway_search_within_5000m',
    )),
)


def _source(source: PublicSource) -> MapSource:
    return MapSource(
        id=source.id, provider=source.provider, dataset=source.dataset,
        release=source.source_version,
    )


def _geometry_wgs84(source_geometry: dict[str, Any]) -> dict[str, Any]:
    projected = shape(source_geometry)
    presented = transform(TO_WGS84, projected)
    if presented.is_empty:
        raise ValueError('Persisted built-world geometry cannot be presented')
    # Force arrays rather than Shapely tuples and reject non-finite JSON values.
    return json.loads(json.dumps(mapping(presented), allow_nan=False))


def _measurement(fact: Fact) -> LayerMeasurement:
    if not isinstance(fact.value, NumericValue) or not isinstance(fact.measurement, BuiltWorldMeasurement):
        raise ValueError('Persisted built-world measurement contract is invalid')
    measurement = fact.measurement
    return LayerMeasurement(
        observation_id=fact.id, definition_id=fact.definition_id,
        value=fact.value.value, unit=fact.unit, known_zero=fact.known_zero,
        availability=fact.availability,
        coverage_status=fact.support.coverage_status,
        coverage_fraction=fact.support.coverage_fraction,
        numerator=measurement.numerator, denominator=measurement.denominator,
        numerator_unit=measurement.numerator_unit,
        denominator_unit=measurement.denominator_unit,
        aggregation=measurement.aggregation,
        supporting_object_ids=sorted(measurement.supporting_object_ids),
    )


def _state(registry_version: str, object_count: int, facts: list[Fact], gaps: list) -> LayerState:
    if registry_version != BUILT_WORLD_REGISTRY_VERSION:
        return 'unsupported'
    gap_states = {gap.state for gap in gaps}
    if 'partial_coverage' in gap_states or any(
            fact.availability == 'partial' or fact.support.coverage_status == 'partial'
            for fact in facts):
        return 'partial'
    if 'unsupported_processing_case' in gap_states:
        return 'unsupported'
    if gap_states & {'source_not_connected', 'unavailable', 'incomplete_inventory'}:
        return 'unavailable'
    if object_count:
        return 'available'
    if facts or any(gap.state == 'absent_observation' for gap in gaps):
        return 'mapped_zero'
    return 'unavailable'


def _qualification(state: LayerState) -> str:
    return {
        'available': 'One or more persisted mapped objects are available for this source-bounded layer.',
        'mapped_zero': ('No qualifying object is represented within the declared complete source support. '
                        'This mapped zero does not prove real-world absence.'),
        'unavailable': ('This source layer is unavailable in the selected snapshot. Missing evidence is not '
                        'reported as zero.'),
        'partial': ('Only partial source support is available. No complete mapped-zero claim or fabricated '
                    'railway minimum distance is made.'),
        'unsupported': ('The selected historical snapshot does not support persisted built-world objects. '
                        'Current objects are not substituted.'),
    }[state]


def build_screening_map_features(run: ModuleRunRecord) -> ScreeningMapFeatureCollection:
    """Project one already integrity-checked Screening Context run without IO or writes."""
    result = ScreeningResult.model_validate(run.result)
    if (
        run.module_id != 'site_screening_context'
        or run.evidence_snapshot_id != result.evidence_snapshot_id
        or run.evidence_content_hash != result.evidence_content_hash
        or run.site_id != result.site_id
        or run.boundary_version != result.boundary_version
    ):
        raise ValueError('Screening run and persisted evidence envelope do not match')

    all_facts = [fact for group in result.groups for fact in group.facts]
    all_gaps = [gap for group in result.groups for gap in group.gaps]
    sources_by_id = {source.id: source for source in result.sources}
    relationships_by_object: dict[str, list] = {}
    for relationship in result.relationships:
        relationships_by_object.setdefault(relationship.object_id, []).append(relationship)

    layers: list[MapLayer] = []
    features: list[GeoJSONFeature] = []
    for layer_id, object_type, definition_ids, coverage_basis in LAYER_DEFINITIONS:
        objects = sorted(
            (obj for obj in result.objects if obj.object_type == object_type),
            key=lambda obj: obj.id,
        )
        facts = sorted(
            (fact for fact in all_facts if fact.definition_id in definition_ids),
            key=lambda fact: (fact.definition_id, fact.id),
        )
        gaps = sorted(
            (gap for gap in all_gaps if gap.definition_id in definition_ids),
            key=lambda gap: (gap.definition_id or '', gap.id),
        )
        state = _state(result.evidence_registry_version, len(objects), facts, gaps)
        source_ids = sorted({
            *(obj.source_reference_id for obj in objects),
            *(source_id for fact in facts for source_id in fact.references.source_reference_ids),
            *(source_id for gap in gaps for source_id in gap.source_reference_ids),
        })
        if any(source_id not in sources_by_id for source_id in source_ids):
            raise ValueError('Persisted map layer has an unresolved source')
        layers.append(MapLayer(
            id=layer_id, object_type=object_type, state=state,
            feature_count=len(objects),
            coverage_status=(state if state in ('partial', 'unavailable', 'unsupported') else 'full'),
            coverage_fraction=(1.0 if state in ('available', 'mapped_zero') else None),
            coverage_basis=list(coverage_basis), qualification=_qualification(state),
            sources=[_source(sources_by_id[source_id]) for source_id in source_ids],
            measurements=[_measurement(fact) for fact in facts],
            observation_ids=[fact.id for fact in facts],
            gap_ids=[gap.id for gap in gaps],
            gap_reason_codes=sorted({gap.reason_code for gap in gaps}),
        ))
        for obj in objects:
            source = sources_by_id.get(obj.source_reference_id)
            if source is None:
                raise ValueError('Persisted map object has an unresolved source')
            relationships = sorted(relationships_by_object.get(obj.id, []), key=lambda item: item.id)
            features.append(GeoJSONFeature(
                id=obj.id, geometry=_geometry_wgs84(obj.source_geometry),
                properties=MapFeatureProperties(
                    layer_id=layer_id, object_id=obj.id, object_type=obj.object_type,
                    source=_source(source), source_release=obj.source_release,
                    feature_code=obj.feature_code,
                    classification=getattr(obj, 'classification', None),
                    name=getattr(obj, 'distinctive_name', None),
                    site_theme=getattr(obj, 'site_theme', None),
                    geometry_fingerprint=obj.source_geometry_fingerprint,
                    relationships=[MapRelationship(
                        id=relationship.id, predicate=relationship.predicate,
                        geometry_semantics=relationship.geometry_semantics,
                        measurements=MapRelationshipMeasurements.model_validate(
                            relationship.measurements.model_dump()
                        ),
                    ) for relationship in relationships],
                ),
            ))

    return ScreeningMapFeatureCollection(
        run_id=run.id, evidence_snapshot_id=result.evidence_snapshot_id,
        evidence_content_hash=result.evidence_content_hash, site_id=result.site_id,
        boundary_version=result.boundary_version,
        boundary_reference=result.boundary_reference,
        boundary_geometry_fingerprint=result.boundary_geometry_fingerprint,
        evidence_as_of=result.evidence_as_of.isoformat(), layers=layers, features=features,
        limitations=[
            'Presentation geometry is transformed to WGS84 only for visualization; persisted EPSG:27700 '
            'geometry, fingerprints and measurements remain authoritative and unchanged.',
            OPENMAP_LOCAL_LIMITATIONS,
        ],
    )
