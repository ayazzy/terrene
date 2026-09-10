"""Versioned compatibility binding from Land Evidence Core to wetland v0.1.

This module translates facts and gaps; it does not acquire evidence or score a
site.  The resulting ``EarthState`` is the unchanged legacy wetland input
contract, not a second Land Evidence representation.
"""
from __future__ import annotations

import ast
from typing import Any

from backend.adapters import select_observations
from backend.derived import compute_features
from backend.earth import (
    Asset,
    EarthState,
    Observation,
    RawSource,
    SpatialReference,
    VARIABLES,
    fingerprint,
)
from backend.land_evidence import (
    BooleanValue,
    CategoryValue,
    EXPLICIT_GAPS,
    LAND_EVIDENCE_V1_DEFINITIONS,
    LandObservation,
    LandEvidenceProjection,
    LandEvidenceValidationError,
    NumericValue,
    validate_land_evidence,
)


BINDING_VERSION = 'wetland_input_binding_v1'

# Every mapping preserves the existing wetland v0.1 meaning.  In particular,
# mapped wetland remains context-only, built-up remains a developed-area proxy,
# and inventory-scoped ancient woodland feeds only the legacy incomplete
# compatibility input described below.
CORE_INPUT_BINDINGS: dict[str, str] = {
    definition.id: definition.legacy_variables[0]
    for definition in LAND_EVIDENCE_V1_DEFINITIONS
    if definition.legacy_variables
    and definition.id != 'ecology.land_cover.class_distribution'
}

MODEL_INPUT_CONTRACT: dict[str, dict[str, Any]] = {
    'terrain.elevation_m': {
        'evidence_definition': 'physical.elevation.mean',
        'role': 'unassessed model context',
    },
    'terrain.slope_deg': {
        'evidence_definition': 'physical.slope.mean',
        'role': 'scored physical input',
    },
    'hydrology.distance_to_water_m': {
        'evidence_definition': 'physical.watercourse.distance_min',
        'role': 'water-context feature input',
    },
    'hydrology.mapped_flood_extent_fraction': {
        'evidence_definition': 'physical.flood.mapped_extent_fraction',
        'role': 'water-context feature input; mapped context, not probability',
    },
    'land_use.current_cover': {
        'evidence_definition': 'ecology.land_cover.dominant_class',
        'role': 'legacy restoration-need input; no condition inference',
    },
    'land_use.developed_fraction': {
        'evidence_definition': 'built.mapped_built_up_fraction',
        'role': 'legacy feasibility proxy; not infrastructure completeness',
    },
    'ecology.mapped_wetland_fraction': {
        'evidence_definition': 'ecology.mapped_herbaceous_wetland_fraction',
        'role': 'current-state context only; never actual wetland extent',
    },
    'hydrology.surface_water_fraction': {
        'evidence_definition': 'physical.mapped_permanent_water_fraction',
        'role': 'current-state context only',
    },
    'regulatory.protected_area_fraction': {
        'evidence_definition': 'designations.overlap_fraction',
        'role': 'review flag only',
    },
    'ecology.irreplaceable_habitat_fraction': {
        'evidence_definition': 'ecology.ancient_woodland.mapped_overlap_fraction',
        'role': ('legacy compatibility input using the original broad scalar; '
                 'inventory zeroes remain unknown and completeness is not broadened'),
    },
    'ecology.wetland_fraction': {
        'evidence_gap': 'ecology.wetland.actual_extent_fraction',
        'role': 'missing scored input; mapped WorldCover wetland is not substituted',
    },
    'ecology.habitat_condition': {
        'evidence_gap': 'ecology.habitat.condition',
        'role': 'missing scored input; remote cover is not condition',
    },
    'human.infrastructure_fraction': {
        'evidence_gap': 'built.infrastructure.complete_footprint_fraction',
        'role': 'missing scored input; built-up fraction is not substituted',
    },
    'soil.drainage_class': {
        'evidence_gap': 'soil.drainage.class',
        'role': 'missing scored input; no soil property is imputed',
    },
    'ecology.distance_to_habitat_m': {
        'evidence_capability': 'registered_unconnected',
        'role': 'missing optional ecological-opportunity input',
    },
    'hydrology.groundwater_depth_m': {
        'evidence_capability': 'registered_unconnected',
        'role': 'unassessed context',
    },
    'climate.annual_precipitation_mm': {
        'evidence_capability': 'registered_unconnected',
        'role': 'unassessed context',
    },
    'hydrology.flow_accumulation': {
        'evidence_capability': 'registered_unconnected',
        'role': 'unassessed context',
    },
}

