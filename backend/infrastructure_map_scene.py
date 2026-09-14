"""Native, read-only infrastructure scene projected from one Evidence Snapshot."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pyproj import Transformer
from shapely.geometry import mapping, shape
from shapely.ops import transform

from backend.land_evidence import (
    BUILDING_HEIGHT_REGISTRY_VERSION,
    BUILT_WORLD_REGISTRY_VERSION,
    BuildingHeightEvidenceGap,
    BuildingHeightObservation,
    BuiltWorldObservation,
    LandEvidenceProjection,
    MappedBuildingObject,
    NumericValue,
)
from backend.land_evidence_store import (
    LandEvidenceSnapshotRecord, snapshot_content_hash,
)
from backend.openmap_local import LIMITATIONS as OPENMAP_LOCAL_LIMITATIONS


CONTRACT_VERSION = 'infrastructure_map_scene_v1'
PRESENTATION_CRS = 'EPSG:4326'
AUTHORITATIVE_CRS = 'EPSG:27700'
TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True).transform

LayerId = Literal['buildings', 'functional_sites', 'railway_tracks', 'railway_stations']
ObjectType = Literal['building', 'functional_site', 'railway_track', 'railway_station']
LayerState = Literal['available', 'mapped_zero', 'unavailable', 'partial', 'unsupported']
HeightState = Literal['available', 'partial', 'gap', 'unsupported']
CapabilityState = Literal['available', 'partial', 'unavailable', 'unsupported']


class SceneRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class SceneSnapshot(SceneRecord):
    id: str
    schema_version: str
    registry_version: str
    content_hash: str
    created: datetime


class SceneSite(SceneRecord):
    id: str
    name: str | None = None
    geography: str


class SceneBoundary(SceneRecord):
    version: int
    reference: str
    geometry_fingerprint: str
    authoritative_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS


class SceneTemporalReference(SceneRecord):
    status: Literal['recorded', 'not_recorded_legacy']
    value: datetime | None = None
    qualification: str | None = None


class SceneSource(SceneRecord):
    id: str
    provider: str
    dataset: str
    release: str
    source_url: str
    retrieved_at: datetime
    reference_period: SceneTemporalReference
    attribution: str | None = None


class SceneRelationshipMeasurements(SceneRecord):
    overlap_area_m2: float | None = Field(default=None, ge=0)
    parcel_overlap_fraction: float | None = Field(default=None, ge=0, le=1)
    object_overlap_fraction: float | None = Field(default=None, ge=0, le=1)
    length_within_m: float | None = Field(default=None, ge=0)
    minimum_distance_m: float | None = Field(default=None, ge=0)


class SceneRelationship(SceneRecord):
    id: str
    predicate: Literal[
        'overlaps', 'touches', 'contained_within', 'crosses', 'intersects',
        'minimum_distance',
    ]
    geometry_semantics: str
    support_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS
    measurements: SceneRelationshipMeasurements


class SceneHeight(SceneRecord):
    state: HeightState
    observation_id: str | None = None
    gap_id: str | None = None
    gap_state: str | None = None
    reason_code: str | None = None
    p50_height_m: float | None = Field(default=None, ge=0)
    p90_height_m: float | None = Field(default=None, ge=0)
    extrusion_height_m: float | None = Field(default=None, ge=0)
    sample_count: int | None = Field(default=None, ge=0)
    coverage_fraction: float | None = Field(default=None, ge=0, le=1)
    evidence_time: datetime | None = None
    source_reference_ids: list[str] = Field(default_factory=list)
    qualification: str


class SceneFeatureProperties(SceneRecord):
    layer_id: LayerId
    object_id: str
    object_type: ObjectType
    object_source_id: str
    source_release: str
    feature_code: int
    classification: str | None = None
    name: str | None = None
    site_theme: str | None = None
    geometry_fingerprint: str
    authoritative_geometry_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS
    relationships: list[SceneRelationship]
    height: SceneHeight | None = None


class SceneFeature(SceneRecord):
    type: Literal['Feature'] = 'Feature'
    id: str
    geometry: dict[str, Any]
    properties: SceneFeatureProperties


class SceneLayer(SceneRecord):
    id: LayerId
    object_type: ObjectType
    state: LayerState
    feature_count: int = Field(ge=0)
    source_reference_ids: list[str]
    height_available_count: int = Field(default=0, ge=0)
    height_gap_count: int = Field(default=0, ge=0)
    height_unsupported_count: int = Field(default=0, ge=0)
    qualification: str


class SceneCapability(SceneRecord):
    id: Literal[
        'native_geojson_selection', 'parcel_relationships',
        'evidence_backed_building_extrusion',
    ]
    state: CapabilityState
    qualification: str


class InfrastructureMapScene(SceneRecord):
    type: Literal['FeatureCollection'] = 'FeatureCollection'
    contract_version: Literal['infrastructure_map_scene_v1'] = CONTRACT_VERSION
    snapshot: SceneSnapshot
    site: SceneSite
    boundary: SceneBoundary
    evidence_as_of: datetime
    presentation_crs: Literal['EPSG:4326'] = PRESENTATION_CRS
    authoritative_geometry_crs: Literal['EPSG:27700'] = AUTHORITATIVE_CRS
    sources: list[SceneSource]
    layers: list[SceneLayer]
    capabilities: list[SceneCapability]
    features: list[SceneFeature]
    limitations: list[str]


LAYER_OBJECTS: tuple[tuple[LayerId, ObjectType], ...] = (
    ('buildings', 'building'),
    ('functional_sites', 'functional_site'),
    ('railway_tracks', 'railway_track'),
    ('railway_stations', 'railway_station'),
)

LAYER_DEFINITIONS = {
    'buildings': ('built.building.mapped_overlap_fraction',),
    'functional_sites': ('built.functional_site.mapped_overlap_fraction',),
    'railway_tracks': (
        'transport.railway_track.mapped_length_within',
        'transport.railway_track.distance_min',
    ),
    'railway_stations': ('transport.railway_station.distance_min',),
}


def _geometry_wgs84(source_geometry: dict[str, Any]) -> dict[str, Any]:
    geometry = transform(TO_WGS84, shape(source_geometry))
    if geometry.is_empty:
        raise ValueError('Persisted infrastructure geometry cannot be presented')
    return json.loads(json.dumps(mapping(geometry), allow_nan=False))


def _source(item) -> SceneSource:
    return SceneSource(
        id=item.id, provider=item.provider, dataset=item.dataset,
        release=item.source_version, source_url=item.source_url,
        retrieved_at=item.retrieved_at,
        reference_period=SceneTemporalReference.model_validate(
            item.reference_period.model_dump(mode='json')
        ),
        attribution=item.licence_or_attribution,
    )


def _layer_state(
    projection: LandEvidenceProjection, object_type: ObjectType, feature_count: int,
) -> LayerState:
    if projection.identity.registry_version not in (
        BUILT_WORLD_REGISTRY_VERSION, BUILDING_HEIGHT_REGISTRY_VERSION,
    ):
        return 'unsupported'
    definitions = LAYER_DEFINITIONS[{value: key for key, value in LAYER_OBJECTS}[object_type]]
    observations = [
        item for item in projection.observations
        if isinstance(item, BuiltWorldObservation) and item.definition_id in definitions
    ]
    gaps = [item for item in projection.gaps if item.definition_id in definitions]
    if any(item.state == 'partial_coverage' for item in gaps):
        return 'partial'
    if any(item.state == 'unsupported_processing_case' for item in gaps):
        return 'unsupported'
    if any(item.state in ('source_not_connected', 'unavailable', 'incomplete_inventory')
           for item in gaps):
        return 'unavailable'
    if feature_count:
        return 'available'
    if observations or any(item.state == 'absent_observation' for item in gaps):
        return 'mapped_zero'
    return 'unavailable'


def _layer_qualification(state: LayerState) -> str:
    return {
        'available': 'Persisted mapped objects are available for this source-bounded layer.',
        'mapped_zero': ('No qualifying mapped object occurs within complete declared source support. '
                        'This does not prove real-world absence.'),
        'unavailable': 'Source evidence is unavailable; missing evidence is not reported as zero.',
        'partial': 'Source support is partial; no complete mapped-zero claim is made.',
        'unsupported': 'This historical registry does not support this scene layer.',
    }[state]


def _unsupported_height() -> SceneHeight:
    return SceneHeight(
        state='unsupported',
        qualification='This historical snapshot predates object-level building-height evidence.',
    )


def _height(
    obj, observations: dict[str, BuildingHeightObservation],
    gaps: dict[str, BuildingHeightEvidenceGap], registry_version: str,
) -> SceneHeight | None:
    if not isinstance(obj, MappedBuildingObject):
        return None
    if registry_version != BUILDING_HEIGHT_REGISTRY_VERSION:
        return _unsupported_height()
    observation = observations.get(obj.id)
    if observation:
        measurement = observation.measurement
        return SceneHeight(
            state=observation.availability, observation_id=observation.id,
            p50_height_m=measurement.p50_height_m,
            p90_height_m=measurement.p90_height_m,
            extrusion_height_m=measurement.extrusion_height_m,
            sample_count=measurement.sample_count,
            coverage_fraction=measurement.coverage_fraction,
            evidence_time=observation.provenance.retrieved_at,
            source_reference_ids=sorted(observation.source_reference_ids),
            qualification=observation.limitations,
        )
    gap = gaps.get(obj.id)
    if not gap:
        raise ValueError('Registry v4 building has no height observation or explicit gap')
    return SceneHeight(
        state='gap', gap_id=gap.id, gap_state=gap.state,
        reason_code=gap.reason_code,
        source_reference_ids=sorted(gap.source_reference_ids),
        qualification=gap.reason,
    )


def build_infrastructure_map_scene(
    snapshot: LandEvidenceSnapshotRecord, projection: LandEvidenceProjection,
) -> InfrastructureMapScene:
    """Present one already revalidated immutable snapshot without IO or writes."""
    identity = projection.identity
    if (
        snapshot.site_id != identity.legacy_location_id
        or snapshot.boundary_version != identity.boundary_version
        or snapshot.boundary_geometry_fingerprint != identity.boundary_geometry_fingerprint
        or snapshot.schema_version != identity.schema_version
        or snapshot.registry_version != identity.registry_version
        or snapshot.content_hash != snapshot_content_hash(projection)
    ):
        raise ValueError('Snapshot record and evidence manifest do not match')

    source_by_id = {item.id: item for item in projection.source_references}
    relationships_by_object: dict[str, list[Any]] = {}
    for item in projection.relationships:
        relationships_by_object.setdefault(item.object_id, []).append(item)
    height_observations = {
        item.object_id: item for item in projection.observations
        if isinstance(item, BuildingHeightObservation)
    }
    height_gaps = {
        item.object_id: item for item in projection.gaps
        if isinstance(item, BuildingHeightEvidenceGap)
    }

    features: list[SceneFeature] = []
    layers: list[SceneLayer] = []
    used_source_ids: set[str] = set()
    for layer_id, object_type in LAYER_OBJECTS:
        objects = sorted(
            (item for item in projection.objects if item.object_type == object_type),
            key=lambda item: item.id,
        )
        heights = [
            _height(item, height_observations, height_gaps, identity.registry_version)
            for item in objects
        ]
        object_source_ids = sorted({item.source_reference_id for item in objects})
        if any(source_id not in source_by_id for source_id in object_source_ids):
            raise ValueError('Infrastructure scene object has an unresolved source')
        used_source_ids.update(object_source_ids)
        for height in heights:
            if height:
                used_source_ids.update(height.source_reference_ids)
        layers.append(SceneLayer(
            id=layer_id, object_type=object_type,
            state=_layer_state(projection, object_type, len(objects)),
            feature_count=len(objects), source_reference_ids=object_source_ids,
            height_available_count=sum(
                height is not None and height.state in ('available', 'partial')
                for height in heights
            ),
            height_gap_count=sum(
                height is not None and height.state == 'gap' for height in heights
            ),
            height_unsupported_count=sum(
                height is not None and height.state == 'unsupported' for height in heights
            ),
            qualification=_layer_qualification(
                _layer_state(projection, object_type, len(objects))
            ),
        ))
        for obj, height in zip(objects, heights):
            relationships = sorted(
                relationships_by_object.get(obj.id, []), key=lambda item: item.id,
            )
            features.append(SceneFeature(
                id=obj.id, geometry=_geometry_wgs84(obj.source_geometry),
                properties=SceneFeatureProperties(
                    layer_id=layer_id, object_id=obj.id,
                    object_type=obj.object_type,
                    object_source_id=obj.source_reference_id,
                    source_release=obj.source_release,
                    feature_code=obj.feature_code,
                    classification=getattr(obj, 'classification', None),
                    name=getattr(obj, 'distinctive_name', None),
                    site_theme=getattr(obj, 'site_theme', None),
                    geometry_fingerprint=obj.source_geometry_fingerprint,
                    relationships=[SceneRelationship(
                        id=item.id, predicate=item.predicate,
                        geometry_semantics=item.geometry_semantics,
                        measurements=SceneRelationshipMeasurements.model_validate(
                            item.measurements.model_dump(mode='json')
                        ),
                    ) for item in relationships],
                    height=height,
                ),
            ))

    building_layer = next(item for item in layers if item.id == 'buildings')
    if identity.registry_version != BUILDING_HEIGHT_REGISTRY_VERSION:
        height_capability: CapabilityState = 'unsupported'
        height_qualification = 'The selected historical snapshot predates height evidence.'
    elif building_layer.height_available_count == 0:
        height_capability = 'unavailable'
        height_qualification = 'No building has valid height evidence; all buildings remain flat.'
    elif building_layer.height_gap_count:
        height_capability = 'partial'
        height_qualification = 'Only buildings with valid height observations may be extruded.'
    else:
        height_capability = 'available'
        height_qualification = 'Every mapped building has evidence-backed extrusion height.'

    relationship_state: CapabilityState = (
        'available' if projection.relationships else
        'unsupported' if identity.registry_version not in (
            BUILT_WORLD_REGISTRY_VERSION, BUILDING_HEIGHT_REGISTRY_VERSION,
        ) else 'unavailable'
    )
    return InfrastructureMapScene(
        snapshot=SceneSnapshot(
            id=snapshot.id, schema_version=snapshot.schema_version,
            registry_version=snapshot.registry_version,
            content_hash=snapshot.content_hash, created=snapshot.created,
        ),
        site=SceneSite(
            id=identity.legacy_location_id, name=identity.site_name,
            geography=identity.geography,
        ),
        boundary=SceneBoundary(
            version=identity.boundary_version,
            reference=identity.boundary_reference,
            geometry_fingerprint=identity.boundary_geometry_fingerprint,
        ),
        evidence_as_of=identity.evidence_as_of,
        sources=[_source(source_by_id[source_id]) for source_id in sorted(used_source_ids)],
        layers=layers,
        capabilities=[
            SceneCapability(
                id='native_geojson_selection',
                state='available' if features else 'unavailable',
                qualification='Scene objects support native rendered-feature selection.',
            ),
            SceneCapability(
                id='parcel_relationships', state=relationship_state,
                qualification=(
                    'Persisted typed parcel relationships are available.'
                    if projection.relationships else
                    'No persisted parcel relationships are available for this snapshot.'
                ),
            ),
            SceneCapability(
                id='evidence_backed_building_extrusion', state=height_capability,
                qualification=height_qualification,
            ),
        ],
        features=features,
        limitations=[
            'Presentation geometry is transformed to WGS84 only for visualization; persisted '
            'EPSG:27700 geometry and measurements remain authoritative.',
            OPENMAP_LOCAL_LIMITATIONS,
            'Building extrusions are historical DSM minus DTM estimates and are never current, '
            'legal or engineering surveyed heights.',
        ],
    )
