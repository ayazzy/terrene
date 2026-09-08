"""New evidence semantics; all generated inputs here are labelled synthetic."""
from copy import deepcopy
import pytest
from backend.adapters import select_observations
from backend.derived import compute_features, DRAINAGE_RETENTION
from backend.wetland import run_wetland, model_spec
from test_nature import state, obs, FAVOURABLE


def test_categorical_soil_is_explicit_ordinal_evidence():
    values = {k: v for k, v in FAVOURABLE.items() if k != 'soil.permeability'}
    values['soil.drainage_class'] = 'poorly_drained'
    earth = state(values)
    retention = earth.get('soil.retention_index')
    assert retention.value == DRAINAGE_RETENTION['poorly_drained']
    assert earth.get('soil.permeability') is None
    assert retention.input_ids == ['synthetic:soil.drainage_class']
    assert 'not hydraulic conductivity' in retention.uncertainty
    model = run_wetland(earth)
    assert model['components'][0]['coverage'] == 1
    assert 'soil.drainage_class' in model['evidence_summary']['data_coverage']['variables']


def test_unsupported_soil_class_does_not_gain_numeric_precision():
    values = {k: v for k, v in FAVOURABLE.items() if k != 'soil.permeability'}
    earth = state(values | {'soil.drainage_class': 'vaguely wet soil'})
    assert earth.get('soil.retention_index').value is None
    assert run_wetland(earth)['overall']['score'] is None


def test_mapped_wetland_zero_does_not_establish_actual_wetland_absence():
    values = {k: v for k, v in FAVOURABLE.items() if k not in ('ecology.wetland_fraction','ecology.habitat_condition')}
    earth = state(values | {'ecology.mapped_wetland_fraction': 0})
    assert earth.get('ecology.wetland_fraction') is None
    result = run_wetland(earth)
    assert result['overall']['score'] is None
    assert {'ecology.wetland_fraction', 'ecology.habitat_condition'} <= {g['variable'] for g in result['missing_inputs']}


def test_generic_grassland_is_not_improved_or_degraded():
    result = run_wetland(state(FAVOURABLE | {'land_use.current_cover': 'grassland'}))
    assert next(c for c in result['components'] if c['key'] == 'restoration_need')['score'] is None
    assert result['overall']['score'] is None


def test_coverage_quality_and_model_validation_are_different():
    full = run_wetland(state())
    evidence = full['evidence_summary']
    assert evidence['data_coverage']['fraction'] == 1
    assert evidence['data_quality']['index'] == pytest.approx(.9)
    assert evidence['model_confidence']['label'] == 'UNVALIDATED'
    assert full['components'][0]['band'] == 'VERY_HIGH'
    assert full['components'][0]['supporting_evidence']


def test_pinned_model_replay_ignores_acquisition_environment(monkeypatch):
    earth = state()
    spec = model_spec(environment_version='crc_england_real_inputs_v1')
    original = run_wetland(earth, spec)
    monkeypatch.setenv('CRC_ENVIRONMENT_ACQUISITION', 'disabled')
    assert original == run_wetland(earth, spec)


def test_tiny_missing_coverage_cannot_round_up_and_unlock_ranking():
    earth = state()
    earth.get('terrain.slope_deg').input_coverage = .99999
    result = run_wetland(earth)
    assert result['components'][0]['coverage'] < 1
    assert result['overall']['score'] is None