MODULE_FEATURE_CONTRACT: dict[str, tuple[str, ...]] = {
    'soil.retention_index': ('soil.drainage_class',),
    'hydrology.water_context_index': (
        'hydrology.mapped_flood_extent_fraction', 'hydrology.distance_to_water_m',
    ),
    'ecology.restoration_need_index': (
        'land_use.current_cover', 'ecology.wetland_fraction',
        'ecology.habitat_condition',
    ),
    'ecology.habitat_proximity_index': ('ecology.distance_to_habitat_m',),
    'human.unblocked_area_index': (
        'land_use.developed_fraction', 'human.infrastructure_fraction',
        'ecology.irreplaceable_habitat_fraction',
    ),
}

_LEGACY_GAP_SOURCE_VERSION = 'crc_os_worldcover_v1'
_SELECTION_NOTE = (
    'Highest-priority available provider; fall back only to a registered covered '
    'provider. All candidates retained.'
)
_ANCIENT_OVERLAY_SUFFIX = (
    ' Source acquisition time and effective spatial resolution may be unknown. '
    'Confidence is a provisional data-quality judgement, not a probability of correctness.'
)
_ANCIENT_ABSENCE_REASON = (
    'No mapped overlap; inventory completeness is not established. Absence remains unknown.'
)


def _legacy_quality(observation) -> tuple[float, str, str]:
    """Decode the exact legacy support fields pinned by binding v1."""
    prefix = 'Legacy confidence='
    text = observation.provenance.legacy_quality_semantics
    if not text.startswith(prefix) or '; observed_or_derived=' not in text or '; epistemic_status=' not in text:
        raise LandEvidenceValidationError(
            'wetland_input_binding_v1 cannot decode legacy quality semantics for '
            + observation.id
        )
    confidence_text, remainder = text[len(prefix):].split('; observed_or_derived=', 1)
    observed_or_derived, epistemic = remainder.split('; epistemic_status=', 1)
    epistemic_status = epistemic.split('.', 1)[0]
    try:
        confidence = ast.literal_eval(confidence_text)
    except (SyntaxError, ValueError) as error:
        raise LandEvidenceValidationError(
            'wetland_input_binding_v1 cannot decode legacy confidence for ' + observation.id
        ) from error
    if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
            or observed_or_derived not in ('observed', 'derived')
            or epistemic_status not in ('observed', 'inferred', 'modelled', 'unknown')):
        raise LandEvidenceValidationError(
            'wetland_input_binding_v1 found unsupported legacy quality semantics for '
            + observation.id
        )
    return float(confidence), observed_or_derived, epistemic_status


def _legacy_value(value):
    if isinstance(value, (NumericValue, CategoryValue)):
        return value.value
    if isinstance(value, BooleanValue):
        return 'yes' if value.value else 'no'
    raise LandEvidenceValidationError('Distribution evidence is not a scalar wetland input')


def _raw_state(projection: LandEvidenceProjection) -> list[RawSource]:
    legacy_raw_ids = {
        raw_id
        for observation in projection.observations
        if isinstance(observation, LandObservation)
        for raw_id in observation.raw_reference_ids
    }
    source_for_raw = {}
    for source in projection.source_references:
        for raw_id in source.raw_reference_ids:
            source_for_raw[raw_id] = source
    records = []
    for raw in projection.raw_references:
        if raw.id not in legacy_raw_ids:
            continue
        source = source_for_raw.get(raw.id)
        if source is None:
            raise LandEvidenceValidationError('Binding cannot resolve source for ' + raw.id)
        records.append(RawSource(
            id=raw.legacy_raw_id,
            source=source.provider,
            source_dataset=source.dataset,
            source_version=source.source_version,
            source_url=source.source_url,
            retrieved_at=source.retrieved_at,
            timestamp=source.reference_period.value,
            storage_reference=raw.storage_reference,
            checksum=raw.checksum,
            assets=[Asset.model_validate(asset.model_dump(mode='json')) for asset in raw.assets],
            raw_semantics=raw.original_semantics,
            # Synthetic labelling was not part of land_evidence_v1 core identity.
            # This binding is intentionally limited to committed production evidence.
            synthetic=False,
        ))
    return records


