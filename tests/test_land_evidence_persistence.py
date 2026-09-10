"""Persistence, identity, isolation and retained-real parity checks."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, insert, select, update

from backend import core
from backend.earth import fingerprint
from backend.land_evidence import (
    LEGACY_MODULE_OUTPUTS,
    LandEvidenceValidationError,
    project_land_evidence,
)
from backend import land_evidence_store as store


REAL_ROOT = Path(__file__).parents[1] / 'data' / 'verification' / 'england-real-v1-final'
PORT_MEADOW = REAL_ROOT / 'port-meadow-after.json'


@pytest.fixture
def snapshot_database(tmp_path, monkeypatch):
    database = create_engine('sqlite:///' + str(tmp_path / 'snapshots.db'))
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    yield database
    database.dispose()


def saved(path=PORT_MEADOW):
    return json.loads(path.read_text())


def table_count(database, table):
    with database.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def legacy_observation(payload, variable):
    state = payload['environmental_state']
    return next(
        observation
        for domain in state['normalized'].values()
        for group in domain.values()
        for observation in group
        if observation['variable'] == variable
    )


def insert_legacy_assessment(database, payload, *, assessment_id='assessment-1',
                             org='org-a'):
    state = payload['environmental_state']
    site_id = state['location_id']
    with database.begin() as connection:
        if not connection.execute(select(core.sites.c.id).where(
                core.sites.c.id == site_id, core.sites.c.org == org)).first():
            connection.execute(insert(core.sites).values(
                id=site_id, org=org, name=payload['site_name'], status='Unreviewed',
                version=state['boundary_version'], geometry=payload['geometry'],
                created=payload['completed'],
            ))
        connection.execute(insert(core.assessments).values(
            id=assessment_id, org=org, site_id=site_id,
            version=state['boundary_version'], geometry=payload['geometry'],
            site_name=payload['site_name'], state='completed', result=payload,
            created=payload['completed'], dedupe='dedupe-' + assessment_id,
        ))
    return assessment_id


def test_all_retained_real_assessments_persist_exactly_and_keep_core_semantics(snapshot_database):
    paths = sorted(REAL_ROOT.glob('*-after.json'))
    assert len(paths) == 12
    originals = {}
    for path in paths:
        payload = saved(path)
        originals[path.name] = fingerprint(payload)
        projection = project_land_evidence(payload)
        assessment_id = insert_legacy_assessment(
            snapshot_database, payload, assessment_id='retained:' + path.stem,
            org='verification-org',
        )
        record = store.create_snapshot_from_legacy_assessment(
            assessment_id, org='verification-org',
        )
        loaded = store.load_land_evidence_snapshot(record.id, org='verification-org')
        assert loaded.model_dump(mode='json') == projection.model_dump(mode='json')
        assert record.content_hash == store.snapshot_content_hash(projection)
        assert record.boundary_version == payload['environmental_state']['boundary_version']
        assert record.boundary_geometry_fingerprint == fingerprint(payload['geometry'])
        assert not ({item.provenance.legacy_variable for item in loaded.observations}
                    & LEGACY_MODULE_OUTPUTS)

    assert table_count(snapshot_database, core.land_evidence_snapshots) == 12
    assert all(fingerprint(saved(path)) == originals[path.name] for path in paths)

    port = next(item for item in store.list_land_evidence_snapshots(
        org='verification-org', site_id='verification-port-meadow', boundary_version=1,
    ))
    projection = store.load_land_evidence_snapshot(port.id, org='verification-org')
    zero = next(item for item in projection.observations
                if item.definition_id == 'physical.watercourse.distance_min')
    missing = next(item for item in projection.gaps
                   if item.legacy_variable == 'soil.drainage_class')
    assert zero.known_zero and zero.value.value == 0
    assert missing.state == 'source_not_connected' and missing.reason_code != 'known_zero'


def test_repeat_creation_is_idempotent_and_memberships_resolve(snapshot_database):
    projection = project_land_evidence(saved())
    first = store.persist_land_evidence_snapshot(
        projection, org='org-a', site_id=projection.identity.legacy_location_id,
    )
    counts = {
        table.name: table_count(snapshot_database, table)
        for table in (
            core.land_evidence_snapshots, core.land_evidence_snapshot_members,
            core.land_evidence_snapshot_links, core.land_evidence_snapshot_origins,
        )
    }
    second = store.persist_land_evidence_snapshot(
        projection, org='org-a', site_id=projection.identity.legacy_location_id,
    )
    assert second == first
    assert counts == {
        table.name: table_count(snapshot_database, table)
        for table in (
            core.land_evidence_snapshots, core.land_evidence_snapshot_members,
            core.land_evidence_snapshot_links, core.land_evidence_snapshot_origins,
        )
    }

    with snapshot_database.connect() as connection:
        member_kinds = set(connection.execute(select(
            core.land_evidence_snapshot_members.c.kind
        ).where(core.land_evidence_snapshot_members.c.snapshot_id == first.id)).scalars())
        links = connection.execute(select(core.land_evidence_snapshot_links).where(
            core.land_evidence_snapshot_links.c.snapshot_id == first.id,
            core.land_evidence_snapshot_links.c.owner_kind == 'observation',
        )).mappings().all()
    assert {'observation', 'gap', 'capability', 'source_reference', 'raw_reference'} <= member_kinds
    assert 'legacy_module_output' not in member_kinds
    assert {'source_reference', 'raw_reference', 'parent_observation'} <= {
        link['relationship'] for link in links
    }


def test_legacy_bridge_is_additive_and_idempotent(snapshot_database):
    payload = saved()
    before = fingerprint(payload)
    assessment_id = insert_legacy_assessment(snapshot_database, payload)
    first = store.create_snapshot_from_legacy_assessment(assessment_id, org='org-a')
    second = store.create_snapshot_from_legacy_assessment(assessment_id, org='org-a')
    assert first == second
    with snapshot_database.connect() as connection:
        retained = connection.execute(select(core.assessments.c.result).where(
            core.assessments.c.id == assessment_id)).scalar_one()
        origin = connection.execute(select(core.land_evidence_snapshot_origins).where(
            core.land_evidence_snapshot_origins.c.snapshot_id == first.id,
        )).mappings().one()
    assert fingerprint(retained) == before
    assert origin['assessment_id'] == assessment_id
    assert origin['assessment_fingerprint'] == project_land_evidence(payload).identity.legacy_assessment_fingerprint


def test_invalid_projection_is_rejected_before_publication(snapshot_database):
    projection = project_land_evidence(saved()).model_dump(mode='json')
    projection['observations'][0]['unit'] = 'percent'
    with pytest.raises(LandEvidenceValidationError, match='Unit mismatch'):
        store.persist_land_evidence_snapshot(
            projection, org='org-a',
            site_id=projection['identity']['legacy_location_id'],
        )
    assert table_count(snapshot_database, core.land_evidence_snapshots) == 0
    assert not list((core.ROOT / 'objects').rglob('*.json'))


def test_partial_database_failure_never_publishes_and_retry_recovers(
        snapshot_database, monkeypatch):
    projection = project_land_evidence(saved())
    original = store._insert_memberships
    with monkeypatch.context() as context:
        context.setattr(store, '_insert_memberships',
                        lambda *args: (_ for _ in ()).throw(RuntimeError('injected membership failure')))
        with pytest.raises(RuntimeError, match='injected membership failure'):
            store.persist_land_evidence_snapshot(
                projection, org='org-a', site_id=projection.identity.legacy_location_id,
            )
    assert store._insert_memberships is original
    assert table_count(snapshot_database, core.land_evidence_snapshots) == 0
    assert table_count(snapshot_database, core.land_evidence_snapshot_members) == 0
    orphan_objects = list((core.ROOT / 'objects').rglob('*.json'))
    assert len(orphan_objects) == 1

    committed = store.persist_land_evidence_snapshot(
        projection, org='org-a', site_id=projection.identity.legacy_location_id,
    )
    assert table_count(snapshot_database, core.land_evidence_snapshots) == 1
    assert store.load_land_evidence_snapshot(committed.id, org='org-a') == projection
    assert list((core.ROOT / 'objects').rglob('*.json')) == orphan_objects


def test_snapshot_is_immutable_and_noncore_bridge_changes_reuse_it(snapshot_database):
    original_payload = saved()
    original = project_land_evidence(original_payload)
    insert_legacy_assessment(
        snapshot_database, original_payload, assessment_id='assessment-1', org='org-a',
    )
    first = store.create_snapshot_from_legacy_assessment('assessment-1', org='org-a')
    manifest_before = core.load_object(first.manifest_key)

    changed_bridge_payload = deepcopy(original_payload)
    changed_bridge_payload['site_name'] = 'Renamed presentation only'
    changed_bridge_payload['findings'][0]['interpretation'] = 'Changed legacy presentation only'
    changed_bridge_payload['next_steps'] = ['Changed legacy recommendation only']
    changed_bridge_payload['wetland_model']['overall']['band'] = 'LEGACY_PRESENTATION_CHANGE'
    changed_bridge_payload['environmental_state']['derived'][
        'hydrology.water_context_index'
    ]['value'] = 0.123
    changed_bridge = project_land_evidence(changed_bridge_payload)
    assert changed_bridge.identity.projection_id == original.identity.projection_id
    assert store.snapshot_content_hash(changed_bridge) == first.content_hash
    insert_legacy_assessment(
        snapshot_database, changed_bridge_payload,
        assessment_id='assessment-2', org='org-a',
    )
    same = store.create_snapshot_from_legacy_assessment('assessment-2', org='org-a')
    assert same.id == first.id
    assert core.load_object(first.manifest_key) == manifest_before
    with snapshot_database.connect() as connection:
        assert connection.execute(select(func.count()).select_from(
            core.land_evidence_snapshot_origins
        )).scalar_one() == 2

    with pytest.raises(core.ImmutableObjectConflict):
        core.store_object_immutable(first.manifest_key, b'changed')

    with snapshot_database.begin() as connection:
        member = connection.execute(select(core.land_evidence_snapshot_members).where(
            core.land_evidence_snapshot_members.c.snapshot_id == first.id,
            core.land_evidence_snapshot_members.c.kind == 'observation',
        )).mappings().first()
        connection.execute(update(core.land_evidence_snapshot_members).where(
            core.land_evidence_snapshot_members.c.snapshot_id == first.id,
            core.land_evidence_snapshot_members.c.kind == member['kind'],
            core.land_evidence_snapshot_members.c.member_id == member['member_id'],
        ).values(definition_id='silently-mutated'))
    with pytest.raises(store.LandEvidenceSnapshotConflict,
                       match='membership catalogue mismatch'):
        store.load_land_evidence_snapshot(first.id, org='org-a')


def test_wrong_organisation_cannot_discover_or_load_snapshot(snapshot_database):
    payload = saved()
    projection = project_land_evidence(payload)
    insert_legacy_assessment(
        snapshot_database, payload, assessment_id='private-assessment', org='org-a',
    )
    record = store.create_snapshot_from_legacy_assessment(
        'private-assessment', org='org-a',
    )
    assert store.list_land_evidence_snapshots(
        org='org-b', site_id=projection.identity.legacy_location_id,
    ) == []
    with pytest.raises(store.LandEvidenceSnapshotNotFound):
        store.get_land_evidence_snapshot(record.id, org='org-b')
    with pytest.raises(store.LandEvidenceSnapshotNotFound):
        store.load_land_evidence_snapshot(record.id, org='org-b')
    with pytest.raises(store.LandEvidenceSnapshotConflict,
                       match='does not resolve in this organisation'):
        store.persist_land_evidence_snapshot(
            projection, org='org-b', site_id=projection.identity.legacy_location_id,
            origin_assessment_id='private-assessment',
        )


def test_changed_boundary_and_changed_evidence_create_new_snapshots(snapshot_database):
    original_payload = saved()
    original = project_land_evidence(original_payload)
    first = store.persist_land_evidence_snapshot(
        original, org='org-a', site_id=original.identity.legacy_location_id,
    )

    changed_boundary_payload = deepcopy(original_payload)
    state = changed_boundary_payload['environmental_state']
    state['boundary_version'] = 2
    changed_boundary_payload['boundary_version'] = 2
    for domain in state['normalized'].values():
        for observations in domain.values():
            for observation in observations:
                observation['spatial']['geometry_or_cell_reference'] = (
                    state['location_id'] + '/boundary/2'
                )
    for observation in state['derived'].values():
        observation['spatial']['geometry_or_cell_reference'] = state['location_id'] + '/boundary/2'
    changed_boundary = project_land_evidence(changed_boundary_payload)
    second = store.persist_land_evidence_snapshot(
        changed_boundary, org='org-a', site_id=changed_boundary.identity.legacy_location_id,
    )
    assert second.id != first.id and second.boundary_version == 2

    changed_evidence_payload = deepcopy(original_payload)
    elevation = legacy_observation(changed_evidence_payload, 'terrain.elevation_m')
    elevation['value'] += 0.125
    changed_evidence = project_land_evidence(changed_evidence_payload)
    third = store.persist_land_evidence_snapshot(
        changed_evidence, org='org-a', site_id=changed_evidence.identity.legacy_location_id,
    )
    assert third.id not in {first.id, second.id}
    assert third.content_hash != first.content_hash
    assert {item.boundary_version for item in store.list_land_evidence_snapshots(
        org='org-a', site_id=original.identity.legacy_location_id,
    )} == {1, 2}


def test_boundary_support_mismatch_cannot_be_persisted(snapshot_database):
    projection = project_land_evidence(saved()).model_dump(mode='json')
    projection['observations'][0]['support']['boundary_reference'] = 'wrong/boundary/99'
    with pytest.raises(LandEvidenceValidationError, match='Boundary support mismatch'):
        store.persist_land_evidence_snapshot(
            projection, org='org-a',
            site_id=projection['identity']['legacy_location_id'],
        )
