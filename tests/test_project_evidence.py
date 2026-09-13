"""Focused Project Evidence v1 contract, persistence and API verification."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, delete, func, inspect, insert, select, text, update

from backend import api, core
from backend.land_evidence import project_land_evidence
from backend import land_evidence_store
from backend import project_evidence as evidence
from synthetic_assessment import synthetic_assessment


FIXTURE = Path(__file__).parent / 'fixtures' / 'project_evidence_v1' / 'synthetic_packet.json'


@pytest.fixture
def project_database(tmp_path, monkeypatch):
    database_url = os.getenv('CRC_TEST_DATABASE_URL')
    database = create_engine(
        database_url or 'sqlite:///' + str(tmp_path / 'project-evidence.db'),
        connect_args=(
            {} if database_url
            else {'check_same_thread': False, 'timeout': 30}
        ),
        pool_pre_ping=True,
    )
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(api, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    tables = (
        core.project_intelligence_runs, core.module_runs,
        core.project_evidence_bundle_members,
        core.project_evidence_sources, core.project_evidence_claims,
        core.project_evidence_bundles, core.project_subjects,
        core.land_evidence_snapshot_origins, core.land_evidence_snapshot_links,
        core.land_evidence_snapshot_members, core.land_evidence_snapshots,
        core.assessments, core.sites,
    )
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    yield database
    api.app.dependency_overrides.clear()
    if database_url:
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    database.dispose()


@pytest.fixture
def client(project_database):
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    with TestClient(api.app) as value:
        yield value


def packet(project_subject_id: str) -> dict:
    value = json.loads(FIXTURE.read_text())
    for claim in value['claims']:
        claim['project_subject_id'] = project_subject_id
    return value


def create_project(*, org='org-a', name='Synthetic Interconnector', site_id=None):
    return evidence.create_project_subject({
        'name': name, 'project_type': 'energy_infrastructure', 'site_id': site_id,
    }, org=org)


def count(database, table) -> int:
    with database.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def counts(database) -> dict[str, int]:
    return {table.name: count(database, table) for table in (
        core.project_subjects, core.project_evidence_bundles,
        core.project_evidence_bundle_members, core.project_evidence_sources,
        core.project_evidence_claims,
        core.land_evidence_snapshots, core.land_evidence_snapshot_members,
        core.land_evidence_snapshot_links, core.land_evidence_snapshot_origins,
        core.module_runs,
    )}


def test_synthetic_packet_round_trips_and_conflicting_claims_coexist(
        project_database, client, monkeypatch):
    project_response = client.post('/api/project-subjects', json={
        'name': 'Synthetic Interconnector',
        'project_type': 'energy_infrastructure',
        'site_id': None,
    })
    assert project_response.status_code == 200, project_response.text
    project = project_response.json()
    response = client.post(
        f'/api/project-subjects/{project["id"]}/evidence-bundles',
        json=packet(project['id']),
    )
    assert response.status_code == 200, response.text
    committed = response.json()
    assert committed['evidence']['schema_version'] == 'project_evidence_v1'
    assert committed['evidence']['project_subject']['id'] == project['id']
    assert committed['source_count'] == 2 and committed['claim_count'] == 2
    claims = committed['evidence']['claims']
    assert [claim['value']['date'] for claim in claims] == [
        '2031-06-30', '2032-09-15',
    ]
    assert {claim['source_record_id'] for claim in claims} == {
        'synthetic-source-a-v1', 'synthetic-source-b-v1',
    }
    for claim in claims:
        source = next(item for item in committed['evidence']['sources']
                      if item['id'] == claim['source_record_id'])
        locator = claim['locator']
        assert source['retained_excerpt'][locator['start']:locator['end']] == locator['exact_passage']

    before = counts(project_database)
    monkeypatch.setattr(
        core, 'store_object_immutable',
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError('A read attempted immutable publication')
        ),
    )
    listed = client.get(
        f'/api/project-subjects/{project["id"]}/evidence-bundles'
    )
    read = client.get(
        f'/api/project-subjects/{project["id"]}/evidence-bundles/{committed["id"]}'
    )
    assert listed.status_code == read.status_code == 200
    assert listed.json() == [{key: committed[key] for key in (
        'id', 'org', 'project_subject_id', 'schema_version', 'content_hash',
        'manifest_sha256', 'source_count', 'claim_count',
        'land_evidence_snapshot_id', 'created',
    )}]
    assert read.json() == committed
    assert counts(project_database) == before


def test_project_identity_is_minimal_immutable_and_names_are_not_keys(project_database):
    first = create_project(name='Same display name')
    second = create_project(name='Same display name')
    assert first.id != second.id
    assert first.site_id is None and first.name == second.name
    assert evidence.get_project_subject(first.id, org='org-a') == first
    with pytest.raises(evidence.ProjectSubjectNotFound):
        evidence.get_project_subject(first.id, org='org-b')
    with pytest.raises(ValidationError):
        evidence.ProjectSubjectCreate(
            name='x', project_type='bess', site_id=None,
        )
    with pytest.raises(evidence.ProjectEvidenceValidationError):
        create_project(site_id='missing-site')


def test_project_subject_collection_is_tenant_scoped_and_read_only(
        project_database, client):
    first = create_project(name='First subject')
    second = create_project(name='Second subject')
    create_project(org='org-b', name='Other tenant subject')
    before = counts(project_database)
    response = client.get('/api/project-subjects')
    assert response.status_code == 200
    assert {item['id'] for item in response.json()} == {first.id, second.id}
    assert counts(project_database) == before


def test_legacy_project_tables_reconcile_in_place_without_losing_rows(
        tmp_path, monkeypatch):
    database = create_engine('sqlite:///' + str(tmp_path / 'legacy-projects.db'))
    core.meta.create_all(database)
    legacy = {
        'id': 'legacy-project', 'org': 'org-a', 'name': 'Legacy subject',
        'project_type': 'energy_infrastructure', 'site_id': None,
        'created': '2030-01-01T00:00:00+00:00',
    }
    legacy['content_hash'] = evidence._hash(evidence._project_content(legacy))
    with database.begin() as connection:
        connection.execute(insert(core.project_subjects).values(**legacy))
        connection.execute(insert(core.project_evidence_bundles).values(
            id='legacy-bundle', org='org-a', project_subject_id=legacy['id'],
            schema_version='project_evidence_v1', content_hash='a' * 64,
            manifest_sha256='b' * 64, manifest_key='legacy/manifest.json',
            source_count=1, claim_count=1, land_evidence_snapshot_id=None,
            created=legacy['created'],
        ))
        connection.execute(text('ALTER TABLE project_subjects RENAME TO projects'))
        for table_name in (
            'project_evidence_bundles', 'project_evidence_claims',
            'project_evidence_sources',
        ):
            connection.execute(text(
                f'ALTER TABLE {table_name} '
                'RENAME COLUMN project_subject_id TO project_id'
            ))
    monkeypatch.setattr(core, 'engine', database)
    core.init()
    inspector = inspect(database)
    assert 'projects' not in inspector.get_table_names()
    assert 'project_subjects' in inspector.get_table_names()
    for table_name in (
        'project_evidence_bundles', 'project_evidence_claims',
        'project_evidence_sources',
    ):
        columns = {column['name'] for column in inspector.get_columns(table_name)}
        assert 'project_subject_id' in columns and 'project_id' not in columns
    assert evidence.get_project_subject(legacy['id'], org='org-a').name == 'Legacy subject'
    with database.connect() as connection:
        assert connection.execute(select(core.project_evidence_bundles.c.project_subject_id)).scalar_one() == legacy['id']
    database.dispose()


def test_invalid_values_references_locators_and_time_are_rejected_before_write(
        project_database):
    project = create_project()
    invalid_values = []

    wrong_status = packet(project.id)
    wrong_status['claims'][0]['predicate'] = 'planning_status'
    wrong_status['claims'][0]['value'] = 'automatically_verified'
    invalid_values.append(wrong_status)

    missing_source = packet(project.id)
    missing_source['claims'][0]['source_record_id'] = 'does-not-exist'
    invalid_values.append(missing_source)

    broken_locator = packet(project.id)
    broken_locator['claims'][0]['locator']['exact_passage'] = 'different passage'
    invalid_values.append(broken_locator)

    occurrence_target = packet(project.id)
    occurrence_target['claims'][0]['time']['kind'] = 'reported_occurrence'
    invalid_values.append(occurrence_target)

    inferred_conclusion = packet(project.id)
    inferred_conclusion['claims'][0]['confidence_score'] = 0.9
    invalid_values.append(inferred_conclusion)

    for value in invalid_values:
        with pytest.raises((ValidationError, ValueError)):
            evidence.persist_project_evidence(project.id, value, org='org-a')
    assert count(project_database, core.project_evidence_bundles) == 0
    assert not list((core.ROOT / 'objects').rglob('*.json'))


def test_api_maps_cross_record_contract_failures_to_422(client):
    project = client.post('/api/project-subjects', json={
        'name': 'Synthetic validation project',
        'project_type': 'other_infrastructure',
    }).json()
    broken = packet(project['id'])
    broken['claims'][0]['source_record_id'] = 'missing-source'
    response = client.post(
        f'/api/project-subjects/{project["id"]}/evidence-bundles', json=broken,
    )
    assert response.status_code == 422


def test_unknown_date_and_past_future_target_keep_explicit_semantics(project_database):
    project = create_project()
    unknown = packet(project.id)
    unknown['claims'] = [deepcopy(unknown['claims'][0])]
    unknown['claims'][0]['id'] = 'unknown-target'
    unknown['claims'][0]['value'] = {
        'state': 'unknown', 'reason': 'The submitted source gives no date.',
    }
    unknown['claims'][0]['time'] = {
        'kind': 'unknown', 'effective_or_event_date': None,
    }
    unknown_record = evidence.persist_project_evidence(
        project.id, unknown, org='org-a',
    )
    unknown_claim = unknown_record.evidence.claims[0]
    assert unknown_claim.value.state == 'unknown'
    assert unknown_claim.time.kind == 'unknown'
    assert unknown_claim.time.effective_or_event_date is None

    past = packet(project.id)
    past['claims'] = [deepcopy(past['claims'][0])]
    past['claims'][0]['id'] = 'past-target-still-target'
    past['claims'][0]['value']['date'] = '2020-01-01'
    past['claims'][0]['time']['effective_or_event_date'] = '2020-01-01'
    past_record = evidence.persist_project_evidence(project.id, past, org='org-a')
    claim = past_record.evidence.claims[0]
    assert claim.time.kind == 'future_target'
    assert claim.predicate == 'target_grid_connection_date'
    assert claim.value.date.isoformat() == '2020-01-01'


def test_small_status_vocabularies_and_unknown_states_are_typed(project_database):
    project = create_project()
    value = packet(project.id)
    planning = deepcopy(value['claims'][0])
    planning.update(
        id='planning-under-review', predicate='planning_status',
        value='under_review', unknown_reason=None,
        locator={'start': 20, 'end': 32, 'exact_passage': 'under review'},
        time={'kind': 'reported_occurrence',
              'effective_or_event_date': '2030-01-12'},
    )
    construction = deepcopy(value['claims'][1])
    construction.update(
        id='construction-not-started', predicate='construction_status',
        value='not_started', unknown_reason=None,
        locator={'start': 0, 'end': 28,
                 'exact_passage': 'Construction has not started'},
        time={'kind': 'reported_occurrence',
              'effective_or_event_date': '2030-02-02'},
    )
    unknown = deepcopy(construction)
    unknown.update(
        id='construction-status-unknown', value='unknown',
        unknown_reason='The source does not establish current construction status.',
        time={'kind': 'unknown', 'effective_or_event_date': None},
    )
    value['claims'] = [planning, construction, unknown]
    committed = evidence.persist_project_evidence(project.id, value, org='org-a')
    assert {claim.predicate for claim in committed.evidence.claims} == {
        'planning_status', 'construction_status',
    }
    assert next(claim for claim in committed.evidence.claims
                if claim.id == 'construction-status-unknown').value == 'unknown'

    invalid = deepcopy(value)
    next(claim for claim in invalid['claims']
         if claim['id'] == 'construction-status-unknown')['unknown_reason'] = None
    with pytest.raises(ValidationError):
        evidence.ProjectEvidenceSubmission.model_validate(invalid)


def test_identical_sequential_and_concurrent_retries_commit_once(project_database):
    project = create_project()
    value = packet(project.id)
    first = evidence.persist_project_evidence(project.id, value, org='org-a')
    second = evidence.persist_project_evidence(project.id, value, org='org-a')
    assert second == first

    other = create_project(name='Concurrent synthetic project')
    concurrent_value = packet(other.id)
    barrier = Barrier(6)

    def commit():
        barrier.wait()
        return evidence.persist_project_evidence(
            other.id, concurrent_value, org='org-a',
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: commit(), range(6)))
    assert {result.id for result in results} == {results[0].id}
    assert len({result.created for result in results}) == 1
    assert count(project_database, core.project_evidence_bundles) == 2
    assert count(project_database, core.project_evidence_bundle_members) == 8
    assert count(project_database, core.project_evidence_sources) == 4
    assert count(project_database, core.project_evidence_claims) == 4


def test_changed_bundle_is_distinct_and_earlier_manifest_is_unchanged(project_database):
    project = create_project()
    original = evidence.persist_project_evidence(
        project.id, packet(project.id), org='org-a',
    )
    with project_database.connect() as connection:
        original_key = connection.execute(select(
            core.project_evidence_bundles.c.manifest_key,
        ).where(core.project_evidence_bundles.c.id == original.id)).scalar_one()
    original_bytes = core.load_object(original_key)

    changed = packet(project.id)
    changed['sources'][0]['title'] = 'Synthetic project notice A, corrected edition'
    changed['sources'][0]['source_version'] = 'synthetic-release-a-2'
    newer = evidence.persist_project_evidence(project.id, changed, org='org-a')
    assert newer.id != original.id
    assert newer.content_hash != original.content_hash
    assert core.load_object(original_key) == original_bytes
    assert evidence.get_project_evidence(
        project.id, original.id, org='org-a',
    ) == original


def test_explicit_correction_preserves_original_and_rejects_broken_boundaries(
        project_database):
    project = create_project()
    original = evidence.persist_project_evidence(
        project.id, packet(project.id), org='org-a',
    )
    correction = packet(project.id)
    correction['claims'] = [deepcopy(correction['claims'][0])]
    correction['claims'][0]['id'] = 'synthetic-claim-correction'
    correction['claims'][0]['supersedes_claim_id'] = 'synthetic-claim-target-a'
    corrected = evidence.persist_project_evidence(
        project.id, correction, org='org-a',
    )
    assert corrected.evidence.claims[0].supersedes_claim_id == 'synthetic-claim-target-a'
    assert evidence.get_project_evidence(
        project.id, original.id, org='org-a',
    ).evidence.claims[0].supersedes_claim_id is None

    other = create_project(name='Other project')
    cross_project = packet(other.id)
    cross_project['claims'] = [deepcopy(cross_project['claims'][0])]
    cross_project['claims'][0]['id'] = 'cross-project-correction'
    cross_project['claims'][0]['supersedes_claim_id'] = 'synthetic-claim-target-a'
    with pytest.raises(evidence.ProjectEvidenceValidationError):
        evidence.persist_project_evidence(other.id, cross_project, org='org-a')

    mismatched_predicate = packet(project.id)
    mismatched_predicate['claims'] = [deepcopy(mismatched_predicate['claims'][0])]
    mismatched_predicate['claims'][0].update(
        id='wrong-predicate-correction', predicate='planning_status',
        value='under_review', unknown_reason=None,
        time={'kind': 'reported_occurrence',
              'effective_or_event_date': '2030-01-12'},
        supersedes_claim_id='synthetic-claim-target-a',
    )
    with pytest.raises(evidence.ProjectEvidenceValidationError, match='same predicate'):
        evidence.persist_project_evidence(
            project.id, mismatched_predicate, org='org-a',
        )

    cross_tenant = create_project(org='org-b', name='Other tenant')
    tenant_packet = packet(cross_tenant.id)
    tenant_packet['claims'] = [deepcopy(tenant_packet['claims'][0])]
    tenant_packet['claims'][0]['id'] = 'cross-tenant-correction'
    tenant_packet['claims'][0]['supersedes_claim_id'] = 'synthetic-claim-target-a'
    with pytest.raises(evidence.ProjectEvidenceValidationError):
        evidence.persist_project_evidence(
            cross_tenant.id, tenant_packet, org='org-b',
        )


def test_optional_land_snapshot_is_exact_site_scoped_and_does_not_change_snapshot(
        project_database):
    payload = synthetic_assessment()
    projection = project_land_evidence(payload)
    with project_database.begin() as connection:
        connection.execute(insert(core.sites).values(
            id=projection.identity.legacy_location_id, org='org-a',
            name='Retained verification site', notes='', status='Unreviewed',
            version=projection.identity.boundary_version,
            geometry=payload['geometry'], created=payload['completed'],
        ))
    snapshot = land_evidence_store.persist_land_evidence_snapshot(
        projection, org='org-a', site_id=projection.identity.legacy_location_id,
    )
    snapshot_bytes = core.load_object(snapshot.manifest_key)
    snapshot_counts = counts(project_database)
    project = create_project(site_id=snapshot.site_id)
    value = packet(project.id)
    value['land_evidence_snapshot_id'] = snapshot.id
    committed = evidence.persist_project_evidence(project.id, value, org='org-a')
    link = committed.evidence.land_evidence_snapshot
    assert link.snapshot_id == snapshot.id
    assert link.content_hash == snapshot.content_hash
    assert link.boundary_version == snapshot.boundary_version
    assert core.load_object(snapshot.manifest_key) == snapshot_bytes
    after = counts(project_database)
    for name in (
        'land_evidence_snapshots', 'land_evidence_snapshot_members',
        'land_evidence_snapshot_links', 'land_evidence_snapshot_origins',
        'module_runs',
    ):
        assert after[name] == snapshot_counts[name]

    unlinked = create_project(name='No fabricated parcel')
    invalid = packet(unlinked.id)
    invalid['land_evidence_snapshot_id'] = snapshot.id
    with pytest.raises(evidence.ProjectEvidenceValidationError):
        evidence.persist_project_evidence(unlinked.id, invalid, org='org-a')

    with project_database.begin() as connection:
        for site_id, org in (('synthetic-other-site', 'org-a'),
                             ('synthetic-tenant-b-site', 'org-b')):
            connection.execute(insert(core.sites).values(
                id=site_id, org=org, name='Synthetic unrelated site', notes='',
                status='Unreviewed', version=1, geometry=payload['geometry'],
                created=payload['completed'],
            ))
    other_site_project = create_project(
        name='Wrong-site link', site_id='synthetic-other-site',
    )
    wrong = packet(other_site_project.id)
    wrong['land_evidence_snapshot_id'] = snapshot.id
    with pytest.raises(evidence.ProjectEvidenceValidationError, match='Project Site'):
        evidence.persist_project_evidence(other_site_project.id, wrong, org='org-a')

    tenant_b_project = create_project(
        org='org-b', name='Tenant B link', site_id='synthetic-tenant-b-site',
    )
    tenant_b_value = packet(tenant_b_project.id)
    tenant_b_value['land_evidence_snapshot_id'] = snapshot.id
    with pytest.raises(evidence.ProjectEvidenceValidationError, match='organisation'):
        evidence.persist_project_evidence(
            tenant_b_project.id, tenant_b_value, org='org-b',
        )

    with project_database.begin() as connection:
        connection.execute(update(core.land_evidence_snapshots).where(
            core.land_evidence_snapshots.c.id == snapshot.id,
        ).values(content_hash='0' * 64))
    with pytest.raises(evidence.ProjectEvidenceConflict, match='Snapshot'):
        evidence.get_project_evidence(project.id, committed.id, org='org-a')


def test_api_project_and_bundle_tenant_and_project_isolation(client):
    first = client.post('/api/project-subjects', json={
        'name': 'Private A', 'project_type': 'transport_infrastructure',
    }).json()
    second = client.post('/api/project-subjects', json={
        'name': 'Private B', 'project_type': 'water_infrastructure',
    }).json()
    committed = client.post(
        f'/api/project-subjects/{first["id"]}/evidence-bundles',
        json=packet(first['id']),
    ).json()
    assert client.get(
        f'/api/project-subjects/{second["id"]}/evidence-bundles/{committed["id"]}'
    ).status_code == 404

    api.app.dependency_overrides[api.organization] = lambda: 'org-b'
    assert client.get(
        f'/api/project-subjects/{first["id"]}'
    ).status_code == 404
    assert client.get(
        f'/api/project-subjects/{first["id"]}/evidence-bundles'
    ).status_code == 404
    assert client.post(
        f'/api/project-subjects/{first["id"]}/evidence-bundles',
        json=packet(first['id']),
    ).status_code == 404


def test_stable_claim_identity_and_catalogue_tampering_fail_closed(project_database):
    project = create_project()
    original = evidence.persist_project_evidence(
        project.id, packet(project.id), org='org-a',
    )
    reused_id = packet(project.id)
    reused_id['claims'][0]['value']['date'] = '2040-01-01'
    reused_id['claims'][0]['time']['effective_or_event_date'] = '2040-01-01'
    with pytest.raises(evidence.ProjectEvidenceConflict):
        evidence.persist_project_evidence(project.id, reused_id, org='org-a')

    reused_source_version = packet(project.id)
    reused_source_version['sources'][0]['title'] = 'Silently changed source metadata'
    with pytest.raises(evidence.ProjectEvidenceConflict):
        evidence.persist_project_evidence(
            project.id, reused_source_version, org='org-a',
        )

    with project_database.begin() as connection:
        connection.execute(update(core.project_evidence_claims).where(
            core.project_evidence_claims.c.project_subject_id == project.id,
            core.project_evidence_claims.c.claim_id == 'synthetic-claim-target-a',
        ).values(predicate='planning_status'))
    with pytest.raises(evidence.ProjectEvidenceConflict, match='claim catalogue'):
        evidence.get_project_evidence(project.id, original.id, org='org-a')
    forged_correction = packet(project.id)
    forged_correction['claims'] = [deepcopy(forged_correction['claims'][0])]
    forged_correction['claims'][0].update(
        id='forged-cross-predicate-correction', predicate='planning_status',
        value='under_review', unknown_reason=None,
        time={'kind': 'reported_occurrence',
              'effective_or_event_date': '2030-01-12'},
        supersedes_claim_id='synthetic-claim-target-a',
    )
    with pytest.raises(evidence.ProjectEvidenceConflict):
        evidence.persist_project_evidence(
            project.id, forged_correction, org='org-a',
        )
    with project_database.begin() as connection:
        connection.execute(update(core.project_evidence_claims).where(
            core.project_evidence_claims.c.project_subject_id == project.id,
            core.project_evidence_claims.c.claim_id == 'synthetic-claim-target-a',
        ).values(predicate='target_grid_connection_date'))

    with project_database.begin() as connection:
        connection.execute(update(core.project_evidence_bundle_members).where(
            core.project_evidence_bundle_members.c.bundle_id == original.id,
            core.project_evidence_bundle_members.c.kind == 'claim',
        ).values(content_hash='0' * 64))
    with pytest.raises(evidence.ProjectEvidenceConflict, match='membership'):
        evidence.get_project_evidence(project.id, original.id, org='org-a')
