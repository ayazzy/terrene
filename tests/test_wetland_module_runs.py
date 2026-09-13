"""Snapshot-bound wetland parity, separation, identity and isolation checks."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, func, insert, select, update

from backend import core
from backend.earth import fingerprint
from backend.land_evidence import (
    LEGACY_MODULE_OUTPUTS,
    LandEvidenceValidationError,
    project_land_evidence,
)
from backend import land_evidence_store as evidence_store
from backend import module_runs
from backend.wetland import run_wetland
from backend.wetland_binding import (
    BINDING_VERSION,
    MODEL_INPUT_CONTRACT,
    bind_wetland_input,
)


REAL_ROOT = Path(__file__).parents[1] / 'data' / 'verification' / 'england-real-v1-final'
PORT_MEADOW = REAL_ROOT / 'port-meadow-after.json'
MODEL_SPEC_KEYS = (
    'model_version', 'adapter_version', 'feature_version',
    'environment_version', 'refresh_sources', 'config', 'signature',
)


@pytest.fixture
def module_database(tmp_path, monkeypatch):
    database_url = os.getenv('CRC_TEST_DATABASE_URL')
    database = create_engine(
        database_url or 'sqlite:///' + str(tmp_path / 'module-runs.db'),
        pool_pre_ping=True,
    )
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    tables = (
        core.design_revisions, core.design_alternatives,
        core.infrastructure_projects, core.module_runs,
        core.land_evidence_snapshot_origins,
        core.land_evidence_snapshot_links, core.land_evidence_snapshot_members,
        core.land_evidence_snapshots, core.assessments, core.sites,
    )
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    yield database
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    database.dispose()


def saved(path=PORT_MEADOW):
    return json.loads(path.read_text())


def model_spec_from(payload):
    return {key: deepcopy(payload['wetland_model'][key]) for key in MODEL_SPEC_KEYS}


def insert_assessment(database, payload, *, assessment_id, org='org-a'):
    state = payload['environmental_state']
    with database.begin() as connection:
        if not connection.execute(select(core.sites.c.id).where(
                core.sites.c.id == state['location_id'], core.sites.c.org == org)).first():
            connection.execute(insert(core.sites).values(
                id=state['location_id'], org=org, name=payload['site_name'],
                status='Unreviewed', version=state['boundary_version'],
                geometry=payload['geometry'], created=payload['completed'],
            ))
        connection.execute(insert(core.assessments).values(
            id=assessment_id, org=org, site_id=state['location_id'],
            version=state['boundary_version'], geometry=payload['geometry'],
            site_name=payload['site_name'], state='completed', result=payload,
            created=payload['completed'], dedupe='dedupe-' + assessment_id,
            model_spec=model_spec_from(payload),
        ))


def commit(database, payload, *, suffix='one', org='org-a'):
    assessment_id = 'assessment-' + suffix
    insert_assessment(database, payload, assessment_id=assessment_id, org=org)
    return evidence_store.create_snapshot_from_legacy_assessment(
        assessment_id, org=org,
    )


def table_count(database, table):
    with database.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def legacy_observation(payload, variable):
    return next(
        observation
        for domain in payload['environmental_state']['normalized'].values()
        for group in domain.values()
        for observation in group
        if observation['variable'] == variable
    )


def test_binding_contract_refuses_semantic_substitutions():
    assert MODEL_INPUT_CONTRACT['ecology.wetland_fraction'] == {
        'evidence_gap': 'ecology.wetland.actual_extent_fraction',
        'role': 'missing scored input; mapped WorldCover wetland is not substituted',
    }
    assert MODEL_INPUT_CONTRACT['human.infrastructure_fraction']['evidence_gap'] == (
        'built.infrastructure.complete_footprint_fraction'
    )
    assert MODEL_INPUT_CONTRACT['ecology.habitat_condition']['evidence_gap'] == (
        'ecology.habitat.condition'
    )
    assert 'completeness is not broadened' in (
        MODEL_INPUT_CONTRACT['ecology.irreplaceable_habitat_fraction']['role']
    )


def test_all_twelve_retained_cases_have_exact_legacy_parity(module_database):
    paths = sorted(REAL_ROOT.glob('*-after.json'))
    assert len(paths) == 12
    assessment_fingerprints = {}
    for path in paths:
        payload = saved(path)
        suffix = path.stem
        assessment_fingerprints[suffix] = fingerprint(payload)
        snapshot = commit(module_database, payload, suffix=suffix, org='verification-org')
        projection = evidence_store.load_land_evidence_snapshot(
            snapshot.id, org='verification-org',
        )
        bound_state = bind_wetland_input(projection, payload['geometry'])
        assert bound_state.model_dump(mode='json') == payload['environmental_state']
        assert run_wetland(bound_state, model_spec_from(payload)) == payload['wetland_model']

        run = module_runs.run_wetland_from_snapshot(
            snapshot.id, org='verification-org', spec=model_spec_from(payload),
        )
        assert run.result == payload['wetland_model']
        assert run.evidence_snapshot_id == snapshot.id
        assert run.evidence_content_hash == snapshot.content_hash
        assert run.module_id == module_runs.MODULE_ID
        assert run.module_version == payload['wetland_model']['model_version']
        assert run.input_binding_version == BINDING_VERSION
        assert run.model_signature == payload['wetland_model']['signature']
        assert run.completed >= run.created
        assert not ({item.provenance.legacy_variable for item in projection.observations}
                    & LEGACY_MODULE_OUTPUTS)

    assert table_count(module_database, core.module_runs) == 12
    with module_database.connect() as connection:
        rows = connection.execute(select(core.assessments)).mappings().all()
    assert all(
        fingerprint(row['result']) == assessment_fingerprints[row['id'].removeprefix('assessment-')]
        for row in rows
    )


def test_known_zero_missing_inputs_and_incomplete_inventory_stay_distinct():
    payload = saved()
    projection = project_land_evidence(payload)
    state = bind_wetland_input(projection, payload['geometry'])
    assert state.get('hydrology.distance_to_water_m').value == 0
    assert state.get('ecology.mapped_wetland_fraction').value is not None
    assert state.get('ecology.wetland_fraction').value is None
    assert state.get('ecology.habitat_condition').value is None
    assert state.get('human.infrastructure_fraction').value is None
    assert state.get('ecology.irreplaceable_habitat_fraction').value is None
    assert len(state.normalized['ecology']['irreplaceable_habitat_fraction']) == 2
    assert all(item.value is None for item in
               state.normalized['ecology']['irreplaceable_habitat_fraction'])
    result = run_wetland(state, model_spec_from(payload))
    missing = {item['variable'] for item in result['missing_inputs']}
    assert {
        'ecology.wetland_fraction', 'ecology.habitat_condition',
        'human.infrastructure_fraction', 'ecology.irreplaceable_habitat_fraction',
    } <= missing


def test_partial_and_missing_source_evidence_do_not_unlock_model():
    partial_payload = saved()
    legacy_observation(partial_payload, 'terrain.slope_deg')['input_coverage'] = .5
    partial = bind_wetland_input(
        project_land_evidence(partial_payload), partial_payload['geometry'],
    )
    assert partial.get('terrain.slope_deg').input_coverage == .5
    partial_result = run_wetland(partial, model_spec_from(partial_payload))
    assert partial_result['components'][0]['coverage'] < 1
    assert partial_result['overall']['score'] is None

    missing_payload = saved()
    slope = legacy_observation(missing_payload, 'terrain.slope_deg')
    slope.update(
        value=None, confidence=0, epistemic_status='unknown', input_coverage=0,
        missing_reason='Real EA DTM unavailable: source failure',
    )
    missing = bind_wetland_input(
        project_land_evidence(missing_payload), missing_payload['geometry'],
    )
    assert missing.get('terrain.slope_deg').value is None
    missing_result = run_wetland(missing, model_spec_from(missing_payload))
    assert 'terrain.slope_deg' in {
        item['variable'] for item in missing_result['missing_inputs']
    }
    assert missing_result['overall']['score'] is None


def test_invalid_or_wrong_boundary_projection_is_rejected():
    payload = saved()
    projection = project_land_evidence(payload).model_dump(mode='json')
    projection['observations'][0]['unit'] = 'percent'
    with pytest.raises(LandEvidenceValidationError, match='Unit mismatch'):
        bind_wetland_input(projection, payload['geometry'])

    valid = project_land_evidence(payload)
    changed_geometry = deepcopy(payload['geometry'])
    changed_geometry['binding_test_change'] = True
    with pytest.raises(LandEvidenceValidationError, match='boundary geometry'):
        bind_wetland_input(valid, changed_geometry)


def test_corrupt_committed_snapshot_cannot_execute(module_database):
    payload = saved()
    snapshot = commit(module_database, payload)
    path = core.ROOT / 'objects' / snapshot.manifest_key
    path.write_text('{}')
    with pytest.raises(evidence_store.LandEvidenceSnapshotConflict,
                       match='manifest is invalid'):
        module_runs.run_wetland_from_snapshot(
            snapshot.id, org='org-a', spec=model_spec_from(payload),
        )
    assert table_count(module_database, core.module_runs) == 0


def test_wrong_organisation_cannot_run_or_retrieve(module_database):
    payload = saved()
    snapshot = commit(module_database, payload, org='org-a')
    with pytest.raises(evidence_store.LandEvidenceSnapshotNotFound):
        module_runs.run_wetland_from_snapshot(
            snapshot.id, org='org-b', spec=model_spec_from(payload),
        )
    run = module_runs.run_wetland_from_snapshot(
        snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    with pytest.raises(module_runs.ModuleRunNotFound):
        module_runs.get_module_run(run.id, org='org-b')
    assert module_runs.get_module_run(run.id, org='org-a') == run


def test_duplicate_execution_is_idempotent_and_snapshot_is_unchanged(module_database):
    payload = saved()
    snapshot = commit(module_database, payload)
    manifest_before = core.load_object(snapshot.manifest_key)
    assessment_before = fingerprint(payload)
    first = module_runs.run_wetland_from_snapshot(
        snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    second = module_runs.run_wetland_from_snapshot(
        snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    assert second == first
    assert table_count(module_database, core.module_runs) == 1
    assert core.load_object(snapshot.manifest_key) == manifest_before
    with module_database.connect() as connection:
        retained = connection.execute(select(core.assessments.c.result)).scalar_one()
    assert fingerprint(retained) == assessment_before


def test_historical_boundary_object_is_resolved_without_assessment_evidence(module_database):
    payload = saved()
    snapshot = commit(module_database, payload)
    raw_feature = {
        'type': 'Feature', 'properties': {'historical': True},
        'geometry': payload['geometry'],
    }
    core.store_object(
        f'org-a/boundaries/{snapshot.site_id}/{snapshot.boundary_version}.json',
        json.dumps(raw_feature),
    )
    with module_database.begin() as connection:
        connection.execute(update(core.sites).where(
            core.sites.c.id == snapshot.site_id,
        ).values(version=2))
    run = module_runs.run_wetland_from_snapshot(
        snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    assert run.result == payload['wetland_model']


def test_changed_snapshot_binding_and_configuration_change_run_identity(module_database):
    payload = saved()
    first_snapshot = commit(module_database, payload, suffix='original')
    first = module_runs.run_wetland_from_snapshot(
        first_snapshot.id, org='org-a', spec=model_spec_from(payload),
    )

    changed_payload = deepcopy(payload)
    legacy_observation(changed_payload, 'terrain.elevation_m')['value'] += .125
    second_snapshot = evidence_store.persist_land_evidence_snapshot(
        project_land_evidence(changed_payload), org='org-a',
        site_id=first_snapshot.site_id,
    )
    changed_evidence = module_runs.run_wetland_from_snapshot(
        second_snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    assert changed_evidence.id != first.id
    assert changed_evidence.evidence_snapshot_id != first.evidence_snapshot_id

    changed_spec = model_spec_from(payload)
    changed_spec['config']['slope_zero_score_deg'] = 5
    from backend.wetland import model_spec
    changed_spec = model_spec(
        changed_spec['config'],
        environment_version=changed_spec['environment_version'],
        refresh_sources=changed_spec['refresh_sources'],
    )
    changed_config = module_runs.run_wetland_from_snapshot(
        first_snapshot.id, org='org-a', spec=changed_spec,
    )
    assert changed_config.id != first.id
    assert changed_config.model_signature != first.model_signature

    future_binding_id = module_runs.module_run_identity(
        org='org-a', evidence_snapshot_id=first_snapshot.id,
        module_id=module_runs.MODULE_ID, module_version=first.module_version,
        input_binding_version='wetland_input_binding_v2',
        model_signature=first.model_signature,
    )
    assert future_binding_id != first.id
    future_module_id = module_runs.module_run_identity(
        org='org-a', evidence_snapshot_id=first_snapshot.id,
        module_id=module_runs.MODULE_ID,
        module_version='wetland_restoration_v0_2',
        input_binding_version=BINDING_VERSION,
        model_signature=first.model_signature,
    )
    assert future_module_id != first.id
    with pytest.raises(ValueError, match='Unsupported wetland input binding'):
        module_runs.run_wetland_from_snapshot(
            first_snapshot.id, org='org-a',
            binding_version='wetland_input_binding_v2', spec=model_spec_from(payload),
        )
    assert table_count(module_database, core.module_runs) == 3


def test_module_run_result_is_integrity_checked(module_database):
    payload = saved()
    snapshot = commit(module_database, payload)
    run = module_runs.run_wetland_from_snapshot(
        snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    changed = deepcopy(run.result)
    changed['overall']['band'] = 'SILENTLY_CHANGED'
    with module_database.begin() as connection:
        connection.execute(update(core.module_runs).where(
            core.module_runs.c.id == run.id,
        ).values(result=changed))
    with pytest.raises(module_runs.ModuleRunConflict, match='content hash mismatch'):
        module_runs.get_module_run(run.id, org='org-a')


def test_module_outputs_have_no_land_evidence_membership(module_database):
    payload = saved()
    snapshot = commit(module_database, payload)
    run = module_runs.run_wetland_from_snapshot(
        snapshot.id, org='org-a', spec=model_spec_from(payload),
    )
    projection = evidence_store.load_land_evidence_snapshot(snapshot.id, org='org-a')
    with module_database.connect() as connection:
        member_ids = set(connection.execute(select(
            core.land_evidence_snapshot_members.c.member_id
        ).where(
            core.land_evidence_snapshot_members.c.snapshot_id == snapshot.id,
        )).scalars())
    assert run.id not in member_ids
    assert run.content_hash not in member_ids
    assert not ({item.provenance.legacy_variable for item in projection.observations}
                & LEGACY_MODULE_OUTPUTS)
