"""Contract, corruption and retained-real-data checks for land_evidence_v1."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.earth import EarthState, VARIABLES, fingerprint
from backend.land_evidence import (
    CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS,
    LEGACY_MODULE_OUTPUTS,
    CategoryValue,
    DistributionValue,
    LandEvidenceValidationError,
    NumericValue,
    project_land_evidence,
    validate_land_evidence,
)
from backend.wetland import model_spec, run_wetland


REAL_ROOT = Path(__file__).parents[1] / 'data' / 'verification' / 'england-real-v1-final'
PORT_MEADOW = REAL_ROOT / 'port-meadow-after.json'
EXAMPLE = Path(__file__).parents[1] / 'docs' / 'land-evidence-v1-port-meadow.example.json'


@pytest.fixture
def saved():
    return json.loads(PORT_MEADOW.read_text())


def legacy_observations(payload):
    state = payload['environmental_state']
    return [
        observation
        for domain in state['normalized'].values()
        for group in domain.values()
        for observation in group
    ] + list(state['derived'].values())


def legacy_observation(payload, variable):
    return next(observation for observation in legacy_observations(payload)
                if observation['variable'] == variable)


def projected_observation(projection, definition_id, **dimensions):
    return next(observation for observation in projection.observations
                if observation.definition_id == definition_id
                and all(observation.dimensions.get(key) == value for key, value in dimensions.items()))


def test_registry_gives_every_legacy_concept_one_explicit_disposition(saved):
    projection = project_land_evidence(saved)
    assert len(CURRENT_SOURCE_BACKED_LEGACY_CONCEPTS) == 17
    assert len(projection.definitions) == 18  # The stored WorldCover distribution becomes an additional typed record.
    assert len(projection.capabilities) == len(VARIABLES) == 38
    assert {capability.legacy_variable for capability in projection.capabilities} == set(VARIABLES)
    assert sum(capability.disposition == 'source_backed_core' for capability in projection.capabilities) == 17
    assert sum(capability.disposition == 'explicit_gap' for capability in projection.capabilities) == 4
    assert sum(capability.disposition == 'legacy_module_output' for capability in projection.capabilities) == 5
    assert sum(capability.disposition == 'registered_unconnected' for capability in projection.capabilities) == 12


def test_port_meadow_semantics_gaps_and_module_isolation(saved):
    projection = project_land_evidence(saved)
    assert projected_observation(projection, 'physical.elevation.mean').value.value == 57.52826672018964
    assert projected_observation(projection, 'physical.watercourse.distance_min').known_zero
    intersection = projected_observation(projection, 'physical.watercourse.intersects')
    assert intersection.value.value is True
    designation = projected_observation(
        projection, 'designations.overlap_fraction', designation_type='SSSI', status='notified')
    assert designation.value.value == 0.9999999999999987
    cover = projected_observation(
        projection, 'ecology.land_cover.dominant_class', classification='esa_worldcover_2021_v200')
    assert cover.value.value == 'grassland'
    assert cover.provenance.legacy_variable == 'land_use.current_cover'

    inventories = [observation for observation in projection.observations
                   if observation.definition_id == 'ecology.ancient_woodland.mapped_overlap_fraction']
    assert {observation.dimensions['inventory'] for observation in inventories} == {'legacy', 'revised'}
    assert all(observation.known_zero and observation.value.value == 0 for observation in inventories)
    assert all(observation.support.thematic_completeness == 'partial_inventory' for observation in inventories)
    assert not any(observation.definition_id == 'ecology.irreplaceable_habitat_fraction'
                   for observation in projection.observations)
    broad_gap = next(gap for gap in projection.gaps
                     if gap.legacy_variable == 'ecology.irreplaceable_habitat_fraction'
                     and gap.definition_id is None)
    assert broad_gap.state == 'incomplete_inventory'

    explicit = {gap.legacy_variable: gap for gap in projection.gaps if gap.state == 'source_not_connected'}
    assert set(explicit) == {
        'soil.drainage_class', 'ecology.wetland_fraction',
        'ecology.habitat_condition', 'human.infrastructure_fraction',
    }
    assert all(output.variable in LEGACY_MODULE_OUTPUTS for output in projection.legacy_module_outputs)
    assert {output.variable for output in projection.legacy_module_outputs} == LEGACY_MODULE_OUTPUTS
    assert not any(observation.provenance.legacy_variable in LEGACY_MODULE_OUTPUTS
                   for observation in projection.observations)


def test_worldcover_distribution_is_exact_typed_and_links_scalar_views(saved):
    projection = project_land_evidence(saved)
    distribution = projected_observation(
        projection, 'ecology.land_cover.class_distribution', classification='esa_worldcover_2021_v200')
    assert isinstance(distribution.value, DistributionValue)
    entries = {entry.category: entry.value for entry in distribution.value.entries}
    assert entries == {
        'arable': 0.002646217762111178,
        'bare_ground': 0.0,
        'developed': 0.0007011924048548014,
        'grassland': 0.9641051981774719,
        'mangroves': 0.0,
        'moss_lichen': 0.0,
        'shrubland': 0.0,
        'snow_ice': 0.0,
        'water': 0.00035064447282728297,
        'wetland': 0.008927013348618083,
        'woodland': 0.023269733834116794,
    }
    assert json.loads(distribution.value.original_legacy_text) == entries
    views = {
        'built.mapped_built_up_fraction': entries['developed'],
        'ecology.mapped_herbaceous_wetland_fraction': entries['wetland'],
        'physical.mapped_permanent_water_fraction': entries['water'],
    }
    for definition_id, expected in views.items():
        view = projected_observation(projection, definition_id)
        assert view.value.value == expected
        assert distribution.id in view.parent_observation_ids


def test_all_retained_real_cases_replay_project_exactly_and_do_not_mutate():
    paths = sorted(REAL_ROOT.glob('*-after.json'))
    assert len(paths) == 12
    for path in paths:
        saved = json.loads(path.read_text())
        original = deepcopy(saved)
        original_fingerprint = fingerprint(saved)
        state = EarthState.model_validate(saved['environmental_state'])
        wetland = saved['wetland_model']
        spec = {key: wetland[key] for key in model_spec()}
        assert run_wetland(state, spec) == wetland

        projection = project_land_evidence(saved)
        validate_land_evidence(projection)
        assert saved == original
        assert fingerprint(saved) == original_fingerprint
        assert projection.legacy_wetland_result.payload_fingerprint == fingerprint(wetland)
        assert not any(diagnostic.severity == 'error' for diagnostic in projection.diagnostics)

        by_legacy_id = {observation['id']: observation for observation in legacy_observations(saved)}
        for observation in projection.observations:
            origin = observation.provenance
            if origin.legacy_value_path.startswith('findings['):
                index = int(origin.legacy_value_path.split('[', 1)[1].split(']', 1)[0])
                assert origin.legacy_value == saved['findings'][index]['fraction']
                assert observation.value.value == saved['findings'][index]['fraction']
                continue
            legacy = by_legacy_id[origin.legacy_observation_id]
            assert origin.legacy_observation_value == legacy['value']
            assert origin.legacy_unit == legacy['unit']
            assert origin.original_legacy_method == legacy['method']
            if isinstance(observation.value, NumericValue):
                assert observation.value.value == legacy['value']
            elif isinstance(observation.value, CategoryValue):
                assert observation.value.value == legacy['value']
            elif observation.value.kind == 'boolean':
                assert observation.value.value is (legacy['value'] == 'yes')
            elif isinstance(observation.value, DistributionValue):
                original_text = legacy['method'].split('Full class fractions: ', 1)[1]
                stored = json.loads(original_text)
                assert origin.legacy_value == stored
                assert {entry.category: entry.value for entry in observation.value.entries} == stored

        source_ids = {source.id for source in projection.source_references}
        raw_ids = {raw.id for raw in projection.raw_references}
        assert all(set(observation.source_reference_ids) <= source_ids for observation in projection.observations)
        assert all(set(observation.raw_reference_ids) <= raw_ids for observation in projection.observations)
        assert projection.model_dump(mode='json') == project_land_evidence(saved).model_dump(mode='json')


def test_dangling_legacy_parent_is_structural_corruption(saved):
    legacy_observation(saved, 'terrain.slope_deg')['input_ids'] = ['does-not-exist']
    with pytest.raises(LandEvidenceValidationError, match='Dangling parent'):
        project_land_evidence(saved)


def test_duplicate_legacy_ids_are_structural_corruption(saved):
    first = legacy_observation(saved, 'terrain.elevation_m')
    second = legacy_observation(saved, 'terrain.elevation_min_m')
    second['id'] = first['id']
    with pytest.raises(LandEvidenceValidationError, match='Duplicate legacy observation IDs'):
        project_land_evidence(saved)


def test_cyclic_legacy_lineage_is_structural_corruption(saved):
    first = legacy_observation(saved, 'terrain.elevation_m')
    second = legacy_observation(saved, 'terrain.slope_deg')
    first['input_ids'] = [second['id']]
    second['input_ids'] = [first['id']]
    with pytest.raises(LandEvidenceValidationError, match='Cyclic legacy lineage'):
        project_land_evidence(saved)


def test_invalid_category_is_diagnosed_without_inventing_a_fact(saved):
    legacy_observation(saved, 'land_use.current_cover')['value'] = 'authoritative_current_land_use'
    projection = project_land_evidence(saved)
    assert any(diagnostic.code == 'invalid_category' and diagnostic.severity == 'error'
               for diagnostic in projection.diagnostics)
    assert not any(observation.definition_id == 'ecology.land_cover.dominant_class'
                   for observation in projection.observations)
    assert any(gap.reason_code == 'category_uninterpretable' for gap in projection.gaps)
    # The independently encoded exact distribution is still inspectable.
    projected_observation(projection, 'ecology.land_cover.class_distribution')


def test_malformed_worldcover_distribution_is_diagnosed_not_guessed(saved):
    legacy_observation(saved, 'land_use.current_cover')['method'] += ' trailing corruption'
    projection = project_land_evidence(saved)
    assert any(diagnostic.code == 'worldcover_distribution_malformed'
               for diagnostic in projection.diagnostics)
    assert not any(observation.definition_id == 'ecology.land_cover.class_distribution'
                   for observation in projection.observations)
    # Exact legacy scalar values remain available without a reconstructed distribution.
    assert projected_observation(projection, 'ecology.land_cover.dominant_class').value.value == 'grassland'
    assert projected_observation(projection, 'built.mapped_built_up_fraction').value.value == 0.0007011924048548014


def test_zero_coverage_with_non_null_value_is_rejected(saved):
    legacy_observation(saved, 'terrain.slope_deg')['input_coverage'] = 0
    with pytest.raises(LandEvidenceValidationError, match='zero coverage'):
        project_land_evidence(saved)


def test_known_zero_and_unknown_are_distinct_states(saved):
    projection = project_land_evidence(saved)
    distance = projected_observation(projection, 'physical.watercourse.distance_min')
    assert distance.known_zero and distance.value.value == 0
    drainage = next(gap for gap in projection.gaps if gap.legacy_variable == 'soil.drainage_class')
    assert drainage.state == 'source_not_connected'
    assert drainage.reason_code != 'known_zero'
    assert not any(observation.provenance.legacy_variable == 'soil.drainage_class'
                   for observation in projection.observations)


def test_earth_state_only_input_diagnoses_unrecoverable_inventory_zero(saved):
    projection = project_land_evidence(EarthState.model_validate(saved['environmental_state']))
    inventory_gaps = [gap for gap in projection.gaps if gap.reason_code == 'legacy_finding_required']
    assert {gap.dimensions['inventory'] for gap in inventory_gaps} == {'legacy', 'revised'}
    assert not any(observation.definition_id == 'ecology.ancient_woodland.mapped_overlap_fraction'
                   for observation in projection.observations)


def test_unavailable_source_becomes_gap_not_null_observation(saved):
    slope = legacy_observation(saved, 'terrain.slope_deg')
    slope.update(value=None, confidence=0, epistemic_status='unknown', input_coverage=0,
                 missing_reason='Real EA DTM unavailable: source failure')
    projection = project_land_evidence(saved)
    assert not any(observation.definition_id == 'physical.slope.mean'
                   for observation in projection.observations)
    gap = next(gap for gap in projection.gaps if gap.definition_id == 'physical.slope.mean')
    assert gap.state == 'unavailable' and gap.reason_code == 'source_failure'


def test_unsupported_processing_case_is_not_generic_unavailable(saved):
    slope = legacy_observation(saved, 'terrain.slope_deg')
    slope.update(value=None, confidence=0, epistemic_status='unknown', input_coverage=0,
                 missing_reason='Parcel bounding box exceeds parcel processing budget')
    projection = project_land_evidence(saved)
    gap = next(gap for gap in projection.gaps if gap.definition_id == 'physical.slope.mean')
    assert gap.state == 'unsupported_processing_case'
    assert gap.reason_code == 'unsupported_processing_case'


def test_partial_raster_support_remains_partial(saved):
    for variable in (
        'land_use.current_cover', 'land_use.developed_fraction',
        'ecology.mapped_wetland_fraction', 'hydrology.surface_water_fraction',
    ):
        legacy_observation(saved, variable)['input_coverage'] = 0.75
    projection = project_land_evidence(saved)
    worldcover = [observation for observation in projection.observations
                  if observation.provenance.source_dataset == 'ESA WorldCover 2021 v200']
    assert len(worldcover) == 5
    assert all(observation.availability == 'partial' for observation in worldcover)
    assert all(observation.support.coverage_status == 'partial' for observation in worldcover)
    assert all(observation.support.coverage_fraction == 0.75 for observation in worldcover)


def test_projection_validator_rejects_duplicate_dangling_and_cyclic_ids(saved):
    projection = project_land_evidence(saved).model_dump(mode='json')
    duplicate = deepcopy(projection)
    duplicate['observations'][1]['id'] = duplicate['observations'][0]['id']
    with pytest.raises(LandEvidenceValidationError, match='Duplicate observation IDs'):
        validate_land_evidence(duplicate)

    dangling = deepcopy(projection)
    dangling['observations'][0]['parent_observation_ids'] = ['observation:missing']
    with pytest.raises(LandEvidenceValidationError, match='Unresolved parent'):
        validate_land_evidence(dangling)

    cyclic = deepcopy(projection)
    first, second = cyclic['observations'][:2]
    first['parent_observation_ids'] = [second['id']]
    second['parent_observation_ids'] = [first['id']]
    with pytest.raises(LandEvidenceValidationError, match='Cyclic projection lineage'):
        validate_land_evidence(cyclic)


def test_projection_validator_enforces_definitions_units_raw_and_selections(saved):
    projection = project_land_evidence(saved).model_dump(mode='json')

    unknown_definition = deepcopy(projection)
    unknown_definition['observations'][0]['definition_id'] = 'invented.fact'
    with pytest.raises(LandEvidenceValidationError, match='Definition does not resolve'):
        validate_land_evidence(unknown_definition)

    wrong_unit = deepcopy(projection)
    wrong_unit['observations'][0]['unit'] = 'percent'
    with pytest.raises(LandEvidenceValidationError, match='Unit mismatch'):
        validate_land_evidence(wrong_unit)

    out_of_bounds = deepcopy(projection)
    fraction = next(observation for observation in out_of_bounds['observations']
                    if observation['definition_id'] == 'built.mapped_built_up_fraction')
    fraction['value']['value'] = 2
    with pytest.raises(LandEvidenceValidationError, match='above definition maximum'):
        validate_land_evidence(out_of_bounds)

    dangling_raw = deepcopy(projection)
    dangling_raw['observations'][0]['raw_reference_ids'] = ['raw:missing']
    with pytest.raises(LandEvidenceValidationError, match='Unresolved raw references'):
        validate_land_evidence(dangling_raw)

    dangling_selection = deepcopy(projection)
    dangling_selection['selections'][0]['observation_id'] = 'observation:missing'
    with pytest.raises(LandEvidenceValidationError, match='Selected observation does not resolve'):
        validate_land_evidence(dangling_selection)

    module_leak = deepcopy(projection)
    module_leak['observations'][0]['provenance']['legacy_variable'] = 'hydrology.water_context_index'
    with pytest.raises(LandEvidenceValidationError, match='interpretation leaked into core'):
        validate_land_evidence(module_leak)


def test_inspectable_port_meadow_example_uses_retained_exact_values():
    example = json.loads(EXAMPLE.read_text())
    saved = json.loads(PORT_MEADOW.read_text())
    projection = project_land_evidence(saved)
    assert example['schema_version'] == 'land_evidence_v1'
    assert example['identity'] == projection.identity.model_dump(mode='json')
    example_values = {
        (observation['definition_id'], json.dumps(observation['dimensions'], sort_keys=True)):
        observation['value']
        for observation in example['observations']
    }
    for observation in projection.observations:
        key = (observation.definition_id, json.dumps(observation.dimensions, sort_keys=True))
        if key in example_values:
            value = observation.value.model_dump(mode='json')
            if value['kind'] == 'distribution':
                value.pop('original_legacy_text')
            assert example_values[key] == value
    assert set(example['legacy_wetland_module']['excluded_core_variables']) == LEGACY_MODULE_OUTPUTS
    assert not set(example['legacy_wetland_module']['excluded_core_variables']) & {
        observation['provenance']['legacy_variable'] for observation in example['observations']
    }