def _legacy_observation(projected, projected_by_id, raw_by_id) -> Observation:
    confidence, observed_or_derived, epistemic_status = _legacy_quality(projected)
    provenance = projected.provenance
    value = (
        provenance.legacy_observation_value
        if projected.definition_id == 'ecology.ancient_woodland.mapped_overlap_fraction'
        else _legacy_value(projected.value)
    )
    parent_ids = []
    for parent_id in projected.parent_observation_ids:
        parent = projected_by_id[parent_id]
        if parent.definition_id == 'ecology.land_cover.class_distribution':
            continue
        parent_ids.append(parent.provenance.legacy_observation_id)
    coverage = projected.support.coverage_fraction
    if value is not None and coverage is None:
        raise LandEvidenceValidationError(
            'Binding cannot recover input coverage for ' + projected.id
        )
    uncertainty = projected.limitations
    if projected.definition_id == 'ecology.ancient_woodland.mapped_overlap_fraction':
        # Projection retains the inventory finding limitation. Restore the exact
        # overlay-adapter qualification used by the legacy compatibility input.
        if not uncertainty.endswith(_ANCIENT_OVERLAY_SUFFIX):
            uncertainty += _ANCIENT_OVERLAY_SUFFIX
    return Observation(
        id=provenance.legacy_observation_id,
        variable=provenance.legacy_variable,
        value=value,
        unit=provenance.legacy_unit,
        source=provenance.provider,
        source_dataset=provenance.source_dataset,
        source_version=provenance.source_version,
        source_url=provenance.source_url,
        timestamp=provenance.observation_period.value,
        retrieved_at=provenance.retrieved_at,
        spatial=SpatialReference(
            geometry_or_cell_reference=projected.support.boundary_reference,
            crs=projected.support.crs,
            spatial_resolution_m=projected.support.spatial_resolution_m,
            support=projected.support.support_type,
            aggregation=projected.support.aggregation,
        ),
        method=provenance.original_legacy_method,
        observed_or_derived=observed_or_derived,
        epistemic_status=epistemic_status if value is not None else 'unknown',
        confidence=confidence if value is not None else 0,
        uncertainty=uncertainty,
        raw_source_ids=[
            raw_by_id[raw_id].legacy_raw_id for raw_id in projected.raw_reference_ids
        ],
        input_ids=list(dict.fromkeys(parent_ids)),
        input_coverage=coverage or 0,
        missing_reason=(None if value is not None else
                        _ANCIENT_ABSENCE_REASON
                        if projected.definition_id == 'ecology.ancient_woodland.mapped_overlap_fraction'
                        else uncertainty),
        synthetic=False,
    )


def _explicit_gap_observation(projection: LandEvidenceProjection, variable: str, gap) -> Observation:
    reason = gap.reason
    return Observation(
        id=fingerprint([
            _LEGACY_GAP_SOURCE_VERSION,
            projection.identity.legacy_location_id,
            projection.identity.boundary_version,
            variable,
        ]),
        variable=variable,
        value=None,
        unit=VARIABLES[variable][0],
        source='CRC',
        source_dataset='Unconnected priority evidence',
        source_version=_LEGACY_GAP_SOURCE_VERSION,
        timestamp=None,
        retrieved_at=projection.identity.evidence_as_of,
        spatial=SpatialReference(
            geometry_or_cell_reference=projection.identity.boundary_reference,
        ),
        method='No inference or imputation',
        observed_or_derived='derived',
        epistemic_status='unknown',
        confidence=0,
        uncertainty=reason,
        missing_reason=reason,
    )


