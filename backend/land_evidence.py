"""Read-only ``land_evidence_v1`` projection of saved CRC evidence.

This module is deliberately a compatibility boundary.  It imports the legacy
Earth schema so that saved records can be validated, but it imports neither
acquisition nor wetland scoring code and performs no IO.  Projection IDs and
diagnostics are derived solely from the supplied saved payload.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime
import json
import math
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator
from shapely.geometry import shape as shapely_shape

from backend.earth import EarthState, Observation as LegacyObservation, VARIABLES, fingerprint
from backend.priority_habitats import (
    CLASSIFICATION as PHI_CLASSIFICATION,
    LIMITATIONS as PHI_LIMITATIONS,
    MAIN_CLASSES as PHI_MAIN_CLASSES,
    PRIORITY_HABITATS as PHI_PRIORITY_HABITATS,
    SCHEMA_VERSION as PHI_SOURCE_SCHEMA_VERSION,
)
from backend.openmap_local import (
    LIMITATIONS as OML_LIMITATIONS,
    PROCESSING_VERSION as OML_PROCESSING_VERSION,
    PRODUCT_URL as OML_PRODUCT_URL,
    SCHEMA_VERSION as OML_SOURCE_SCHEMA_VERSION,
    SEARCH_RADIUS_M as OML_SEARCH_RADIUS_M,
    SOURCE_CRS as OML_SOURCE_CRS,
    validate_properties as validate_oml_properties,
)


SCHEMA_VERSION = 'land_evidence_v1'
REGISTRY_VERSION = 'land_evidence_registry_v1'
PHI_REGISTRY_VERSION = 'land_evidence_registry_v2'
BUILT_WORLD_REGISTRY_VERSION = 'land_evidence_registry_v3'

WORLD_COVER_CLASSES = {
    10: 'woodland', 20: 'shrubland', 30: 'grassland', 40: 'arable',
    50: 'developed', 60: 'bare_ground', 70: 'snow_ice', 80: 'water',
    90: 'wetland', 95: 'mangroves', 100: 'moss_lichen',
}
WORLD_COVER_CLASSIFICATION = 'esa_worldcover_2021_v200'
WORLD_COVER_METHOD_PREFIX = (
    'crc_os_worldcover_v1; WorldCover class mapping ' + str(WORLD_COVER_CLASSES)
    + '; native cell centres within parcel, geodesic row-area weights, valid classes only. '
      'No management/condition inference. Full class fractions: '
)

LEGACY_MODULE_OUTPUTS = {
    'soil.retention_index',
    'hydrology.water_context_index',
    'ecology.restoration_need_index',
    'ecology.habitat_proximity_index',
    'human.unblocked_area_index',
}

EXPLICIT_GAPS = {
    'soil.drainage_class': (
        'soil.drainage.class',
        'No connected source establishes parcel soil drainage.',
    ),
    'ecology.wetland_fraction': (
        'ecology.wetland.actual_extent_fraction',
        'Mapped herbaceous-wetland cover does not establish actual wetland extent.',
    ),
    'ecology.habitat_condition': (
        'ecology.habitat.condition',
        'No current ecological condition survey is connected.',
    ),
    'human.infrastructure_fraction': (
        'built.infrastructure.complete_footprint_fraction',
        'No complete road, rail, utility and infrastructure footprint source is connected.',
    ),
}

REGISTERED_UNCONNECTED = {
    'terrain.aspect_deg', 'soil.clay_fraction', 'soil.permeability',
    'hydrology.flow_accumulation', 'hydrology.floodplain_probability',
    'hydrology.groundwater_depth_m', 'climate.annual_precipitation_mm',
    'vegetation.ndvi', 'ecology.habitat_type', 'ecology.distance_to_habitat_m',
    'land_use.agricultural_quality', 'economic.intervention_cost_per_ha',
}


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


DimensionValue = str | int | float | bool | list[str] | list[int]


class DimensionDefinition(Record):
    name: str
    allowed_values: list[DimensionValue]
    description: str


class ObservationDefinition(Record):
    id: str
    version: str = '1'
    description: str
    value_kind: Literal['number', 'category', 'boolean', 'distribution']
    unit: str
    statistic: str
    value_denominator: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    coverage_basis: str
    allowed_categories: list[str] = Field(default_factory=list)
    dimensions: list[DimensionDefinition] = Field(default_factory=list)
    legacy_variables: list[str] = Field(default_factory=list)


StrictNumber = StrictFloat | StrictInt


class NumericValue(Record):
    kind: Literal['number'] = 'number'
    value: StrictNumber


class CategoryValue(Record):
    kind: Literal['category'] = 'category'
    value: str


class BooleanValue(Record):
    kind: Literal['boolean'] = 'boolean'
    value: bool


class DistributionEntry(Record):
    code: StrictInt
    category: str
    value: Annotated[StrictNumber, Field(ge=0, le=1)]


class DistributionValue(Record):
    kind: Literal['distribution'] = 'distribution'
    entries: list[DistributionEntry]
    original_legacy_text: str


TypedValue = Annotated[
    NumericValue | CategoryValue | BooleanValue | DistributionValue,
    Field(discriminator='kind'),
]


class TemporalReference(Record):
    status: Literal['recorded', 'not_recorded_legacy']
    value: datetime | None = None
    qualification: str | None = None

    @model_validator(mode='after')
    def consistent(self):
        if (self.status == 'recorded') != (self.value is not None):
            raise ValueError('Recorded temporal metadata requires a value; unrecorded metadata cannot have one')
        return self


class ArtifactAssetReference(Record):
    href: str
    media_type: str
    roles: list[str]
    crs: str
    spatial_resolution_m: float | None = None
    stac_item_href: str | None = None


class RawArtifactReference(Record):
    id: str
    legacy_raw_id: str
    retention_status: Literal['retained_artifact', 'external_asset_only', 'reference_only']
    storage_reference: str | None = None
    checksum: str | None = None
    assets: list[ArtifactAssetReference] = Field(default_factory=list)
    original_semantics: str


class SourceReference(Record):
    id: str
    provider: str
    dataset: str
    source_version: str
    source_url: str
    reference_period: TemporalReference
    retrieved_at: datetime
    raw_reference_ids: list[str]
    licence_or_attribution: str | None = None
    licence_metadata_status: Literal['recorded_legacy', 'not_recorded_legacy']


class SpatialSupport(Record):
    boundary_reference: str
    crs: str
    spatial_resolution_m: float | None = None
    support_type: Literal['parcel', 'cell', 'feature', 'asset']
    aggregation: str | None = None
    coverage_status: Literal['full', 'partial', 'unrecorded_legacy']
    coverage_fraction: float | None = Field(default=None, ge=0, le=1)
    coverage_basis: str
    denominator_metadata_status: Literal['recorded', 'not_recorded_legacy']
    thematic_completeness: Literal[
        'complete_for_declared_product', 'partial_inventory', 'unknown'
    ]

    @model_validator(mode='after')
    def coverage_consistent(self):
        if self.coverage_status == 'unrecorded_legacy' and self.coverage_fraction is not None:
            raise ValueError('Unrecorded coverage cannot carry a fraction')
        if self.coverage_status == 'full' and self.coverage_fraction != 1:
            raise ValueError('Full coverage requires an exact fraction of one')
        if self.coverage_status == 'partial' and not (
            self.coverage_fraction is not None and 0 < self.coverage_fraction < 1
        ):
            raise ValueError('Partial coverage requires a fraction strictly between zero and one')
        return self


LegacyStoredValue = float | int | str | bool | dict[str, float] | None


class ObservationProvenance(Record):
    legacy_observation_id: str
    legacy_variable: str
    legacy_value: LegacyStoredValue
    legacy_value_path: str
    legacy_observation_value: float | int | str | bool | None
    legacy_unit: str
    provider: str
    source_dataset: str
    source_version: str
    source_url: str | None = None
    derivation_method: str
    original_legacy_method: str
    observation_period: TemporalReference
    retrieved_at: datetime
    legacy_quality_semantics: str


class PriorityHabitatClassReference(Record):
    code: str
    name: str
    status: Literal['priority', 'supporting_non_priority']


class PriorityHabitatFeatureQualifier(Record):
    code: str
    description: str


class SourceFeatureReference(Record):
    id: str
    source_reference_id: str
    raw_reference_ids: list[str]
    source_feature_id: str
    source_global_id: str
    source_object_id: int
    source_release: str
    source_geometry_fingerprint: str
    source_area_ha_rounded: float
    parcel_intersection_area_ha: float
    parcel_intersection_fraction: float = Field(ge=0, le=1)
    main_habitats: list[PriorityHabitatClassReference]
    feature_qualifiers: list[PriorityHabitatFeatureQualifier]
    other_classification: str | None = None
    additional_habitat_codes: list[str]
    primary_source: str | None = None


class PriorityHabitatMeasurement(Record):
    mapped_intersection_area_ha: float = Field(ge=0)
    parcel_area_ha: float = Field(gt=0)
    overlap_fraction: float = Field(ge=0, le=1)


class PriorityHabitatProvenance(Record):
    kind: Literal['native_priority_habitats_inventory_v3'] = 'native_priority_habitats_inventory_v3'
    provider: Literal['Natural England'] = 'Natural England'
    source_dataset: Literal['Priority Habitats Inventory (England)'] = 'Priority Habitats Inventory (England)'
    source_release: str
    source_schema_version: str
    classification: str
    source_url: str
    source_metadata_revision_date: str | None = None
    source_capture_end_date: str | None = None
    source_service_data_last_edit: datetime | None = None
    retrieved_at: datetime
    derivation_method: Literal[
        'per-HabCode union and all-main-priority spatial union / EPSG:27700 / v1'
    ] = 'per-HabCode union and all-main-priority spatial union / EPSG:27700 / v1'


class BuiltWorldObjectBase(Record):
    id: str
    source_reference_id: str
    raw_reference_ids: list[str]
    source_feature_id: str
    source_release: str
    feature_code: int
    source_geometry: dict[str, Any]
    source_crs: Literal['EPSG:27700'] = 'EPSG:27700'
    source_geometry_fingerprint: str


class MappedBuildingObject(BuiltWorldObjectBase):
    object_type: Literal['building'] = 'building'


class FunctionalSiteObject(BuiltWorldObjectBase):
    object_type: Literal['functional_site'] = 'functional_site'
    distinctive_name: str | None = None
    site_theme: str
    classification: str


class RailwayTrackObject(BuiltWorldObjectBase):
    object_type: Literal['railway_track'] = 'railway_track'
    classification: str


class RailwayStationObject(BuiltWorldObjectBase):
    object_type: Literal['railway_station'] = 'railway_station'
    distinctive_name: str
    classification: str


BuiltWorldObject = Annotated[
    MappedBuildingObject | FunctionalSiteObject | RailwayTrackObject | RailwayStationObject,
    Field(discriminator='object_type'),
]


class RelationshipMeasurements(Record):
    overlap_area_m2: float | None = Field(default=None, ge=0)
    parcel_overlap_fraction: float | None = Field(default=None, ge=0, le=1)
    object_overlap_fraction: float | None = Field(default=None, ge=0, le=1)
    length_within_m: float | None = Field(default=None, ge=0)
    minimum_distance_m: float | None = Field(default=None, ge=0)


class SpatialRelationshipProvenance(Record):
    provider: Literal['Ordnance Survey'] = 'Ordnance Survey'
    source_dataset: Literal['OS OpenMap - Local'] = 'OS OpenMap - Local'
    source_release: str
    source_schema_version: str
    source_reference_id: str
    raw_reference_ids: list[str]
    processing_method: Literal['crc_openmap_local_spatial_v1'] = OML_PROCESSING_VERSION


class ParcelObjectRelationship(Record):
    id: str
    parcel_reference: str
    object_id: str
    predicate: Literal[
        'overlaps', 'touches', 'contained_within', 'crosses', 'intersects',
        'minimum_distance',
    ]
    geometry_semantics: str
    measurements: RelationshipMeasurements
    support_crs: Literal['EPSG:27700'] = 'EPSG:27700'
    provenance: SpatialRelationshipProvenance


class BuiltWorldMeasurement(Record):
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


class BuiltWorldProvenance(Record):
    kind: Literal['native_os_openmap_local_2026_04'] = 'native_os_openmap_local_2026_04'
    provider: Literal['Ordnance Survey'] = 'Ordnance Survey'
    source_dataset: Literal['OS OpenMap - Local'] = 'OS OpenMap - Local'
    source_release: str
    source_schema_version: str
    source_crs: Literal['EPSG:27700'] = 'EPSG:27700'
    source_url: str
    retrieved_at: datetime
    derivation_method: Literal['crc_openmap_local_spatial_v1'] = OML_PROCESSING_VERSION


class LandObservation(Record):
    id: str
    definition_id: str
    dimensions: dict[str, DimensionValue] = Field(default_factory=dict)
    value: TypedValue
    unit: str
    availability: Literal['available', 'partial']
    known_zero: bool
    support: SpatialSupport
    source_reference_ids: list[str]
    raw_reference_ids: list[str]
    parent_observation_ids: list[str] = Field(default_factory=list)
    provenance: ObservationProvenance
    limitations: str


class PriorityHabitatObservation(Record):
    id: str
    definition_id: str
    dimensions: dict[str, DimensionValue] = Field(default_factory=dict)
    mapped_habitat_name: str | None = None
    value: NumericValue
    unit: Literal['fraction'] = 'fraction'
    availability: Literal['available', 'partial']
    known_zero: bool
    support: SpatialSupport
    measurement: PriorityHabitatMeasurement
    source_reference_ids: list[str]
    raw_reference_ids: list[str]
    source_feature_reference_ids: list[str] = Field(default_factory=list)
    parent_observation_ids: list[str] = Field(default_factory=list)
    provenance: PriorityHabitatProvenance
    limitations: str


class BuiltWorldObservation(Record):
    id: str
    definition_id: str
    dimensions: dict[str, DimensionValue] = Field(default_factory=dict)
    value: NumericValue
    unit: Literal['fraction', 'm']
    availability: Literal['available'] = 'available'
    known_zero: bool
    support: SpatialSupport
    measurement: BuiltWorldMeasurement
    source_reference_ids: list[str]
    raw_reference_ids: list[str]
    supporting_object_ids: list[str]
    parent_observation_ids: list[str] = Field(default_factory=list)
    provenance: BuiltWorldProvenance
    limitations: str


LandObservationRecord = LandObservation | PriorityHabitatObservation | BuiltWorldObservation


class EvidenceGap(Record):
    id: str
    definition_id: str | None = None
    dimensions: dict[str, DimensionValue] = Field(default_factory=dict)
    legacy_variable: str | None = None
    state: Literal[
        'source_not_connected', 'unavailable', 'absent_observation',
        'incomplete_inventory', 'unsupported_processing_case', 'partial_coverage',
    ]
    reason_code: str
    reason: str
    source_reference_ids: list[str] = Field(default_factory=list)
    raw_reference_ids: list[str] = Field(default_factory=list)


class Diagnostic(Record):
    id: str
    severity: Literal['info', 'warning', 'error']
    code: str
    message: str
    related_ids: list[str] = Field(default_factory=list)


class CapabilityDisposition(Record):
    legacy_variable: str
    disposition: Literal[
        'source_backed_core', 'explicit_gap', 'legacy_module_output',
        'registered_unconnected',
    ]
    projected_definition_ids: list[str] = Field(default_factory=list)
    note: str


class EvidenceSelection(Record):
    semantic_key: str
    observation_id: str
    policy: Literal['legacy_selection', 'only_candidate', 'source_scoped_dimension']


class LegacyModuleOutputReference(Record):
    legacy_observation_id: str
    variable: str
    value: float | int | str | bool | None
    unit: str
    source_version: str
    parent_legacy_observation_ids: list[str]
    classification: Literal['legacy_wetland_module_output'] = 'legacy_wetland_module_output'


class LegacyWetlandResultReference(Record):
    status: Literal['referenced_not_copied'] = 'referenced_not_copied'
    payload_fingerprint: str
    model_version: str | None = None
    model_signature: str | None = None
    state_fingerprint: str | None = None


class EvidenceSnapshotIdentity(Record):
    schema_version: Literal['land_evidence_v1'] = SCHEMA_VERSION
    projection_id: str
    registry_version: Literal[
        'land_evidence_registry_v1', 'land_evidence_registry_v2',
        'land_evidence_registry_v3'
    ] = REGISTRY_VERSION
    legacy_assessment_fingerprint: str
    legacy_state_fingerprint: str
    legacy_location_id: str
    site_name: str | None = None
    boundary_version: int
    boundary_reference: str
    boundary_geometry_fingerprint: str
    geography: str
    evidence_as_of: datetime


class LandEvidenceProjection(Record):
    identity: EvidenceSnapshotIdentity
    definitions: list[ObservationDefinition]
    raw_references: list[RawArtifactReference]
    source_references: list[SourceReference]
    source_feature_references: list[SourceFeatureReference] = Field(default_factory=list)
    objects: list[BuiltWorldObject] = Field(default_factory=list)
    relationships: list[ParcelObjectRelationship] = Field(default_factory=list)
    observations: list[LandObservationRecord]
    selections: list[EvidenceSelection]
    gaps: list[EvidenceGap]
    capabilities: list[CapabilityDisposition]
    diagnostics: list[Diagnostic]
    legacy_module_outputs: list[LegacyModuleOutputReference]
    legacy_wetland_result: LegacyWetlandResultReference | None = None


def _dimension(name: str, allowed: list[DimensionValue], description: str) -> DimensionDefinition:
    return DimensionDefinition(name=name, allowed_values=allowed, description=description)


def _definition(
    id: str,
    description: str,
    value_kind: Literal['number', 'category', 'boolean', 'distribution'],
    unit: str,
    statistic: str,
    coverage_basis: str,
    *,
    denominator: str | None = None,
    categories: list[str] | None = None,
    dimensions: list[DimensionDefinition] | None = None,
    legacy: list[str] | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
) -> ObservationDefinition:
    legacy = legacy or []
    low, high = minimum, maximum
    if value_kind == 'number' and legacy:
        _, low, high = VARIABLES[legacy[0]]
    return ObservationDefinition(
        id=id, description=description, value_kind=value_kind, unit=unit,
        statistic=statistic, value_denominator=denominator,
        minimum=low, maximum=high,
        coverage_basis=coverage_basis, allowed_categories=categories or [],
        dimensions=dimensions or [], legacy_variables=legacy,
    )


_WORLD_COVER_DIMENSION = _dimension(
    'classification', [WORLD_COVER_CLASSIFICATION],
    'The exact ESA WorldCover 2021 v200 vocabulary and release profile.',
)

LAND_EVIDENCE_V1_DEFINITIONS = [
    _definition('physical.elevation.mean', 'Mean bare-earth elevation of valid native cell centres.', 'number', 'm',
                'arithmetic_mean', 'eligible_native_elevation_cell_centres', legacy=['terrain.elevation_m']),
    _definition('physical.elevation.minimum', 'Minimum bare-earth elevation of valid native cell centres.', 'number', 'm',
                'minimum', 'eligible_native_elevation_cell_centres', legacy=['terrain.elevation_min_m']),
    _definition('physical.elevation.maximum', 'Maximum bare-earth elevation of valid native cell centres.', 'number', 'm',
                'maximum', 'eligible_native_elevation_cell_centres', legacy=['terrain.elevation_max_m']),
    _definition('physical.elevation.stddev', 'Population standard deviation of valid native elevations.', 'number', 'm',
                'population_standard_deviation', 'eligible_native_elevation_cell_centres', legacy=['terrain.elevation_std_m']),
    _definition('physical.slope.mean', 'Mean Horn 3x3 slope over valid native neighbourhoods.', 'number', 'degree',
                'arithmetic_mean', 'eligible_native_slope_cell_centres', legacy=['terrain.slope_deg']),
    _definition('physical.slope.p90', 'Linear-interpolated 90th percentile Horn slope.', 'number', 'degree',
                'linear_percentile_90', 'eligible_native_slope_cell_centres', legacy=['terrain.slope_p90_deg']),
    _definition('physical.slope.maximum', 'Maximum Horn 3x3 slope over valid native neighbourhoods.', 'number', 'degree',
                'maximum', 'eligible_native_slope_cell_centres', legacy=['terrain.slope_max_deg']),
    _definition('physical.watercourse.distance_min', 'Minimum parcel distance to the mapped OS Open Rivers line network.', 'number', 'm',
                'minimum_polygon_to_line_distance', 'complete_mapped_network_search_within_5000m', legacy=['hydrology.distance_to_water_m']),
    _definition('physical.watercourse.intersects', 'Whether the parcel intersects the mapped OS Open Rivers line network, including touches.', 'boolean', 'boolean',
                'ogc_intersects_including_touches', 'complete_mapped_network_search_within_5000m', legacy=['hydrology.watercourse_intersection']),
    _definition('physical.watercourse.proximity_area_fraction', 'Parcel fraction inside a round buffer of the mapped line network.', 'number', 'fraction',
                'unioned_round_buffer_intersection_fraction', 'whole_parcel_against_mapped_network', denominator='parcel_area',
                dimensions=[_dimension('distance_m', [100], 'Round buffer distance in metres.')],
                legacy=['hydrology.within_100m_watercourse_fraction']),
    _definition('ecology.land_cover.class_distribution', 'Geodesic native-cell area distribution over valid WorldCover classes.', 'distribution', 'fraction',
                'class_area_distribution', 'eligible_worldcover_cell_centres', denominator='valid_sample_area',
                categories=list(WORLD_COVER_CLASSES.values()), dimensions=[_WORLD_COVER_DIMENSION],
                legacy=['land_use.current_cover']),
    _definition('ecology.land_cover.dominant_class', 'Largest valid-sample WorldCover class, ties resolved by lowest source code.', 'category', 'category',
                'argmax_class_area_fraction', 'eligible_worldcover_cell_centres', categories=list(WORLD_COVER_CLASSES.values()),
                dimensions=[_WORLD_COVER_DIMENSION], legacy=['land_use.current_cover']),
    _definition('built.mapped_built_up_fraction', 'WorldCover class 50 share of valid classified sample area; not a complete infrastructure footprint.', 'number', 'fraction',
                'class_area_fraction', 'eligible_worldcover_cell_centres', denominator='valid_sample_area',
                dimensions=[_WORLD_COVER_DIMENSION], legacy=['land_use.developed_fraction']),
    _definition('ecology.mapped_herbaceous_wetland_fraction', 'WorldCover class 90 share; not actual complete wetland extent.', 'number', 'fraction',
                'class_area_fraction', 'eligible_worldcover_cell_centres', denominator='valid_sample_area',
                dimensions=[_WORLD_COVER_DIMENSION], legacy=['ecology.mapped_wetland_fraction']),
    _definition('physical.mapped_permanent_water_fraction', 'WorldCover class 80 share of valid classified sample area.', 'number', 'fraction',
                'class_area_fraction', 'eligible_worldcover_cell_centres', denominator='valid_sample_area',
                dimensions=[_WORLD_COVER_DIMENSION], legacy=['hydrology.surface_water_fraction']),
    _definition('physical.flood.mapped_extent_fraction', 'Overlap with present-day Flood Map for Planning Zones 2 and 3 combined.', 'number', 'fraction',
                'unioned_polygon_overlap_fraction', 'whole_parcel_within_imported_extract', denominator='parcel_area',
                dimensions=[
                    _dimension('zone_set', [[2, 3]], 'Flood Zones 2 and 3 combined.'),
                    _dimension('scenario', ['present_day'], 'Published map scenario.'),
                    _dimension('defence_basis', ['ignored'], 'Benefits of defences are ignored.'),
                    _dimension('sources', [['rivers', 'sea']], 'Flood sources represented by the map.'),
                ], legacy=['hydrology.mapped_flood_extent_fraction']),
    _definition('designations.overlap_fraction', 'Overlap with one declared designation type and status.', 'number', 'fraction',
                'unioned_polygon_overlap_fraction', 'whole_parcel_within_imported_extract', denominator='parcel_area',
                dimensions=[
                    _dimension('designation_type', ['SSSI'], 'Sites of Special Scientific Interest only.'),
                    _dimension('status', ['notified'], 'Notified sites only.'),
                ], legacy=['regulatory.protected_area_fraction']),
    _definition('ecology.ancient_woodland.mapped_overlap_fraction', 'Inventory-specific mapped ancient-woodland overlap; broader irreplaceability remains unresolved.', 'number', 'fraction',
                'unioned_polygon_overlap_fraction', 'whole_parcel_within_imported_extract', denominator='parcel_area',
                dimensions=[_dimension('inventory', ['legacy', 'revised'], 'The retained Natural England inventory edition.')],
                legacy=['ecology.irreplaceable_habitat_fraction']),
]

PRIORITY_HABITAT_DEFINITIONS = [
    _definition(
        'ecology.priority_habitat.mapped_overlap_fraction',
        'Parcel fraction mapped as one PHI Version 3 main priority-habitat code in the declared release; overlapping features for the same code are unioned.',
        'number', 'fraction', 'per_habitat_code_unioned_polygon_overlap_fraction',
        'whole_parcel_within_acquired_phi_extract', denominator='parcel_area',
        dimensions=[
            _dimension('classification', [PHI_CLASSIFICATION],
                       'Natural England Priority Habitats Inventory Version 3 vocabulary.'),
            _dimension('habitat_code', list(PHI_PRIORITY_HABITATS),
                       'Natural England PHI main priority-habitat code.'),
        ], minimum=0, maximum=1,
    ),
    _definition(
        'ecology.priority_habitat.any_mapped_overlap_fraction',
        'Parcel fraction in the spatial union of PHI polygons carrying at least one main priority-habitat code; geometry is counted once across codes and overlapping features.',
        'number', 'fraction', 'all_main_priority_habitat_spatial_union_overlap_fraction',
        'whole_parcel_within_acquired_phi_extract', denominator='parcel_area',
        dimensions=[
            _dimension('classification', [PHI_CLASSIFICATION],
                       'Natural England Priority Habitats Inventory Version 3 vocabulary.'),
        ], minimum=0, maximum=1,
    ),
]

BUILT_WORLD_DEFINITIONS = [
    _definition(
        'built.building.mapped_overlap_fraction',
        'Parcel fraction in the spatial union of generalized OS OpenMap - Local Building polygons; not an exact legal or engineering footprint.',
        'number', 'fraction', 'clipped_source_polygon_spatial_union',
        'whole_parcel_within_acquired_openmap_local_extract', denominator='parcel_area',
        minimum=0, maximum=1,
    ),
    _definition(
        'built.functional_site.mapped_overlap_fraction',
        'Parcel fraction in the spatial union of OS OpenMap - Local FunctionalSite polygons. Object-level names, themes and classifications remain distinct.',
        'number', 'fraction', 'clipped_source_polygon_spatial_union',
        'whole_parcel_within_acquired_openmap_local_extract', denominator='parcel_area',
        minimum=0, maximum=1,
    ),
    _definition(
        'transport.railway_track.mapped_length_within',
        'Length of the spatial union of OS OpenMap - Local RailwayTrack lines within the parcel; lines are not surface footprints or track counts.',
        'number', 'm', 'clipped_source_line_spatial_union',
        'whole_parcel_within_acquired_openmap_local_extract', minimum=0,
    ),
    _definition(
        'transport.railway_track.distance_min',
        'Minimum EPSG:27700 Euclidean distance from the parcel to a mapped OS OpenMap - Local RailwayTrack line within a complete 5 km search.',
        'number', 'm', 'minimum_euclidean_distance',
        'complete_mapped_railway_search_within_5000m', minimum=0,
        maximum=OML_SEARCH_RADIUS_M,
    ),
    _definition(
        'transport.railway_station.distance_min',
        'Minimum EPSG:27700 Euclidean distance from the parcel to a mapped OS OpenMap - Local RailwayStation point within a complete 5 km search.',
        'number', 'm', 'minimum_euclidean_distance',
        'complete_mapped_railway_search_within_5000m', minimum=0,
        maximum=OML_SEARCH_RADIUS_M,
    ),
]

LAND_EVIDENCE_V2_DEFINITIONS = LAND_EVIDENCE_V1_DEFINITIONS + PRIORITY_HABITAT_DEFINITIONS
LAND_EVIDENCE_V3_DEFINITIONS = LAND_EVIDENCE_V2_DEFINITIONS + BUILT_WORLD_DEFINITIONS
DEFINITIONS_BY_REGISTRY = {
    REGISTRY_VERSION: LAND_EVIDENCE_V1_DEFINITIONS,
    PHI_REGISTRY_VERSION: LAND_EVIDENCE_V2_DEFINITIONS,
    BUILT_WORLD_REGISTRY_VERSION: LAND_EVIDENCE_V3_DEFINITIONS,
}
DEFINITIONS_BY_ID = {definition.id: definition for definition in LAND_EVIDENCE_V3_DEFINITIONS}


LEGACY_CORE_MAPPINGS: dict[str, tuple[str, dict[str, DimensionValue]]] = {
    'terrain.elevation_m': ('physical.elevation.mean', {}),
    'terrain.elevation_min_m': ('physical.elevation.minimum', {}),
    'terrain.elevation_max_m': ('physical.elevation.maximum', {}),
    'terrain.elevation_std_m': ('physical.elevation.stddev', {}),
    'terrain.slope_deg': ('physical.slope.mean', {}),
    'terrain.slope_p90_deg': ('physical.slope.p90', {}),
    'terrain.slope_max_deg': ('physical.slope.maximum', {}),
    'hydrology.distance_to_water_m': ('physical.watercourse.distance_min', {}),
    'hydrology.watercourse_intersection': ('physical.watercourse.intersects', {}),
    'hydrology.within_100m_watercourse_fraction': (
        'physical.watercourse.proximity_area_fraction', {'distance_m': 100}),
    'land_use.current_cover': (
        'ecology.land_cover.dominant_class', {'classification': WORLD_COVER_CLASSIFICATION}),
    'land_use.developed_fraction': (
        'built.mapped_built_up_fraction', {'classification': WORLD_COVER_CLASSIFICATION}),
    'ecology.mapped_wetland_fraction': (
        'ecology.mapped_herbaceous_wetland_fraction', {'classification': WORLD_COVER_CLASSIFICATION}),
    'hydrology.surface_water_fraction': (
        'physical.mapped_permanent_water_fraction', {'classification': WORLD_COVER_CLASSIFICATION}),
    'hydrology.mapped_flood_extent_fraction': (
        'physical.flood.mapped_extent_fraction', {
            'zone_set': [2, 3], 'scenario': 'present_day',
            'defence_basis': 'ignored', 'sources': ['rivers', 'sea'],
        }),
    'regulatory.protected_area_fraction': (
        'designations.overlap_fraction', {'designation_type': 'SSSI', 'status': 'notified'}),
}

CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS = set(LEGACY_CORE_MAPPINGS) | {
    'ecology.irreplaceable_habitat_fraction'
}

_LEGACY_DISPOSITION_GROUPS = (
    CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS,
    set(EXPLICIT_GAPS),
    LEGACY_MODULE_OUTPUTS,
    REGISTERED_UNCONNECTED,
)
if (
    set().union(*_LEGACY_DISPOSITION_GROUPS) != set(VARIABLES)
    or sum(len(group) for group in _LEGACY_DISPOSITION_GROUPS) != len(VARIABLES)
):
    raise RuntimeError(
        'land_evidence_v1 capability dispositions must partition the legacy registry exactly'
    )


class LandEvidenceValidationError(ValueError):
    """Raised when saved or projected evidence is structurally unsafe to consume."""


def _observations(state: EarthState) -> list[LegacyObservation]:
    return [
        observation
        for domain in state.normalized.values()
        for group in domain.values()
        for observation in group
    ] + list(state.derived.values())


def _projection_identity_seed(
    state: EarthState, findings: list[Any], registry_version: str,
) -> dict[str, Any]:
    """Return only boundary and evidence inputs that can affect core output IDs.

    Legacy assessment presentation, site names, wetland features/results and
    other module-owned fields deliberately do not scope core observation IDs.
    The final persisted content hash is still calculated from the complete
    validated core payload.
    """
    normalized: dict[str, dict[str, list[dict[str, Any]]]] = {}
    included = CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS | set(EXPLICIT_GAPS)
    for domain, groups in state.normalized.items():
        for name, observations in groups.items():
            variable = domain + '.' + name
            if variable in included:
                normalized.setdefault(domain, {})[name] = [
                    {
                        key: value for key, value in observation.model_dump(mode='json').items()
                        if key not in ('missing_input_variables', 'synthetic')
                    }
                    for observation in observations
                ]
    selected = {
        variable: observation_id for variable, observation_id in state.selected.items()
        if variable in included
    }
    # Inventory zeroes survive only in legacy findings. Keep their original
    # positions because the precise lineage path is part of the observation.
    inventory_findings = [
        {
            'index': index,
            'finding': {
                key: finding.get(key) for key in (
                    'key', 'dataset_version', 'coverage', 'fraction', 'limitations',
                )
            },
        }
        for index, finding in enumerate(findings)
        if isinstance(finding, dict) and finding.get('key') in ('woodland', 'woodland_revised')
    ]
    result = {
        'schema_version': SCHEMA_VERSION,
        'registry_version': registry_version,
        'location_id': state.location_id,
        'boundary_version': state.boundary_version,
        'boundary_geometry_fingerprint': fingerprint(state.geometry),
        'geography': state.geography,
        'evidence_as_of': state.as_of.isoformat(),
        'raw': [
            {
                key: value for key, value in raw.model_dump(mode='json').items()
                if key != 'synthetic'
            }
            for raw in state.raw
        ],
        'normalized': normalized,
        'selected': selected,
        'inventory_findings': inventory_findings,
    }
    if registry_version in (PHI_REGISTRY_VERSION, BUILT_WORLD_REGISTRY_VERSION):
        result['priority_habitat_findings'] = [
            {
                key: finding.get(key) for key in (
                    'key', 'dataset', 'publisher', 'source_url', 'retrieved',
                    'dataset_version', 'source_release',
                    'source_metadata_revision_date', 'source_capture_end_date',
                    'source_service_data_last_edit', 'coverage', 'coverage_fraction',
                    'limitations', 'attribution', 'licence', 'raw_sha256',
                    'raw_storage_reference', 'raw_semantics', 'priority_habitats',
                )
            }
            for finding in findings
            if isinstance(finding, dict) and finding.get('key') == 'priority_habitats'
        ]
    if registry_version == BUILT_WORLD_REGISTRY_VERSION:
        result['built_world_findings'] = [
            {
                key: finding.get(key) for key in (
                    'key', 'dataset', 'publisher', 'source_url', 'retrieved',
                    'dataset_version', 'source_release', 'coverage', 'coverage_fraction',
                    'limitations', 'attribution', 'licence', 'raw_sha256',
                    'raw_storage_reference', 'raw_semantics', 'built_world',
                )
            }
            for finding in findings
            if isinstance(finding, dict) and finding.get('key') == 'built_world'
        ]
    return result


def _validate_legacy_state(state: EarthState) -> None:
    errors: list[str] = []
    observations = _observations(state)
    observation_ids = [observation.id for observation in observations]
    raw_ids = [raw.id for raw in state.raw]
    duplicates = sorted({value for value in observation_ids if observation_ids.count(value) > 1})
    if duplicates:
        errors.append('Duplicate legacy observation IDs: ' + ', '.join(duplicates))
    duplicate_raw = sorted({value for value in raw_ids if raw_ids.count(value) > 1})
    if duplicate_raw:
        errors.append('Duplicate legacy raw IDs: ' + ', '.join(duplicate_raw))
    observation_set = set(observation_ids)
    raw_set = set(raw_ids)
    by_id = {observation.id: observation for observation in observations}
    for variable, selected_id in state.selected.items():
        domain, name = variable.split('.', 1)
        candidates = state.normalized.get(domain, {}).get(name, [])
        if selected_id not in {candidate.id for candidate in candidates}:
            errors.append(f'Selected legacy reference does not resolve for {variable}: {selected_id}')
    for observation in observations:
        missing_parents = sorted(set(observation.input_ids) - observation_set)
        if missing_parents:
            errors.append(f'Dangling parent(s) from {observation.id}: {", ".join(missing_parents)}')
        missing_raw = sorted(set(observation.raw_source_ids) - raw_set)
        if missing_raw:
            errors.append(f'Dangling raw reference(s) from {observation.id}: {", ".join(missing_raw)}')
        if observation.value is not None and observation.input_coverage == 0:
            errors.append(f'Non-null legacy observation has zero coverage: {observation.id}')
        if observation.value is not None and observation.source != 'CRC' and not observation.raw_source_ids:
            errors.append(f'Available source observation has no raw reference: {observation.id}')

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(observation_id: str, path: list[str]) -> None:
        if observation_id in visiting:
            start = path.index(observation_id)
            errors.append('Cyclic legacy lineage: ' + ' -> '.join(path[start:] + [observation_id]))
            return
        if observation_id in visited:
            return
        visiting.add(observation_id)
        path.append(observation_id)
        for parent in by_id[observation_id].input_ids:
            if parent in by_id:
                visit(parent, path)
        path.pop()
        visiting.remove(observation_id)
        visited.add(observation_id)

    for observation_id in observation_ids:
        visit(observation_id, [])
    if errors:
        raise LandEvidenceValidationError('; '.join(dict.fromkeys(errors)))


def _temporal(value: datetime | None, qualification: str | None = None) -> TemporalReference:
    return TemporalReference(
        status='recorded' if value is not None else 'not_recorded_legacy',
        value=value,
        qualification=qualification,
    )


def _diagnostic(
    diagnostics: list[Diagnostic], severity: Literal['info', 'warning', 'error'],
    code: str, message: str, related_ids: list[str] | None = None,
) -> None:
    related_ids = related_ids or []
    diagnostics.append(Diagnostic(
        id='diagnostic:' + fingerprint([code, message, related_ids]),
        severity=severity, code=code, message=message, related_ids=related_ids,
    ))


def _gap(
    gaps: list[EvidenceGap], *, definition_id: str | None, dimensions: dict[str, DimensionValue] | None,
    legacy_variable: str | None, state: Literal[
        'source_not_connected', 'unavailable', 'absent_observation',
        'incomplete_inventory', 'unsupported_processing_case', 'partial_coverage'],
    reason_code: str, reason: str, source_reference_ids: list[str] | None = None,
    raw_reference_ids: list[str] | None = None,
) -> None:
    payload = [definition_id, dimensions or {}, legacy_variable, state, reason_code, reason,
               source_reference_ids or [], raw_reference_ids or []]
    gaps.append(EvidenceGap(
        id='gap:' + fingerprint(payload), definition_id=definition_id,
        dimensions=dimensions or {}, legacy_variable=legacy_variable,
        state=state, reason_code=reason_code, reason=reason,
        source_reference_ids=source_reference_ids or [], raw_reference_ids=raw_reference_ids or [],
    ))


def _raw_ids(observation: LegacyObservation) -> tuple[list[str], list[str]]:
    return (
        ['source:' + raw_id for raw_id in observation.raw_source_ids],
        ['raw:' + raw_id for raw_id in observation.raw_source_ids],
    )


def _support(
    observation: LegacyObservation,
    definition_id: str,
    *,
    coverage_fraction: float | None = None,
    thematic_completeness: Literal[
        'complete_for_declared_product', 'partial_inventory', 'unknown'
    ] = 'complete_for_declared_product',
) -> SpatialSupport:
    coverage = observation.input_coverage if coverage_fraction is None else coverage_fraction
    status: Literal['full', 'partial', 'unrecorded_legacy']
    if coverage == 1:
        status = 'full'
    elif coverage is not None and 0 < coverage < 1:
        status = 'partial'
    else:
        status = 'unrecorded_legacy'
        coverage = None
    return SpatialSupport(
        boundary_reference=observation.spatial.geometry_or_cell_reference,
        crs=observation.spatial.crs,
        spatial_resolution_m=observation.spatial.spatial_resolution_m,
        support_type=observation.spatial.support,
        aggregation=observation.spatial.aggregation,
        coverage_status=status,
        coverage_fraction=coverage,
        coverage_basis=DEFINITIONS_BY_ID[definition_id].coverage_basis,
        denominator_metadata_status='not_recorded_legacy',
        thematic_completeness=thematic_completeness,
    )


def _availability(support: SpatialSupport) -> Literal['available', 'partial']:
    return 'partial' if support.coverage_status == 'partial' else 'available'


def _known_zero(value: TypedValue) -> bool:
    return isinstance(value, NumericValue) and value.value == 0


def _legacy_path(state: EarthState, observation: LegacyObservation) -> str:
    domain, name = observation.variable.split('.', 1)
    group = state.normalized.get(domain, {}).get(name, [])
    for index, candidate in enumerate(group):
        if candidate is observation:
            return f'environmental_state.normalized.{domain}.{name}[{index}].value'
    return f'environmental_state.derived.{observation.variable}.value'


def _provenance(
    state: EarthState,
    observation: LegacyObservation,
    *,
    legacy_value: LegacyStoredValue | None = None,
    legacy_value_path: str | None = None,
) -> ObservationProvenance:
    value = observation.value if legacy_value is None else legacy_value
    qualification = None
    if observation.source_dataset == 'ESA WorldCover 2021 v200' and observation.timestamp is not None:
        qualification = 'Recorded timestamp is the start of the 2021 annual reference period, not a point survey.'
    return ObservationProvenance(
        legacy_observation_id=observation.id,
        legacy_variable=observation.variable,
        legacy_value=value,
        legacy_value_path=legacy_value_path or _legacy_path(state, observation),
        legacy_observation_value=observation.value,
        legacy_unit=observation.unit,
        provider=observation.source,
        source_dataset=observation.source_dataset,
        source_version=observation.source_version,
        source_url=observation.source_url,
        derivation_method=observation.method,
        original_legacy_method=observation.method,
        observation_period=_temporal(observation.timestamp, qualification),
        retrieved_at=observation.retrieved_at,
        legacy_quality_semantics=(
            f'Legacy confidence={observation.confidence!r}; observed_or_derived={observation.observed_or_derived}; '
            f'epistemic_status={observation.epistemic_status}. These are retained legacy support semantics, '
            'not a Land Evidence Core confidence score.'
        ),
    )


def _observation_id(
    snapshot_id: str, definition_id: str, dimensions: dict[str, DimensionValue],
    legacy_observation_id: str, legacy_value_path: str,
) -> str:
    return 'observation:' + fingerprint([
        SCHEMA_VERSION, snapshot_id, definition_id, dimensions,
        legacy_observation_id, legacy_value_path,
    ])


def _typed_legacy_value(
    observation: LegacyObservation,
    definition: ObservationDefinition,
) -> TypedValue | None:
    value = observation.value
    if value is None:
        return None
    if definition.value_kind == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        return NumericValue(value=value)
    if definition.value_kind == 'category':
        if not isinstance(value, str) or value not in definition.allowed_categories:
            return None
        return CategoryValue(value=value)
    if definition.value_kind == 'boolean':
        if value == 'yes':
            return BooleanValue(value=True)
        if value == 'no':
            return BooleanValue(value=False)
        return None
    return None


def _classify_unavailable(reason: str) -> tuple[
    Literal['unavailable', 'unsupported_processing_case'], str
]:
    lowered = reason.lower()
    if any(term in lowered for term in (
        'tile boundary', 'processing budget', 'raster budget', 'unsupported', 'exceeds parcel processing',
    )):
        return 'unsupported_processing_case', 'unsupported_processing_case'
    if 'no valid' in lowered or 'fewer than four' in lowered:
        return 'unavailable', 'no_valid_cells'
    if 'search radius' in lowered or 'within complete 5km' in lowered:
        return 'unavailable', 'search_limit_reached'
    if 'outside' in lowered or 'extent' in lowered:
        return 'unavailable', 'outside_acquired_extent'
    return 'unavailable', 'source_failure'


def _extract_worldcover_distribution(
    state: EarthState,
    observation: LegacyObservation,
    snapshot_id: str,
    diagnostics: list[Diagnostic],
    gaps: list[EvidenceGap],
) -> LandObservation | None:
    definition_id = 'ecology.land_cover.class_distribution'
    dimensions = {'classification': WORLD_COVER_CLASSIFICATION}
    method = observation.method
    source_ids, raw_ids = _raw_ids(observation)
    if not method.startswith(WORLD_COVER_METHOD_PREFIX):
        message = 'WorldCover distribution was not extracted because the exact recognized legacy method prefix is absent.'
        _diagnostic(diagnostics, 'error', 'worldcover_distribution_unextractable', message, [observation.id])
        _gap(gaps, definition_id=definition_id, dimensions=dimensions,
             legacy_variable='land_use.current_cover', state='unavailable',
             reason_code='legacy_distribution_format_unrecognized', reason=message,
             source_reference_ids=source_ids, raw_reference_ids=raw_ids)
        return None
    original_text = method[len(WORLD_COVER_METHOD_PREFIX):]
    try:
        decoded = json.loads(original_text)
    except (TypeError, json.JSONDecodeError):
        decoded = None
    labels = list(WORLD_COVER_CLASSES.values())
    valid = (
        isinstance(decoded, dict)
        and list(sorted(decoded)) == list(sorted(labels))
        and all(
            not isinstance(decoded[label], bool)
            and isinstance(decoded[label], (int, float))
            and math.isfinite(decoded[label])
            and 0 <= decoded[label] <= 1
            for label in labels
        )
        and math.isclose(sum(decoded.values()), 1, rel_tol=0, abs_tol=1e-12)
    )
    if not valid:
        message = 'WorldCover distribution was not extracted because the recognized legacy payload is malformed.'
        _diagnostic(diagnostics, 'error', 'worldcover_distribution_malformed', message, [observation.id])
        _gap(gaps, definition_id=definition_id, dimensions=dimensions,
             legacy_variable='land_use.current_cover', state='unavailable',
             reason_code='legacy_distribution_malformed', reason=message,
             source_reference_ids=source_ids, raw_reference_ids=raw_ids)
        return None
    entries = [
        DistributionEntry(code=code, category=label, value=decoded[label])
        for code, label in WORLD_COVER_CLASSES.items()
    ]
    path = _legacy_path(state, observation).removesuffix('.value') + '.method.Full class fractions'
    support = _support(observation, definition_id)
    value = DistributionValue(entries=entries, original_legacy_text=original_text)
    return LandObservation(
        id=_observation_id(snapshot_id, definition_id, dimensions, observation.id, path),
        definition_id=definition_id, dimensions=dimensions, value=value, unit='fraction',
        availability=_availability(support), known_zero=False, support=support,
        source_reference_ids=source_ids, raw_reference_ids=raw_ids,
        provenance=_provenance(state, observation, legacy_value=decoded, legacy_value_path=path),
        limitations=observation.uncertainty,
    )


def _capabilities() -> list[CapabilityDisposition]:
    mapped: dict[str, list[str]] = defaultdict(list)
    for definition in LAND_EVIDENCE_V1_DEFINITIONS:
        for variable in definition.legacy_variables:
            mapped[variable].append(definition.id)
    capabilities = []
    for variable in VARIABLES:
        if variable in CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS:
            note = 'Projected as precise, source-scoped Land Evidence Core evidence.'
            if variable == 'ecology.irreplaceable_habitat_fraction':
                note = ('Only inventory-specific ancient-woodland observations are projected. '
                        'The broader irreplaceable-habitat interpretation remains an explicit gap.')
            capabilities.append(CapabilityDisposition(
                legacy_variable=variable, disposition='source_backed_core',
                projected_definition_ids=sorted(mapped[variable]), note=note,
            ))
        elif variable in EXPLICIT_GAPS:
            capabilities.append(CapabilityDisposition(
                legacy_variable=variable, disposition='explicit_gap',
                note=EXPLICIT_GAPS[variable][1],
            ))
        elif variable in LEGACY_MODULE_OUTPUTS:
            capabilities.append(CapabilityDisposition(
                legacy_variable=variable, disposition='legacy_module_output',
                note='Retained only as a legacy wetland/module output; never a core land fact.',
            ))
        elif variable in REGISTERED_UNCONNECTED:
            capabilities.append(CapabilityDisposition(
                legacy_variable=variable, disposition='registered_unconnected',
                note='Registered in the legacy Earth vocabulary but no production source is connected.',
            ))
        else:  # Protected by the import-time partition invariant above.
            raise RuntimeError('No land_evidence_v1 disposition for ' + variable)
    return capabilities


def _semantic_key(definition_id: str, dimensions: dict[str, DimensionValue]) -> str:
    return definition_id + '|' + json.dumps(dimensions, sort_keys=True, separators=(',', ':'))


def _project_priority_habitats(
    finding: dict[str, Any], snapshot_id: str, boundary_reference: str,
    gaps: list[EvidenceGap],
) -> tuple[list[SourceFeatureReference], list[PriorityHabitatObservation]]:
    dataset_version = finding.get('dataset_version')
    source_release = finding.get('source_release')
    source_id = 'source:' + str(dataset_version)
    raw_id = 'raw:' + str(dataset_version)
    common_gap = {
        'definition_id': 'ecology.priority_habitat.any_mapped_overlap_fraction',
        'dimensions': {'classification': PHI_CLASSIFICATION},
        'legacy_variable': None,
        'source_reference_ids': [source_id],
        'raw_reference_ids': [raw_id],
    }
    coverage = finding.get('coverage')
    if coverage != 'covered':
        if coverage == 'partial':
            state = 'partial_coverage'
            reason_code = 'partial_acquired_coverage'
            reason = ('Only part of the parcel is inside the acquired PHI extract; '
                      'no parcel-wide mapped overlap or mapped-zero fact is asserted.')
        elif finding.get('raw_storage_reference'):
            state = 'unavailable'
            reason_code = 'outside_acquired_coverage'
            reason = 'The parcel is outside the fully acquired PHI extract.'
        else:
            state = 'unavailable'
            reason_code = 'source_unavailable'
            reason = 'The authoritative PHI source was unavailable or processing did not complete.'
        _gap(gaps, state=state, reason_code=reason_code,
             reason=reason + ' ' + finding.get('limitations', ''), **common_gap)
        return [], []

    summary = finding.get('priority_habitats')
    if not isinstance(summary, dict):
        raise LandEvidenceValidationError('Covered PHI finding has no native intersection summary')
    if summary.get('classification') != PHI_CLASSIFICATION:
        raise LandEvidenceValidationError('PHI finding classification is invalid')
    if summary.get('schema_version') != PHI_SOURCE_SCHEMA_VERSION:
        raise LandEvidenceValidationError('PHI finding source schema version is invalid')
    if not isinstance(source_release, str) or not source_release:
        raise LandEvidenceValidationError('PHI source release is missing')
    if summary.get('source_release') != source_release:
        raise LandEvidenceValidationError('PHI summary release does not match source release')
    source_url = finding.get('source_url')
    if not isinstance(source_url, str) or not source_url:
        raise LandEvidenceValidationError('PHI source URL is missing')

    feature_references: list[SourceFeatureReference] = []
    feature_id_by_uid: dict[str, str] = {}
    for feature in summary.get('source_features', []):
        try:
            uid = feature['uid']
            if uid in feature_id_by_uid:
                raise LandEvidenceValidationError('Duplicate PHI source feature UID: ' + uid)
            reference_id = 'source-feature:' + fingerprint([
                dataset_version, uid, feature['source_geometry_fingerprint'],
            ])
            reference = SourceFeatureReference(
                id=reference_id, source_reference_id=source_id,
                raw_reference_ids=[raw_id], source_feature_id=uid,
                source_global_id=feature['global_id'],
                source_object_id=feature['object_id'], source_release=feature['source_release'],
                source_geometry_fingerprint=feature['source_geometry_fingerprint'],
                source_area_ha_rounded=feature['source_area_ha_rounded'],
                parcel_intersection_area_ha=feature['intersection_area_ha'],
                parcel_intersection_fraction=feature['intersection_fraction_of_parcel'],
                main_habitats=[PriorityHabitatClassReference.model_validate(item)
                               for item in feature['main_habitats']],
                feature_qualifiers=[PriorityHabitatFeatureQualifier.model_validate(item)
                                    for item in feature['feature_qualifiers']],
                other_classification=feature.get('other_classification'),
                additional_habitat_codes=feature['additional_habitat_codes'],
                primary_source=feature.get('primary_source'),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, LandEvidenceValidationError):
                raise
            raise LandEvidenceValidationError('Malformed PHI source feature relationship') from error
        feature_references.append(reference)
        feature_id_by_uid[uid] = reference_id

    provenance = PriorityHabitatProvenance(
        source_release=source_release,
        source_schema_version=PHI_SOURCE_SCHEMA_VERSION,
        classification=PHI_CLASSIFICATION, source_url=source_url,
        source_metadata_revision_date=finding.get('source_metadata_revision_date'),
        source_capture_end_date=finding.get('source_capture_end_date'),
        source_service_data_last_edit=finding.get('source_service_data_last_edit'),
        retrieved_at=finding.get('retrieved'),
    )
    support = SpatialSupport(
        boundary_reference=boundary_reference, crs='EPSG:27700',
        support_type='feature',
        aggregation='Exact polygon intersection and spatial union in EPSG:27700',
        coverage_status='full', coverage_fraction=1,
        coverage_basis='whole_parcel_within_acquired_phi_extract',
        denominator_metadata_status='recorded',
        thematic_completeness='complete_for_declared_product',
    )

    observations: list[PriorityHabitatObservation] = []
    seen_codes: set[str] = set()
    for habitat in summary.get('habitats', []):
        try:
            code = habitat['habitat_code']
            name = habitat['habitat_name']
            if code in seen_codes or PHI_PRIORITY_HABITATS.get(code) != name:
                raise LandEvidenceValidationError('Invalid or duplicate PHI habitat code/name: ' + str(code))
            seen_codes.add(code)
            value = NumericValue(value=habitat['overlap_fraction'])
            measurement = PriorityHabitatMeasurement(
                mapped_intersection_area_ha=habitat['mapped_intersection_area_ha'],
                parcel_area_ha=habitat['parcel_area_ha'],
                overlap_fraction=habitat['overlap_fraction'],
            )
            feature_ids = [feature_id_by_uid[uid] for uid in habitat['source_feature_ids']]
        except KeyError as error:
            raise LandEvidenceValidationError('Malformed PHI habitat intersection') from error
        dimensions = {'classification': PHI_CLASSIFICATION, 'habitat_code': code}
        observations.append(PriorityHabitatObservation(
            id='observation:' + fingerprint([
                snapshot_id, 'ecology.priority_habitat.mapped_overlap_fraction',
                dimensions, source_release, feature_ids, measurement.model_dump(mode='json'),
            ]),
            definition_id='ecology.priority_habitat.mapped_overlap_fraction',
            dimensions=dimensions, mapped_habitat_name=name, value=value,
            availability='available', known_zero=value.value == 0,
            support=support.model_copy(deep=True), measurement=measurement,
            source_reference_ids=[source_id], raw_reference_ids=[raw_id],
            source_feature_reference_ids=feature_ids,
            provenance=provenance.model_copy(deep=True), limitations=PHI_LIMITATIONS,
        ))

    union = summary.get('any_main_priority_habitat')
    if not isinstance(union, dict):
        raise LandEvidenceValidationError('Covered PHI finding has no union measurement')
    try:
        union_measurement = PriorityHabitatMeasurement(
            mapped_intersection_area_ha=union['mapped_intersection_area_ha'],
            parcel_area_ha=union['parcel_area_ha'],
            overlap_fraction=union['overlap_fraction'],
        )
        union_feature_ids = [feature_id_by_uid[uid] for uid in union['source_feature_ids']]
    except KeyError as error:
        raise LandEvidenceValidationError('Malformed PHI union measurement') from error
    union_dimensions = {'classification': PHI_CLASSIFICATION}
    union_value = NumericValue(value=union_measurement.overlap_fraction)
    observations.append(PriorityHabitatObservation(
        id='observation:' + fingerprint([
            snapshot_id, 'ecology.priority_habitat.any_mapped_overlap_fraction',
            union_dimensions, source_release, union_feature_ids,
            union_measurement.model_dump(mode='json'),
        ]),
        definition_id='ecology.priority_habitat.any_mapped_overlap_fraction',
        dimensions=union_dimensions, value=union_value,
        availability='available', known_zero=union_value.value == 0,
        support=support.model_copy(deep=True), measurement=union_measurement,
        source_reference_ids=[source_id], raw_reference_ids=[raw_id],
        source_feature_reference_ids=union_feature_ids,
        provenance=provenance.model_copy(deep=True), limitations=PHI_LIMITATIONS,
    ))
    return sorted(feature_references, key=lambda item: item.id), observations


def _project_built_world(
    finding: dict[str, Any], snapshot_id: str, boundary_reference: str,
    gaps: list[EvidenceGap],
) -> tuple[list[BuiltWorldObject], list[ParcelObjectRelationship], list[BuiltWorldObservation]]:
    dataset_version = finding.get('dataset_version')
    source_release = finding.get('source_release')
    source_id = 'source:' + str(dataset_version)
    raw_id = 'raw:' + str(dataset_version)
    coverage = finding.get('coverage')
    definition_ids = [definition.id for definition in BUILT_WORLD_DEFINITIONS]
    if coverage != 'covered':
        if coverage == 'partial':
            state = 'partial_coverage'
            reason_code = 'partial_acquired_coverage'
            reason = ('Only part of the parcel is inside the acquired OpenMap Local extract; '
                      'no parcel-wide mapped object observation is asserted.')
        elif finding.get('source_failure_type') in (
                'acquisition_failure', 'processing_failure'):
            state = 'unavailable'
            reason_code = finding['source_failure_type']
            reason = (
                'The authoritative OpenMap Local acquisition failed.'
                if reason_code == 'acquisition_failure' else
                'The retained OpenMap Local source could not be processed safely.'
            )
            if finding.get('source_error'):
                reason += ' Recorded failure: ' + str(finding['source_error'])
        elif finding.get('raw_storage_reference'):
            state = 'unavailable'
            reason_code = 'outside_acquired_coverage'
            reason = 'The parcel is outside the fully acquired OpenMap Local extract.'
        else:
            state = 'unavailable'
            reason_code = 'source_unavailable'
            reason = 'The authoritative OpenMap Local source was unavailable or processing failed.'
        for definition_id in definition_ids:
            _gap(
                gaps, definition_id=definition_id, dimensions={}, legacy_variable=None,
                state=state, reason_code=reason_code,
                reason=reason + ' ' + finding.get('limitations', ''),
                source_reference_ids=[source_id], raw_reference_ids=[raw_id],
            )
        return [], [], []

    summary = finding.get('built_world')
    if not isinstance(summary, dict):
        raise LandEvidenceValidationError('Covered OpenMap Local finding has no object summary')
    if summary.get('schema_version') != OML_SOURCE_SCHEMA_VERSION:
        raise LandEvidenceValidationError('OpenMap Local source schema version is invalid')
    if summary.get('processing_version') != OML_PROCESSING_VERSION:
        raise LandEvidenceValidationError('OpenMap Local processing version is invalid')
    if summary.get('source_crs') != OML_SOURCE_CRS:
        raise LandEvidenceValidationError('OpenMap Local source CRS is invalid')
    if summary.get('rail_distance_coverage') not in ('full', 'partial'):
        raise LandEvidenceValidationError('OpenMap Local rail distance coverage is invalid')
    if not isinstance(source_release, str) or summary.get('source_release') != source_release:
        raise LandEvidenceValidationError('OpenMap Local summary release does not match source release')
    source_url = finding.get('source_url')
    if not isinstance(source_url, str) or not source_url:
        raise LandEvidenceValidationError('OpenMap Local source URL is missing')

    object_types = {
        'building': MappedBuildingObject,
        'functional_site': FunctionalSiteObject,
        'railway_track': RailwayTrackObject,
        'railway_station': RailwayStationObject,
    }
    objects: list[BuiltWorldObject] = []
    object_id_by_key: dict[str, str] = {}
    for item in summary.get('objects', []):
        try:
            source_key = item['source_object_key']
            object_type = item['object_type']
            if source_key in object_id_by_key or object_type not in object_types:
                raise LandEvidenceValidationError('Duplicate or unsupported OpenMap Local object key')
            object_id = 'object:' + fingerprint([
                snapshot_id, source_key, item['source_geometry_fingerprint'], source_release,
            ])
            payload = {
                key: value for key, value in item.items()
                if key not in ('source_object_key',)
            } | {
                'id': object_id, 'source_reference_id': source_id,
                'raw_reference_ids': [raw_id],
            }
            # Keep the in-memory representation equal to its immutable JSON
            # round-trip (Shapely mappings otherwise retain coordinate tuples).
            payload['source_geometry'] = json.loads(json.dumps(payload['source_geometry']))
            obj = object_types[object_type].model_validate(payload)
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, LandEvidenceValidationError):
                raise
            raise LandEvidenceValidationError('Malformed OpenMap Local source object') from error
        objects.append(obj)
        object_id_by_key[source_key] = object_id

    semantics = {
        'overlaps': 'Polygon interiors share positive area; neither source polygon containment nor boundary touch alone is reported as overlap.',
        'touches': 'Source geometry and parcel boundaries intersect without source geometry entering the parcel interior.',
        'contained_within': 'The immutable parcel geometry covers the complete source object geometry, including possible boundary contact.',
        'crosses': 'The source railway line passes through the parcel interior under the OGC crosses predicate.',
        'intersects': 'The source railway line intersects the parcel with positive in-parcel length but is neither covered nor classified as crossing.',
        'minimum_distance': 'Minimum planar Euclidean distance between parcel and source geometry in EPSG:27700 within the complete 5 km search.',
    }
    relationship_provenance = SpatialRelationshipProvenance(
        source_release=source_release, source_schema_version=OML_SOURCE_SCHEMA_VERSION,
        source_reference_id=source_id, raw_reference_ids=[raw_id],
    )
    relationships: list[ParcelObjectRelationship] = []
    for item in summary.get('relationships', []):
        try:
            source_key = item['source_object_key']
            predicate = item['predicate']
            object_id = object_id_by_key[source_key]
            measurements = RelationshipMeasurements.model_validate(item.get('measurements') or {})
            relationships.append(ParcelObjectRelationship(
                id='relationship:' + fingerprint([
                    snapshot_id, object_id, predicate, measurements.model_dump(mode='json'),
                    OML_PROCESSING_VERSION,
                ]),
                parcel_reference=boundary_reference, object_id=object_id,
                predicate=predicate, geometry_semantics=semantics[predicate],
                measurements=measurements,
                provenance=relationship_provenance.model_copy(deep=True),
            ))
        except (KeyError, TypeError, ValueError) as error:
            raise LandEvidenceValidationError('Malformed OpenMap Local relationship') from error

    support_by_definition = {
        definition.id: SpatialSupport(
            boundary_reference=boundary_reference, crs='EPSG:27700',
            support_type='feature',
            aggregation=definition.statistic,
            coverage_status='full', coverage_fraction=1,
            coverage_basis=definition.coverage_basis,
            denominator_metadata_status='recorded',
            thematic_completeness='complete_for_declared_product',
        )
        for definition in BUILT_WORLD_DEFINITIONS
    }
    provenance = BuiltWorldProvenance(
        source_release=source_release, source_schema_version=OML_SOURCE_SCHEMA_VERSION,
        source_url=source_url, retrieved_at=finding.get('retrieved'),
    )
    observations: list[BuiltWorldObservation] = []
    seen_definitions: set[str] = set()
    for item in summary.get('observations', []):
        try:
            definition_id = item['definition_id']
            if definition_id in seen_definitions or definition_id not in support_by_definition:
                raise LandEvidenceValidationError('Duplicate or unsupported OpenMap Local observation')
            supporting_ids = [object_id_by_key[key]
                              for key in item['supporting_source_object_keys']]
            measurement = BuiltWorldMeasurement(
                numerator=item['numerator'], denominator=item.get('denominator'),
                numerator_unit=item['numerator_unit'],
                denominator_unit=item.get('denominator_unit'),
                aggregation=item['aggregation'], supporting_object_ids=supporting_ids,
            )
            value = NumericValue(value=item['value'])
            definition = DEFINITIONS_BY_ID[definition_id]
            observations.append(BuiltWorldObservation(
                id='observation:' + fingerprint([
                    snapshot_id, definition_id, source_release, supporting_ids,
                    measurement.model_dump(mode='json'),
                ]),
                definition_id=definition_id, value=value, unit=definition.unit,
                known_zero=value.value == 0,
                support=support_by_definition[definition_id].model_copy(deep=True),
                measurement=measurement, source_reference_ids=[source_id],
                raw_reference_ids=[raw_id], supporting_object_ids=supporting_ids,
                provenance=provenance.model_copy(deep=True), limitations=OML_LIMITATIONS,
            ))
            seen_definitions.add(definition_id)
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, LandEvidenceValidationError):
                raise
            raise LandEvidenceValidationError('Malformed OpenMap Local observation') from error

    for definition_id in definition_ids:
        if definition_id in seen_definitions:
            continue
        if (definition_id.endswith('distance_min')
                and summary['rail_distance_coverage'] == 'partial'):
            state = 'partial_coverage'
            reason_code = 'partial_search_coverage'
            reason = (
                f'The acquired OpenMap Local tile does not cover the complete '
                f'{OML_SEARCH_RADIUS_M:g} m search around this parcel; no minimum '
                'distance is asserted. ' + OML_LIMITATIONS
            )
        else:
            state = 'absent_observation'
            reason_code = 'no_mapped_object_within_search_radius'
            reason = (
                f'No qualifying mapped railway object was found within the complete '
                f'{OML_SEARCH_RADIUS_M:g} m source search. No unbounded minimum distance '
                'is asserted. ' + OML_LIMITATIONS
            )
        _gap(
            gaps, definition_id=definition_id, dimensions={}, legacy_variable=None,
            state=state, reason_code=reason_code, reason=reason,
            source_reference_ids=[source_id], raw_reference_ids=[raw_id],
        )
    return (
        sorted(objects, key=lambda item: item.id),
        sorted(relationships, key=lambda item: item.id),
        sorted(observations, key=lambda item: item.id),
    )


def project_land_evidence(saved_assessment: dict[str, Any] | EarthState) -> LandEvidenceProjection:
    """Purely project a saved assessment or EarthState into ``land_evidence_v1``.

    The function performs no network, database, filesystem, acquisition or model
    calls.  A whole saved assessment is preferred because inventory-specific
    ancient-woodland zeroes live in its retained ``findings`` collection.
    """
    if isinstance(saved_assessment, EarthState):
        supplied: dict[str, Any] = saved_assessment.model_dump(mode='json')
        state_payload = supplied
        assessment_payload: dict[str, Any] = {'environmental_state': supplied}
    elif isinstance(saved_assessment, dict):
        supplied = saved_assessment
        assessment_payload = deepcopy(saved_assessment)
        state_payload = assessment_payload.get('environmental_state')
        if state_payload is None and assessment_payload.get('schema_version') == 'crc_earth_v0_1':
            state_payload = assessment_payload
            assessment_payload = {'environmental_state': state_payload}
    else:
        raise TypeError('project_land_evidence expects a saved assessment mapping or EarthState')
    if not isinstance(state_payload, dict):
        raise LandEvidenceValidationError('Saved assessment has no environmental_state payload')

    input_fingerprint = fingerprint(supplied)
    state = EarthState.model_validate(state_payload)
    if state.schema_version != 'crc_earth_v0_1':
        raise LandEvidenceValidationError('Unsupported legacy Earth schema: ' + state.schema_version)
    _validate_legacy_state(state)

    findings = assessment_payload.get('findings', [])
    if not isinstance(findings, list):
        raise LandEvidenceValidationError('Saved findings must be a list')

    phi_findings = [finding for finding in findings
                    if isinstance(finding, dict) and finding.get('key') == 'priority_habitats']
    if len(phi_findings) > 1:
        raise LandEvidenceValidationError('Saved assessment contains multiple PHI findings')
    built_findings = [finding for finding in findings
                      if isinstance(finding, dict) and finding.get('key') == 'built_world']
    if len(built_findings) > 1:
        raise LandEvidenceValidationError('Saved assessment contains multiple OpenMap Local findings')
    registry_version = (
        BUILT_WORLD_REGISTRY_VERSION if built_findings else
        PHI_REGISTRY_VERSION if phi_findings else REGISTRY_VERSION
    )
    assessment_fingerprint = fingerprint(assessment_payload)
    state_fingerprint = fingerprint(state.model_dump(mode='json'))
    # Preserve the compatibility projection scope when an unrelated native
    # family is appended. wetland_input_binding_v1 uses this identity for its
    # existing missing-value placeholders and remains unchanged.
    legacy_findings = [
        finding for finding in findings
        if not (isinstance(finding, dict)
                and finding.get('key') in ('priority_habitats', 'built_world'))
    ]
    snapshot_id = fingerprint(
        _projection_identity_seed(state, legacy_findings, REGISTRY_VERSION)
    )
    # Native families have independent scopes so adding unrelated evidence does
    # not rename existing PHI objects or observations inside the new snapshot.
    phi_scope_id = fingerprint(_projection_identity_seed(
        state,
        [finding for finding in findings
         if not (isinstance(finding, dict) and finding.get('key') == 'built_world')],
        PHI_REGISTRY_VERSION,
    ))
    built_scope_id = fingerprint(_projection_identity_seed(
        state,
        [finding for finding in findings
         if not (isinstance(finding, dict) and finding.get('key') == 'priority_habitats')],
        BUILT_WORLD_REGISTRY_VERSION,
    ))
    boundary_reference = f'{state.location_id}/boundary/{state.boundary_version}'
    identity = EvidenceSnapshotIdentity(
        projection_id='land-evidence:' + snapshot_id,
        registry_version=registry_version,
        legacy_assessment_fingerprint=assessment_fingerprint,
        legacy_state_fingerprint=state_fingerprint,
        legacy_location_id=state.location_id,
        site_name=assessment_payload.get('site_name'),
        boundary_version=state.boundary_version,
        boundary_reference=boundary_reference,
        boundary_geometry_fingerprint=fingerprint(state.geometry),
        geography=state.geography,
        evidence_as_of=state.as_of,
    )

    finding_by_version = {
        finding.get('dataset_version'): finding
        for finding in findings if isinstance(finding, dict) and finding.get('dataset_version')
    }
    raw_references: list[RawArtifactReference] = []
    source_references: list[SourceReference] = []
    for raw in state.raw:
        assets = [ArtifactAssetReference.model_validate(asset.model_dump(mode='json')) for asset in raw.assets]
        retention = ('retained_artifact' if raw.storage_reference else
                     'external_asset_only' if assets else 'reference_only')
        raw_reference_id = 'raw:' + raw.id
        raw_references.append(RawArtifactReference(
            id=raw_reference_id, legacy_raw_id=raw.id, retention_status=retention,
            storage_reference=raw.storage_reference, checksum=raw.checksum,
            assets=assets, original_semantics=raw.raw_semantics,
        ))
        finding = finding_by_version.get(raw.id, {})
        attribution = finding.get('attribution') if isinstance(finding, dict) else None
        licence = finding.get('licence') if isinstance(finding, dict) else None
        licence_or_attribution = ' | '.join(value for value in (licence, attribution) if value) or None
        source_references.append(SourceReference(
            id='source:' + raw.id, provider=raw.source, dataset=raw.source_dataset,
            source_version=raw.source_version, source_url=raw.source_url,
            reference_period=_temporal(raw.timestamp), retrieved_at=raw.retrieved_at,
            raw_reference_ids=[raw_reference_id],
            licence_or_attribution=licence_or_attribution,
            licence_metadata_status='recorded_legacy' if licence_or_attribution else 'not_recorded_legacy',
        ))

    diagnostics: list[Diagnostic] = []
    gaps: list[EvidenceGap] = []
    projected: list[LandObservation] = []
    source_feature_references: list[SourceFeatureReference] = []
    native_projected: list[PriorityHabitatObservation] = []
    built_objects: list[BuiltWorldObject] = []
    built_relationships: list[ParcelObjectRelationship] = []
    built_projected: list[BuiltWorldObservation] = []
    legacy_to_projected: dict[str, list[str]] = defaultdict(list)
    distribution_by_source: dict[tuple[str, tuple[str, ...]], str] = {}

    if phi_findings:
        finding = phi_findings[0]
        dataset_version = finding.get('dataset_version')
        # PHI intentionally never enters the legacy EarthState consumed by the
        # wetland module.  Build its native raw and source references directly
        # from the retained finding when projecting a new assessment.  Older
        # transitional payloads that did include the raw entry still follow the
        # loop above and are accepted without duplication.
        if 'raw:' + str(dataset_version) not in {raw.id for raw in raw_references}:
            storage_reference = finding.get('raw_storage_reference')
            raw_reference_id = 'raw:' + str(dataset_version)
            raw_references.append(RawArtifactReference(
                id=raw_reference_id,
                legacy_raw_id=str(dataset_version),
                retention_status='retained_artifact' if storage_reference else 'reference_only',
                storage_reference=storage_reference,
                checksum=finding.get('raw_sha256'),
                assets=[],
                original_semantics=finding.get('raw_semantics') or (
                    'Native PHI source acquisition reference retained by Land Evidence.'
                ),
            ))
            licence_or_attribution = ' | '.join(
                value for value in (finding.get('licence'), finding.get('attribution'))
                if value
            ) or None
            try:
                source_references.append(SourceReference(
                    id='source:' + str(dataset_version),
                    provider=finding.get('publisher') or 'Natural England',
                    dataset=finding.get('dataset') or 'Priority Habitats Inventory (England)',
                    source_version=finding.get('source_release') or str(dataset_version),
                    source_url=finding.get('source_url'),
                    reference_period=_temporal(None),
                    retrieved_at=finding.get('retrieved'),
                    raw_reference_ids=[raw_reference_id],
                    licence_or_attribution=licence_or_attribution,
                    licence_metadata_status=(
                        'recorded_legacy' if licence_or_attribution else 'not_recorded_legacy'
                    ),
                ))
            except (TypeError, ValueError) as error:
                raise LandEvidenceValidationError(
                    'PHI finding has incomplete native source provenance'
                ) from error
        if 'raw:' + str(dataset_version) not in {raw.id for raw in raw_references}:
            raise LandEvidenceValidationError('PHI finding has no matching raw evidence reference')
        matching_source = next(
            (source for source in source_references
             if source.id == 'source:' + str(dataset_version)), None
        )
        if matching_source is None or matching_source.provider != 'Natural England':
            raise LandEvidenceValidationError('PHI finding has no matching Natural England source reference')
        if matching_source.source_version != finding.get('source_release'):
            raise LandEvidenceValidationError('PHI raw source release does not match finding release')
        source_feature_references, native_projected = _project_priority_habitats(
            finding, phi_scope_id, boundary_reference, gaps,
        )

    if built_findings:
        finding = built_findings[0]
        dataset_version = finding.get('dataset_version')
        raw_reference_id = 'raw:' + str(dataset_version)
        if raw_reference_id not in {raw.id for raw in raw_references}:
            storage_reference = finding.get('raw_storage_reference')
            raw_references.append(RawArtifactReference(
                id=raw_reference_id, legacy_raw_id=str(dataset_version),
                retention_status='retained_artifact' if storage_reference else 'reference_only',
                storage_reference=storage_reference, checksum=finding.get('raw_sha256'),
                assets=[], original_semantics=finding.get('raw_semantics') or (
                    'Original official OS OpenMap Local archive acquisition reference.'
                ),
            ))
            licence_or_attribution = ' | '.join(
                value for value in (finding.get('licence'), finding.get('attribution'))
                if value
            ) or None
            try:
                source_references.append(SourceReference(
                    id='source:' + str(dataset_version), provider='Ordnance Survey',
                    dataset=finding.get('dataset') or 'OS OpenMap - Local',
                    source_version=finding.get('source_release'),
                    source_url=finding.get('source_url'), reference_period=_temporal(None),
                    retrieved_at=finding.get('retrieved'),
                    raw_reference_ids=[raw_reference_id],
                    licence_or_attribution=licence_or_attribution,
                    licence_metadata_status=(
                        'recorded_legacy' if licence_or_attribution else 'not_recorded_legacy'
                    ),
                ))
            except (TypeError, ValueError) as error:
                raise LandEvidenceValidationError(
                    'OpenMap Local finding has incomplete native source provenance'
                ) from error
        matching_source = next(
            (source for source in source_references
             if source.id == 'source:' + str(dataset_version)), None
        )
        if matching_source is None or matching_source.provider != 'Ordnance Survey':
            raise LandEvidenceValidationError(
                'OpenMap Local finding has no matching Ordnance Survey source reference'
            )
        if matching_source.source_version != finding.get('source_release'):
            raise LandEvidenceValidationError(
                'OpenMap Local raw source release does not match finding release'
            )
        built_objects, built_relationships, built_projected = _project_built_world(
            finding, built_scope_id, boundary_reference, gaps,
        )

    for variable, (definition_id, dimensions) in LEGACY_CORE_MAPPINGS.items():
        domain, name = variable.split('.', 1)
        candidates = state.normalized.get(domain, {}).get(name, [])
        if not candidates:
            _gap(gaps, definition_id=definition_id, dimensions=dimensions,
                 legacy_variable=variable, state='absent_observation',
                 reason_code='absent_observation', reason='No legacy observation was saved for this registered source-backed concept.')
            if variable == 'land_use.current_cover':
                _gap(gaps, definition_id='ecology.land_cover.class_distribution',
                     dimensions={'classification': WORLD_COVER_CLASSIFICATION},
                     legacy_variable=variable, state='absent_observation',
                     reason_code='absent_observation', reason='No legacy WorldCover method record was saved for distribution extraction.')
            continue
        for legacy in candidates:
            source_ids, raw_ids = _raw_ids(legacy)
            if legacy.value is None:
                gap_state, reason_code = _classify_unavailable(legacy.missing_reason or 'Legacy observation unavailable.')
                _gap(gaps, definition_id=definition_id, dimensions=dimensions,
                     legacy_variable=variable, state=gap_state, reason_code=reason_code,
                     reason=legacy.missing_reason or 'Legacy observation unavailable.',
                     source_reference_ids=source_ids, raw_reference_ids=raw_ids)
                if variable == 'land_use.current_cover':
                    _gap(gaps, definition_id='ecology.land_cover.class_distribution',
                         dimensions={'classification': WORLD_COVER_CLASSIFICATION},
                         legacy_variable=variable, state=gap_state, reason_code=reason_code,
                         reason=legacy.missing_reason or 'Legacy WorldCover observation unavailable.',
                         source_reference_ids=source_ids, raw_reference_ids=raw_ids)
                continue
            definition = DEFINITIONS_BY_ID[definition_id]
            typed = _typed_legacy_value(legacy, definition)
            if typed is None:
                message = f'Legacy value for {variable} is invalid for {definition_id}: {legacy.value!r}'
                _diagnostic(diagnostics, 'error', 'invalid_category' if definition.value_kind in ('category', 'boolean') else 'invalid_value', message, [legacy.id])
                _gap(gaps, definition_id=definition_id, dimensions=dimensions,
                     legacy_variable=variable, state='unavailable',
                     reason_code='category_uninterpretable' if definition.value_kind in ('category', 'boolean') else 'value_uninterpretable',
                     reason=message, source_reference_ids=source_ids, raw_reference_ids=raw_ids)
            else:
                support = _support(legacy, definition_id)
                path = _legacy_path(state, legacy)
                observation = LandObservation(
                    id=_observation_id(snapshot_id, definition_id, dimensions, legacy.id, path),
                    definition_id=definition_id, dimensions=dimensions, value=typed,
                    unit=definition.unit, availability=_availability(support),
                    known_zero=_known_zero(typed), support=support,
                    source_reference_ids=source_ids, raw_reference_ids=raw_ids,
                    provenance=_provenance(state, legacy), limitations=legacy.uncertainty,
                )
                projected.append(observation)
                legacy_to_projected[legacy.id].append(observation.id)

            if variable == 'land_use.current_cover':
                distribution = _extract_worldcover_distribution(
                    state, legacy, snapshot_id, diagnostics, gaps,
                )
                if distribution is not None:
                    projected.append(distribution)
                    legacy_to_projected[legacy.id].insert(0, distribution.id)
                    distribution_by_source[(legacy.source_version, tuple(legacy.raw_source_ids))] = distribution.id

    # The legacy adapter deliberately converted covered zeroes in each ancient-
    # woodland inventory to a broad unknown.  Recover only the exact retained
    # finding fraction and keep each inventory as a distinct semantic dimension.
    ancient_candidates = state.normalized.get('ecology', {}).get('irreplaceable_habitat_fraction', [])
    ancient_by_version = {candidate.source_version: candidate for candidate in ancient_candidates}
    ancient_seen: set[str] = set()
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict) or finding.get('key') not in ('woodland', 'woodland_revised'):
            continue
        inventory = 'legacy' if finding['key'] == 'woodland' else 'revised'
        ancient_seen.add(inventory)
        dimensions = {'inventory': inventory}
        legacy = ancient_by_version.get(finding.get('dataset_version'))
        if legacy is None:
            raise LandEvidenceValidationError(
                f'Ancient-woodland finding {finding.get("dataset_version")} has no matching legacy observation'
            )
        source_ids, raw_ids = _raw_ids(legacy)
        if finding.get('coverage') != 'covered':
            _gap(gaps, definition_id='ecology.ancient_woodland.mapped_overlap_fraction',
                 dimensions=dimensions, legacy_variable='ecology.irreplaceable_habitat_fraction',
                 state='unavailable', reason_code='outside_acquired_extent',
                 reason=legacy.missing_reason or 'Ancient-woodland inventory did not cover the whole parcel.',
                 source_reference_ids=source_ids, raw_reference_ids=raw_ids)
            continue
        value = finding.get('fraction')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            message = f'Covered ancient-woodland finding has no valid stored fraction for {inventory} inventory.'
            _diagnostic(diagnostics, 'error', 'ancient_woodland_fraction_malformed', message, [legacy.id])
            _gap(gaps, definition_id='ecology.ancient_woodland.mapped_overlap_fraction',
                 dimensions=dimensions, legacy_variable='ecology.irreplaceable_habitat_fraction',
                 state='unavailable', reason_code='value_uninterpretable', reason=message,
                 source_reference_ids=source_ids, raw_reference_ids=raw_ids)
            continue
        definition_id = 'ecology.ancient_woodland.mapped_overlap_fraction'
        typed = NumericValue(value=value)
        support = _support(legacy, definition_id, coverage_fraction=1, thematic_completeness='partial_inventory')
        path = f'findings[{index}].fraction'
        observation = LandObservation(
            id=_observation_id(snapshot_id, definition_id, dimensions, legacy.id, path),
            definition_id=definition_id, dimensions=dimensions, value=typed, unit='fraction',
            availability='available', known_zero=_known_zero(typed), support=support,
            source_reference_ids=source_ids, raw_reference_ids=raw_ids,
            provenance=_provenance(state, legacy, legacy_value=value, legacy_value_path=path),
            limitations=finding.get('limitations') or legacy.uncertainty,
        )
        projected.append(observation)
        legacy_to_projected[legacy.id].append(observation.id)

    # EarthState-only callers cannot recover covered inventory zeroes because the
    # old adapter deliberately replaced them with broad unknowns.  A positive
    # candidate value is still an exact inventory-scoped fact, so retain it; make
    # the unrecoverable zero/unknown distinction explicit for null candidates.
    for legacy in ancient_candidates:
        inventory = (
            'legacy' if legacy.source_dataset == 'Ancient woodland · legacy inventory' else
            'revised' if legacy.source_dataset == 'Ancient woodland · revised inventory' else
            None
        )
        if inventory is None or inventory in ancient_seen:
            continue
        ancient_seen.add(inventory)
        dimensions = {'inventory': inventory}
        source_ids, raw_ids = _raw_ids(legacy)
        definition_id = 'ecology.ancient_woodland.mapped_overlap_fraction'
        if legacy.value is None:
            _gap(
                gaps, definition_id=definition_id, dimensions=dimensions,
                legacy_variable='ecology.irreplaceable_habitat_fraction',
                state='incomplete_inventory', reason_code='legacy_finding_required',
                reason=(f'The {inventory} inventory legacy observation is null. The retained finding is required '
                        'to distinguish covered mapped zero from unavailable evidence.'),
                source_reference_ids=source_ids, raw_reference_ids=raw_ids,
            )
            continue
        typed = NumericValue(value=legacy.value)
        support = _support(legacy, definition_id, thematic_completeness='partial_inventory')
        path = _legacy_path(state, legacy)
        observation = LandObservation(
            id=_observation_id(snapshot_id, definition_id, dimensions, legacy.id, path),
            definition_id=definition_id, dimensions=dimensions, value=typed, unit='fraction',
            availability=_availability(support), known_zero=_known_zero(typed), support=support,
            source_reference_ids=source_ids, raw_reference_ids=raw_ids,
            provenance=_provenance(state, legacy), limitations=legacy.uncertainty,
        )
        projected.append(observation)
        legacy_to_projected[legacy.id].append(observation.id)

    for inventory in ('legacy', 'revised'):
        if inventory not in ancient_seen:
            _gap(gaps, definition_id='ecology.ancient_woodland.mapped_overlap_fraction',
                 dimensions={'inventory': inventory}, legacy_variable='ecology.irreplaceable_habitat_fraction',
                 state='absent_observation', reason_code='absent_legacy_finding',
                 reason=f'No retained {inventory} ancient-woodland finding was saved; no inventory fact was manufactured.')

    _gap(gaps, definition_id=None, dimensions={},
         legacy_variable='ecology.irreplaceable_habitat_fraction', state='incomplete_inventory',
         reason_code='incomplete_inventory',
         reason=('Inventory-specific ancient-woodland evidence is retained separately. It does not establish '
                 'a complete or broad irreplaceable-habitat fraction.'))

    for variable, (concept, default_reason) in EXPLICIT_GAPS.items():
        legacy = state.get(variable)
        reason = legacy.missing_reason if legacy is not None and legacy.value is None else default_reason
        source_ids, raw_ids = _raw_ids(legacy) if legacy is not None else ([], [])
        if legacy is not None and legacy.value is not None:
            _diagnostic(
                diagnostics, 'warning', 'out_of_scope_connected_gap_value',
                f'{variable} contains a value in this saved record but land_evidence_v1 does not define a production mapping for it.',
                [legacy.id],
            )
            continue
        _gap(gaps, definition_id=concept, dimensions={}, legacy_variable=variable,
             state='source_not_connected', reason_code='source_unconnected',
             reason=reason or default_reason,
             source_reference_ids=source_ids, raw_reference_ids=raw_ids)

    # Attach projected core parents.  WorldCover scalar views additionally point
    # to the extracted distribution from which the legacy method says they came.
    legacy_by_id = {observation.id: observation for observation in _observations(state)}
    updated: list[LandObservation] = []
    for observation in projected:
        legacy = legacy_by_id[observation.provenance.legacy_observation_id]
        parents: list[str] = []
        for legacy_parent in legacy.input_ids:
            if legacy_by_id[legacy_parent].variable in LEGACY_MODULE_OUTPUTS:
                raise LandEvidenceValidationError('Wetland/module interpretation cannot be a core observation parent')
            candidates = legacy_to_projected.get(legacy_parent, [])
            if not candidates:
                raise LandEvidenceValidationError(
                    f'Core observation parent {legacy_parent} has no projected core representation'
                )
            parents.append(candidates[0])
        if observation.definition_id in {
            'ecology.land_cover.dominant_class', 'built.mapped_built_up_fraction',
            'ecology.mapped_herbaceous_wetland_fraction', 'physical.mapped_permanent_water_fraction',
        }:
            distribution_id = distribution_by_source.get((legacy.source_version, tuple(legacy.raw_source_ids)))
            if distribution_id:
                parents.insert(0, distribution_id)
        updated.append(observation.model_copy(update={
            'parent_observation_ids': list(dict.fromkeys(parents))
        }))
    projected = updated
    projected.extend(native_projected)  # type: ignore[arg-type]
    projected.extend(built_projected)  # type: ignore[arg-type]

    groups: dict[str, list[LandObservation]] = defaultdict(list)
    for observation in projected:
        groups[_semantic_key(observation.definition_id, observation.dimensions)].append(observation)
    selections: list[EvidenceSelection] = []
    for semantic_key, candidates in sorted(groups.items()):
        legacy_selected = [
            candidate for candidate in candidates
            if isinstance(candidate, LandObservation)
            and state.selected.get(candidate.provenance.legacy_variable) == candidate.provenance.legacy_observation_id
        ]
        if legacy_selected:
            chosen = sorted(legacy_selected, key=lambda item: item.id)[0]
            policy: Literal['legacy_selection', 'only_candidate', 'source_scoped_dimension'] = 'legacy_selection'
        elif len(candidates) == 1:
            chosen = candidates[0]
            policy = ('source_scoped_dimension'
                      if chosen.definition_id in {
                          'ecology.ancient_woodland.mapped_overlap_fraction',
                          'ecology.priority_habitat.mapped_overlap_fraction',
                      }
                      else 'only_candidate')
        else:
            chosen = sorted(candidates, key=lambda item: item.id)[0]
            policy = 'source_scoped_dimension'
            _diagnostic(
                diagnostics, 'warning', 'legacy_selection_unavailable',
                f'No available legacy-selected candidate for {semantic_key}; deterministic first candidate referenced.',
                [candidate.id for candidate in candidates],
            )
        selections.append(EvidenceSelection(
            semantic_key=semantic_key, observation_id=chosen.id, policy=policy,
        ))

    unrecorded_periods = [source.id for source in source_references if source.reference_period.status == 'not_recorded_legacy']
    if unrecorded_periods:
        _diagnostic(
            diagnostics, 'info', 'legacy_reference_period_unrecorded',
            'One or more source reference periods were not recorded historically; retrieval times were not substituted.',
            unrecorded_periods,
        )
    _diagnostic(
        diagnostics, 'info', 'legacy_support_denominators_unrecorded',
        'Legacy observations retain coverage fractions, but exact cell/area numerator and denominator quantities were not stored in EarthState.',
        [observation.id for observation in projected],
    )

    module_outputs = [
        LegacyModuleOutputReference(
            legacy_observation_id=observation.id, variable=variable,
            value=observation.value, unit=observation.unit,
            source_version=observation.source_version,
            parent_legacy_observation_ids=observation.input_ids,
        )
        for variable, observation in sorted(state.derived.items())
        if variable in LEGACY_MODULE_OUTPUTS
    ]
    wetland = assessment_payload.get('wetland_model')
    wetland_reference = None
    if isinstance(wetland, dict):
        wetland_reference = LegacyWetlandResultReference(
            payload_fingerprint=fingerprint(wetland),
            model_version=wetland.get('model_version'),
            model_signature=wetland.get('signature'),
            state_fingerprint=wetland.get('state_fingerprint'),
        )

    projection = LandEvidenceProjection(
        identity=identity,
        definitions=[definition.model_copy(deep=True)
                     for definition in DEFINITIONS_BY_REGISTRY[registry_version]],
        raw_references=raw_references,
        source_references=source_references,
        source_feature_references=source_feature_references,
        objects=built_objects,
        relationships=built_relationships,
        observations=sorted(projected, key=lambda item: item.id),
        selections=selections,
        gaps=sorted(gaps, key=lambda item: item.id),
        capabilities=_capabilities(),
        diagnostics=sorted(diagnostics, key=lambda item: item.id),
        legacy_module_outputs=module_outputs,
        legacy_wetland_result=wetland_reference,
    )
    validate_land_evidence(projection)
    if isinstance(saved_assessment, dict) and fingerprint(saved_assessment) != input_fingerprint:
        raise RuntimeError('Pure projection invariant failed: supplied assessment was modified')
    return projection


def validate_land_evidence(
    value: LandEvidenceProjection | dict[str, Any],
) -> LandEvidenceProjection:
    """Validate semantic, reference and lineage invariants for a projection."""
    projection = value if isinstance(value, LandEvidenceProjection) else LandEvidenceProjection.model_validate(value)
    errors: list[str] = []
    definitions = {definition.id: definition for definition in projection.definitions}
    if len(definitions) != len(projection.definitions):
        errors.append('Duplicate observation definition IDs')
    expected_registry = DEFINITIONS_BY_REGISTRY.get(projection.identity.registry_version)
    if expected_registry is None:
        errors.append('Unsupported Land Evidence registry version')
        expected_registry = []
    expected_definitions = {
        definition.id: definition.model_dump(mode='json') for definition in expected_registry
    }
    actual_definitions = {
        definition.id: definition.model_dump(mode='json') for definition in projection.definitions
    }
    if actual_definitions != expected_definitions:
        errors.append('Projection definitions do not match the immutable land_evidence_v1 registry')

    def unique(records: list[Any], label: str) -> set[str]:
        ids = [record.id for record in records]
        duplicates = sorted({record_id for record_id in ids if ids.count(record_id) > 1})
        if duplicates:
            errors.append(f'Duplicate {label} IDs: ' + ', '.join(duplicates))
        return set(ids)

    observation_ids = unique(projection.observations, 'observation')
    raw_ids = unique(projection.raw_references, 'raw reference')
    source_ids = unique(projection.source_references, 'source reference')
    source_feature_ids = unique(projection.source_feature_references, 'source feature reference')
    object_ids = unique(projection.objects, 'object')
    relationship_ids = unique(projection.relationships, 'relationship')
    gap_ids = unique(projection.gaps, 'gap')
    diagnostic_ids = unique(projection.diagnostics, 'diagnostic')
    scoped_groups = {
        'observation': observation_ids, 'raw': raw_ids, 'source': source_ids,
        'source feature': source_feature_ids,
        'object': object_ids, 'relationship': relationship_ids,
        'gap': gap_ids, 'diagnostic': diagnostic_ids,
    }
    scoped_names = list(scoped_groups)
    for index, left in enumerate(scoped_names):
        for right in scoped_names[index + 1:]:
            overlap = scoped_groups[left] & scoped_groups[right]
            if overlap:
                errors.append(f'IDs are not globally scoped between {left} and {right}: {sorted(overlap)}')
    source_by_id = {source.id: source for source in projection.source_references}
    source_feature_by_id = {feature.id: feature for feature in projection.source_feature_references}
    object_by_id = {item.id: item for item in projection.objects}
    observation_by_id = {observation.id: observation for observation in projection.observations}

    for source in projection.source_references:
        missing = set(source.raw_reference_ids) - raw_ids
        if missing:
            errors.append(f'Source {source.id} has dangling raw references: {sorted(missing)}')

    for feature in projection.source_feature_references:
        if feature.source_reference_id not in source_ids:
            errors.append(f'Source feature {feature.id} has a dangling source reference')
        if set(feature.raw_reference_ids) - raw_ids or not feature.raw_reference_ids:
            errors.append(f'Source feature {feature.id} has dangling raw references')
        source = source_by_id.get(feature.source_reference_id)
        if source and feature.source_release != source.source_version:
            errors.append(f'Source feature release does not match source reference: {feature.id}')
        for habitat in feature.main_habitats:
            expected_name = PHI_MAIN_CLASSES.get(habitat.code)
            expected_status = ('priority' if habitat.code in PHI_PRIORITY_HABITATS
                               else 'supporting_non_priority')
            if habitat.name != expected_name or habitat.status != expected_status:
                errors.append(f'Invalid PHI feature habitat code/name/status: {feature.id}')
        if set(feature.additional_habitat_codes) - set(PHI_MAIN_CLASSES):
            errors.append(f'Invalid PHI additional habitat code: {feature.id}')

    expected_geometry_types = {
        'building': {'Polygon', 'MultiPolygon'},
        'functional_site': {'Polygon', 'MultiPolygon'},
        'railway_track': {'LineString', 'MultiLineString'},
        'railway_station': {'Point'},
    }
    for obj in projection.objects:
        if obj.source_reference_id not in source_ids:
            errors.append(f'Object {obj.id} has a dangling source reference')
        if not obj.raw_reference_ids or set(obj.raw_reference_ids) - raw_ids:
            errors.append(f'Object {obj.id} has dangling raw references')
        source = source_by_id.get(obj.source_reference_id)
        if (source and (source.provider != 'Ordnance Survey'
                        or source.source_version != obj.source_release)):
            errors.append(f'Object source/release does not resolve: {obj.id}')
        try:
            validate_oml_properties(obj.object_type, obj.model_dump(mode='python'))
            geometry = shapely_shape(obj.source_geometry)
            if geometry.is_empty or geometry.geom_type not in expected_geometry_types[obj.object_type]:
                errors.append(f'Object geometry type is invalid: {obj.id}')
            if fingerprint(obj.source_geometry) != obj.source_geometry_fingerprint:
                errors.append(f'Object geometry fingerprint mismatch: {obj.id}')
        except (TypeError, ValueError):
            errors.append(f'Object attributes are invalid: {obj.id}')

    for relationship in projection.relationships:
        obj = object_by_id.get(relationship.object_id)
        if obj is None:
            errors.append(f'Relationship has a dangling object: {relationship.id}')
            continue
        if relationship.parcel_reference != projection.identity.boundary_reference:
            errors.append(f'Relationship parcel support mismatch: {relationship.id}')
        provenance = relationship.provenance
        if (provenance.source_reference_id != obj.source_reference_id
                or provenance.source_release != obj.source_release
                or set(provenance.raw_reference_ids) != set(obj.raw_reference_ids)
                or provenance.source_schema_version != OML_SOURCE_SCHEMA_VERSION):
            errors.append(f'Relationship provenance does not resolve through object: {relationship.id}')
        measurement = relationship.measurements
        values = measurement.model_dump()
        if relationship.predicate == 'minimum_distance':
            if (obj.object_type not in ('railway_track', 'railway_station')
                    or measurement.minimum_distance_m is None
                    or any(value is not None for key, value in values.items()
                           if key != 'minimum_distance_m')):
                errors.append(f'Invalid minimum-distance relationship metrics: {relationship.id}')
        elif obj.object_type in ('building', 'functional_site'):
            if (relationship.predicate in ('overlaps', 'contained_within')
                    and (measurement.overlap_area_m2 is None
                         or measurement.parcel_overlap_fraction is None
                         or measurement.object_overlap_fraction is None)):
                errors.append(f'Polygon relationship lacks overlap metrics: {relationship.id}')
            if relationship.predicate == 'touches' and any(
                    value is not None for value in values.values()):
                errors.append(f'Polygon touch has area/distance metrics: {relationship.id}')
        elif obj.object_type == 'railway_track':
            if (relationship.predicate in ('crosses', 'intersects', 'contained_within')
                    and (measurement.length_within_m is None
                         or measurement.length_within_m <= 0)):
                errors.append(f'Rail relationship lacks positive in-parcel length: {relationship.id}')
        elif obj.object_type == 'railway_station' and any(
                value is not None for value in values.values()):
            errors.append(f'Station topological relationship carries fictional metrics: {relationship.id}')

    for observation in projection.observations:
        definition = definitions.get(observation.definition_id)
        if definition is None:
            errors.append(f'Definition does not resolve for {observation.id}: {observation.definition_id}')
            continue
        if observation.value.kind != definition.value_kind:
            errors.append(f'Value kind mismatch for {observation.id}')
        if observation.unit != definition.unit:
            errors.append(f'Unit mismatch for {observation.id}: {observation.unit} != {definition.unit}')
        required_dimensions = {dimension.name: dimension for dimension in definition.dimensions}
        if set(observation.dimensions) != set(required_dimensions):
            errors.append(f'Dimension mismatch for {observation.id}')
        else:
            for name, dimension in required_dimensions.items():
                if observation.dimensions[name] not in dimension.allowed_values:
                    errors.append(f'Invalid dimension {name} for {observation.id}')
        if isinstance(observation.value, CategoryValue) and observation.value.value not in definition.allowed_categories:
            errors.append(f'Invalid category for {observation.id}: {observation.value.value}')
        if isinstance(observation.value, NumericValue):
            if definition.minimum is not None and observation.value.value < definition.minimum:
                errors.append(f'Numeric value below definition minimum for {observation.id}')
            if definition.maximum is not None and observation.value.value > definition.maximum:
                errors.append(f'Numeric value above definition maximum for {observation.id}')
        if isinstance(observation.value, DistributionValue):
            codes = [entry.code for entry in observation.value.entries]
            categories = [entry.category for entry in observation.value.entries]
            if codes != list(WORLD_COVER_CLASSES) or categories != list(WORLD_COVER_CLASSES.values()):
                errors.append(f'Invalid distribution vocabulary or ordering for {observation.id}')
            if not math.isclose(sum(entry.value for entry in observation.value.entries), 1, rel_tol=0, abs_tol=1e-12):
                errors.append(f'Distribution does not sum to one for {observation.id}')
        expected_zero = isinstance(observation.value, NumericValue) and observation.value.value == 0
        if observation.known_zero != expected_zero:
            errors.append(f'Known-zero state does not match value for {observation.id}')
        if observation.support.coverage_fraction == 0:
            errors.append(f'Non-null observation has zero coverage: {observation.id}')
        if observation.availability == 'partial' and observation.support.coverage_status != 'partial':
            errors.append(f'Partial availability lacks partial support for {observation.id}')
        if observation.availability == 'available' and observation.support.coverage_status == 'partial':
            errors.append(f'Available observation masks partial support for {observation.id}')
        if observation.support.coverage_basis != definition.coverage_basis:
            errors.append(f'Coverage basis mismatch for {observation.id}')
        if observation.support.boundary_reference != projection.identity.boundary_reference:
            errors.append(f'Boundary support mismatch for {observation.id}')
        missing_sources = set(observation.source_reference_ids) - source_ids
        missing_raw = set(observation.raw_reference_ids) - raw_ids
        missing_parents = set(observation.parent_observation_ids) - observation_ids
        if not observation.source_reference_ids or missing_sources:
            errors.append(f'Unresolved source references for {observation.id}: {sorted(missing_sources)}')
        if not observation.raw_reference_ids or missing_raw:
            errors.append(f'Unresolved raw references for {observation.id}: {sorted(missing_raw)}')
        if missing_parents:
            errors.append(f'Unresolved parent observations for {observation.id}: {sorted(missing_parents)}')
        for source_id in observation.source_reference_ids:
            source = source_by_id.get(source_id)
            if source and not set(source.raw_reference_ids) <= set(observation.raw_reference_ids):
                errors.append(f'Observation {observation.id} omits raw reference resolved by {source_id}')
        resolved_sources = [source_by_id[source_id] for source_id in observation.source_reference_ids if source_id in source_by_id]
        provenance_version = (
            observation.provenance.source_release
            if isinstance(observation, (PriorityHabitatObservation, BuiltWorldObservation))
            else observation.provenance.source_version
        )
        if resolved_sources and not any(
            source.provider == observation.provenance.provider
            and source.source_version == provenance_version
            for source in resolved_sources
        ):
            errors.append(f'Observation source/provider version does not resolve for {observation.id}')
        if isinstance(observation, LandObservation) and observation.provenance.legacy_variable in LEGACY_MODULE_OUTPUTS:
            errors.append(f'Wetland/module interpretation leaked into core: {observation.id}')
        if isinstance(observation, PriorityHabitatObservation):
            missing_features = set(observation.source_feature_reference_ids) - source_feature_ids
            if missing_features:
                errors.append(f'Unresolved source feature references for {observation.id}: {sorted(missing_features)}')
            measurement = observation.measurement
            if observation.value.value != measurement.overlap_fraction:
                errors.append(f'PHI value disagrees with measurement for {observation.id}')
            calculated = measurement.mapped_intersection_area_ha / measurement.parcel_area_ha
            if not math.isclose(calculated, measurement.overlap_fraction,
                                rel_tol=0, abs_tol=1e-12):
                errors.append(f'PHI numerator/denominator disagree for {observation.id}')
            if observation.provenance.classification != PHI_CLASSIFICATION:
                errors.append(f'PHI provenance classification mismatch for {observation.id}')
            if observation.provenance.source_schema_version != PHI_SOURCE_SCHEMA_VERSION:
                errors.append(f'PHI provenance schema mismatch for {observation.id}')
            if observation.definition_id == 'ecology.priority_habitat.mapped_overlap_fraction':
                code = observation.dimensions.get('habitat_code')
                if PHI_PRIORITY_HABITATS.get(code) != observation.mapped_habitat_name:
                    errors.append(f'PHI observation code/name mismatch for {observation.id}')
                if not observation.source_feature_reference_ids:
                    errors.append(f'Positive habitat observation has no feature lineage: {observation.id}')
            elif observation.definition_id == 'ecology.priority_habitat.any_mapped_overlap_fraction':
                if observation.mapped_habitat_name is not None:
                    errors.append(f'PHI union observation must not claim one habitat name: {observation.id}')
                if observation.known_zero and observation.source_feature_reference_ids:
                    errors.append(f'PHI mapped-zero union has priority feature lineage: {observation.id}')
        if isinstance(observation, BuiltWorldObservation):
            missing_objects = set(observation.supporting_object_ids) - object_ids
            if missing_objects:
                errors.append(f'Unresolved supporting objects for {observation.id}: {sorted(missing_objects)}')
            measurement = observation.measurement
            if observation.supporting_object_ids != measurement.supporting_object_ids:
                errors.append(f'Built-world observation object lineage mismatch: {observation.id}')
            if measurement.denominator is not None:
                calculated = measurement.numerator / measurement.denominator
            else:
                calculated = measurement.numerator
            if not math.isclose(calculated, observation.value.value, rel_tol=0, abs_tol=1e-12):
                errors.append(f'Built-world numerator/denominator disagree for {observation.id}')
            if observation.provenance.source_schema_version != OML_SOURCE_SCHEMA_VERSION:
                errors.append(f'Built-world provenance schema mismatch for {observation.id}')
            supporting_types = {
                object_by_id[object_id].object_type
                for object_id in observation.supporting_object_ids if object_id in object_by_id
            }
            expected_type = {
                'built.building.mapped_overlap_fraction': 'building',
                'built.functional_site.mapped_overlap_fraction': 'functional_site',
                'transport.railway_track.mapped_length_within': 'railway_track',
                'transport.railway_track.distance_min': 'railway_track',
                'transport.railway_station.distance_min': 'railway_station',
            }.get(observation.definition_id)
            if expected_type is None or supporting_types - {expected_type}:
                errors.append(f'Built-world observation has wrong object type support: {observation.id}')
            if (observation.definition_id.endswith('mapped_overlap_fraction')
                    and (measurement.numerator_unit != 'm2'
                         or measurement.denominator_unit != 'm2'
                         or measurement.denominator is None)):
                errors.append(f'Built-world overlap measurement units are invalid: {observation.id}')
            if not observation.supporting_object_ids and not observation.known_zero:
                errors.append(f'Positive built-world observation lacks object support: {observation.id}')

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(observation_id: str, path: list[str]) -> None:
        if observation_id in visiting:
            start = path.index(observation_id)
            errors.append('Cyclic projection lineage: ' + ' -> '.join(path[start:] + [observation_id]))
            return
        if observation_id in visited:
            return
        visiting.add(observation_id)
        path.append(observation_id)
        for parent in observation_by_id[observation_id].parent_observation_ids:
            if parent in observation_by_id:
                visit(parent, path)
        path.pop()
        visiting.remove(observation_id)
        visited.add(observation_id)

    for observation_id in observation_ids:
        visit(observation_id, [])

    selection_keys: set[str] = set()
    for selection in projection.selections:
        if selection.semantic_key in selection_keys:
            errors.append('Duplicate semantic selection: ' + selection.semantic_key)
        selection_keys.add(selection.semantic_key)
        selected = observation_by_id.get(selection.observation_id)
        if selected is None:
            errors.append('Selected observation does not resolve: ' + selection.observation_id)
        elif selection.semantic_key != _semantic_key(selected.definition_id, selected.dimensions):
            errors.append('Selected observation does not match semantic key: ' + selection.semantic_key)

    for gap in projection.gaps:
        if gap.state == 'source_not_connected' and gap.reason_code != 'source_unconnected':
            errors.append(f'Source-not-connected gap has inconsistent reason code: {gap.id}')
        if gap.reason_code == 'known_zero':
            errors.append(f'Gap incorrectly represents known zero: {gap.id}')
        if set(gap.source_reference_ids) - source_ids:
            errors.append(f'Gap has unresolved source references: {gap.id}')
        if set(gap.raw_reference_ids) - raw_ids:
            errors.append(f'Gap has unresolved raw references: {gap.id}')

    native_observations = [observation for observation in projection.observations
                           if isinstance(observation, PriorityHabitatObservation)]
    built_observations = [observation for observation in projection.observations
                          if isinstance(observation, BuiltWorldObservation)]
    if projection.identity.registry_version == REGISTRY_VERSION:
        if (projection.source_feature_references or native_observations
                or projection.objects or projection.relationships or built_observations):
            errors.append('Registry v1 snapshot contains native v2/v3 members')
    elif projection.identity.registry_version == PHI_REGISTRY_VERSION:
        if projection.objects or projection.relationships or built_observations:
            errors.append('Registry v2 snapshot contains built-world v3 members')
        phi_gaps = [gap for gap in projection.gaps
                    if gap.definition_id == 'ecology.priority_habitat.any_mapped_overlap_fraction']
        if not native_observations and not phi_gaps:
            errors.append('Registry v2 snapshot has neither PHI observations nor a PHI availability gap')
    elif projection.identity.registry_version == BUILT_WORLD_REGISTRY_VERSION:
        built_gaps = [gap for gap in projection.gaps
                      if gap.definition_id == 'built.building.mapped_overlap_fraction']
        if not built_observations and not built_gaps:
            errors.append('Registry v3 snapshot has neither built-world observations nor a source gap')

    capability_variables = [capability.legacy_variable for capability in projection.capabilities]
    if len(capability_variables) != len(set(capability_variables)):
        errors.append('Duplicate capability dispositions')
    if set(capability_variables) != set(VARIABLES):
        errors.append('Capability dispositions do not cover exactly the 38 legacy registry concepts')
    for capability in projection.capabilities:
        if set(capability.projected_definition_ids) - set(definitions):
            errors.append(f'Capability has unknown projected definition: {capability.legacy_variable}')
        expected_disposition = (
            'source_backed_core' if capability.legacy_variable in CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS else
            'explicit_gap' if capability.legacy_variable in EXPLICIT_GAPS else
            'legacy_module_output' if capability.legacy_variable in LEGACY_MODULE_OUTPUTS else
            'registered_unconnected'
        )
        if capability.disposition != expected_disposition:
            errors.append(f'Incorrect capability disposition: {capability.legacy_variable}')
        expected_definition_ids = sorted(
            definition.id for definition in LAND_EVIDENCE_V1_DEFINITIONS
            if capability.legacy_variable in definition.legacy_variables
        ) if expected_disposition == 'source_backed_core' else []
        if sorted(capability.projected_definition_ids) != expected_definition_ids:
            errors.append(f'Incorrect capability definition mapping: {capability.legacy_variable}')

    # When the recognized distribution is present, its stored scalar views must
    # agree exactly; a tolerance or reconstruction would hide legacy corruption.
    distributions = {
        observation.id: observation
        for observation in projection.observations
        if isinstance(observation.value, DistributionValue)
    }
    class_views = {
        'built.mapped_built_up_fraction': 'developed',
        'ecology.mapped_herbaceous_wetland_fraction': 'wetland',
        'physical.mapped_permanent_water_fraction': 'water',
    }
    for observation in projection.observations:
        parents = [distributions[parent] for parent in observation.parent_observation_ids if parent in distributions]
        if not parents:
            continue
        distribution = parents[0]
        entries = {entry.category: entry.value for entry in distribution.value.entries}
        if observation.definition_id in class_views:
            expected = entries[class_views[observation.definition_id]]
            if not isinstance(observation.value, NumericValue) or observation.value.value != expected:
                errors.append(f'WorldCover scalar view disagrees with stored distribution: {observation.id}')
        elif observation.definition_id == 'ecology.land_cover.dominant_class':
            expected_code = max(WORLD_COVER_CLASSES, key=lambda code: (entries[WORLD_COVER_CLASSES[code]], -code))
            expected = WORLD_COVER_CLASSES[expected_code]
            if not isinstance(observation.value, CategoryValue) or observation.value.value != expected:
                errors.append(f'WorldCover dominant class disagrees with stored distribution: {observation.id}')

    if errors:
        raise LandEvidenceValidationError('; '.join(dict.fromkeys(errors)))
    return projection