def _unavailable_observation(projection: LandEvidenceProjection, variable: str, gap) -> Observation:
    sources = {source.id: source for source in projection.source_references}
    source = sources.get(gap.source_reference_ids[0]) if gap.source_reference_ids else None
    raw_ids = {
        raw.id: raw.legacy_raw_id for raw in projection.raw_references
    }
    return Observation(
        id=fingerprint([BINDING_VERSION, projection.identity.projection_id, variable, gap.id]),
        variable=variable,
        value=None,
        unit=VARIABLES[variable][0],
        source=source.provider if source else 'CRC',
        source_dataset=source.dataset if source else 'Unavailable Land Evidence input',
        source_version=source.source_version if source else BINDING_VERSION,
        source_url=source.source_url if source else None,
        timestamp=source.reference_period.value if source else None,
        retrieved_at=source.retrieved_at if source else projection.identity.evidence_as_of,
        spatial=SpatialReference(
            geometry_or_cell_reference=projection.identity.boundary_reference,
        ),
        method=BINDING_VERSION + ' missing-evidence compatibility placeholder',
        observed_or_derived='derived',
        epistemic_status='unknown',
        confidence=0,
        uncertainty=gap.reason,
        raw_source_ids=[raw_ids[item] for item in gap.raw_reference_ids],
        missing_reason=gap.reason,
    )


def bind_wetland_input(
    value: LandEvidenceProjection | dict[str, Any], boundary_geometry: dict,
    *, binding_version: str = BINDING_VERSION,
) -> EarthState:
    """Build and feature-compute the unchanged wetland ``EarthState`` input.

    No acquisition or persistence occurs. The supplied boundary is used only to
    satisfy the legacy state envelope and must match the immutable snapshot
    boundary fingerprint.
    """
    if binding_version != BINDING_VERSION:
        raise ValueError('Unsupported wetland input binding: ' + binding_version)
    projection = validate_land_evidence(value)
    if fingerprint(boundary_geometry) != projection.identity.boundary_geometry_fingerprint:
        raise LandEvidenceValidationError('Wetland binding boundary geometry does not match snapshot')

    state = EarthState(
        location_id=projection.identity.legacy_location_id,
        boundary_version=projection.identity.boundary_version,
        geography=projection.identity.geography,
        as_of=projection.identity.evidence_as_of,
        geometry=boundary_geometry,
        raw=_raw_state(projection),
    )
    raw_by_id = {raw.id: raw for raw in projection.raw_references}
    projected_by_id: dict[str, Any] = {
        observation.id: observation for observation in projection.observations
    }

    by_legacy_id: dict[str, Observation] = {}
    selected_projected_ids = {
        selection.observation_id for selection in projection.selections
    }
    selected_legacy_ids: dict[str, str] = {}
    for projected in projection.observations:
        variable = CORE_INPUT_BINDINGS.get(projected.definition_id)
        if variable is None:
            continue
        legacy = _legacy_observation(projected, projected_by_id, raw_by_id)
        prior = by_legacy_id.get(legacy.id)
        if prior is not None and prior != legacy:
            raise LandEvidenceValidationError(
                'Binding found contradictory views of legacy observation ' + legacy.id
            )
        by_legacy_id[legacy.id] = legacy
        if projected.id in selected_projected_ids:
            selected_legacy_ids.setdefault(variable, legacy.id)

    candidates = [(100, observation) for observation in by_legacy_id.values()]
    for variable, (definition_id, _) in EXPLICIT_GAPS.items():
        matches = [
            gap for gap in projection.gaps
            if gap.legacy_variable == variable and gap.definition_id == definition_id
        ]
        if matches and variable not in {observation.variable for _, observation in candidates}:
            candidates.append((100, _explicit_gap_observation(projection, variable, matches[0])))

    # Source-backed missing evidence must stay missing. A placeholder carries the
    # exact gap reason into the unchanged model without manufacturing a value.
    candidate_variables = {observation.variable for _, observation in candidates}
    for definition_id, variable in CORE_INPUT_BINDINGS.items():
        if variable in candidate_variables or variable == 'ecology.irreplaceable_habitat_fraction':
            continue
        gaps = [gap for gap in projection.gaps if gap.definition_id == definition_id]
        if gaps:
            candidates.append((100, _unavailable_observation(projection, variable, gaps[0])))
            candidate_variables.add(variable)

    select_observations(state, candidates)
    for variable, legacy_id in selected_legacy_ids.items():
        if variable != 'ecology.irreplaceable_habitat_fraction':
            state.selected[variable] = legacy_id
    # select_observations pins the legacy notes. Keep this assertion close to the
    # binding because those notes contribute to the historical state fingerprint.
    if any(note != _SELECTION_NOTE for variable, note in state.selection_notes.items()
           if variable != 'ecology.irreplaceable_habitat_fraction'):
        raise RuntimeError('Unexpected legacy observation selection semantics')
    return compute_features(state)
