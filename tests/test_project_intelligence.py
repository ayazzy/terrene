"""Project Evidence binding, deterministic reasoning and run persistence tests."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, update

from backend import api, core
from backend import project_evidence as evidence
from backend import project_evidence_binding as binding
from backend import project_intelligence as intelligence
from backend import project_intelligence_store as store


@pytest.fixture
def project_intelligence_database(tmp_path, monkeypatch):
    database = create_engine(
        'sqlite:///' + str(tmp_path / 'project-intelligence.db'),
        connect_args={'check_same_thread': False, 'timeout': 30},
        pool_pre_ping=True,
    )
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(api, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    yield database
    api.app.dependency_overrides.clear()
    database.dispose()


@pytest.fixture
def client(project_intelligence_database):
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    with TestClient(api.app) as value:
        yield value


def subject(*, org='org-a', name='Synthetic Northfield BESS'):
    return evidence.create_project_subject({
        'name': name, 'project_type': 'energy_infrastructure', 'site_id': None,
    }, org=org)


def source(source_id: str, excerpt: str, *, recorded: str) -> dict:
    return {
        'id': source_id, 'source_version': source_id + '-release-1',
        'publisher': 'Synthetic project bulletin',
        'title': 'Synthetic evidence ' + source_id,
        'reference': 'https://example.invalid/' + source_id,
        'published_at': recorded, 'recorded_at': recorded,
        'retained_excerpt': excerpt,
        'content_hash': sha256(excerpt.encode()).hexdigest(),
        'entry_method': 'human_submitted_structured',
    }


def claim(subject_id: str, claim_id: str, predicate: str, value, excerpt: str,
          passage: str, source_id: str, *, event_date: str | None,
          time_kind='reported_occurrence', supersedes=None, phase=None) -> dict:
    start = excerpt.index(passage)
    return {
        'id': claim_id, 'project_subject_id': subject_id, 'phase': phase,
        'predicate': predicate, 'value': value,
        'source_record_id': source_id,
        'locator': {'start': start, 'end': start + len(passage),
                    'exact_passage': passage},
        'time': {'kind': time_kind, 'effective_or_event_date': event_date},
        'supersedes_claim_id': supersedes,
    }


def commit_bundle(subject_id: str, suffix: str, *, planning=None,
                  construction=None, target=None, supersedes=None,
                  recorded='2030-02-02T11:00:00Z', org='org-a'):
    phrases = []
    if planning is not None:
        phrases.append('Planning status is ' + planning + '.')
    if construction is not None:
        phrases.append('Construction status is ' + construction + '.')
    if target is not None:
        phrases.append('Target grid connection is ' + target + '.')
    excerpt = ' '.join(phrases)
    source_id = 'source-' + suffix
    claims = []
    if planning is not None:
        claims.append(claim(
            subject_id, 'planning-' + suffix, 'planning_status', planning,
            excerpt, planning, source_id, event_date='2030-01-12',
            phase='planning',
        ))
    if construction is not None:
        claims.append(claim(
            subject_id, 'construction-' + suffix, 'construction_status',
            construction, excerpt, construction, source_id,
            event_date='2030-02-01', phase='construction',
        ))
    if target is not None:
        claims.append(claim(
            subject_id, 'target-' + suffix, 'target_grid_connection_date',
            {'state': 'known', 'date': target}, excerpt, target, source_id,
            event_date=target, time_kind='future_target',
            supersedes=supersedes, phase='pre_construction',
        ))
    return evidence.persist_project_evidence(subject_id, {
        'schema_version': 'project_evidence_v1',
        'land_evidence_snapshot_id': None,
        'sources': [source(source_id, excerpt, recorded=recorded)],
        'claims': claims,
    }, org=org)


def scenario(subject_id: str):
    first = commit_bundle(
        subject_id, 'a', planning='approved',
        construction='under_construction', target='2031-06-30',
    )
    second = commit_bundle(
        subject_id, 'b', construction='under_construction',
        target='2032-09-15', recorded='2030-03-02T11:00:00Z',
    )
    correction = commit_bundle(
        subject_id, 'c', target='2032-09-15', supersedes='target-a',
        recorded='2030-04-02T11:00:00Z',
    )
    return first, second, correction


def table_count(database, table):
    with database.connect() as connection:
        return connection.execute(select(func.count()).select_from(table)).scalar_one()


def test_binding_is_explicit_canonical_closed_and_read_only(project_intelligence_database):
    item = subject()
    first, second, correction = scenario(item.id)
    before = table_count(project_intelligence_database, core.project_intelligence_runs)
    one = binding.load_project_evidence_binding(
        item.id, [first.id, second.id], org='org-a',
    )
    reversed_order = binding.load_project_evidence_binding(
        item.id, [second.id, first.id], org='org-a',
    )
    assert reversed_order == one
    assert one.active_claim_ids == sorted(one.active_claim_ids)
    assert {'target-a', 'target-b'} <= set(one.active_claim_ids)
    assert table_count(project_intelligence_database, core.project_intelligence_runs) == before
    with pytest.raises(ValueError, match='unique'):
        binding.load_project_evidence_binding(
            item.id, [first.id, first.id], org='org-a',
        )
    with pytest.raises(binding.ProjectEvidenceBindingError, match='ancestry'):
        binding.load_project_evidence_binding(
            item.id, [second.id, correction.id], org='org-a',
        )
    corrected = binding.load_project_evidence_binding(
        item.id, [first.id, second.id, correction.id], org='org-a',
    )
    assert 'target-a' in corrected.superseded_claim_ids
    assert 'target-c' in corrected.active_claim_ids
    assert corrected.id != one.id


def test_binding_rejects_a_tampered_immutable_manifest(project_intelligence_database):
    item = subject()
    first, _, _ = scenario(item.id)
    with project_intelligence_database.connect() as connection:
        manifest_key = connection.execute(select(
            core.project_evidence_bundles.c.manifest_key,
        ).where(core.project_evidence_bundles.c.id == first.id)).scalar_one()
    manifest = core.ROOT / 'objects' / manifest_key
    manifest.write_bytes(b'{"tampered":true}')
    with pytest.raises(evidence.ProjectEvidenceConflict, match='checksum'):
        binding.load_project_evidence_binding(item.id, [first.id], org='org-a')


def test_binding_rejects_a_cyclic_correction_graph(project_intelligence_database):
    item = subject()
    first, second, _ = scenario(item.id)
    value = binding.load_project_evidence_binding(
        item.id, [first.id, second.id], org='org-a',
    ).model_dump(mode='json')
    target_a = next(entry for entry in value['claims'] if entry['claim']['id'] == 'target-a')
    target_b = next(entry for entry in value['claims'] if entry['claim']['id'] == 'target-b')
    target_a['claim']['supersedes_claim_id'] = 'target-b'
    target_b['claim']['supersedes_claim_id'] = 'target-a'
    target_a['claim_hash'] = binding._hash(target_a['claim'])
    target_b['claim_hash'] = binding._hash(target_b['claim'])
    value['active_claim_ids'] = [
        entry['claim']['id'] for entry in value['claims']
        if entry['claim']['id'] not in {'target-a', 'target-b'}
    ]
    value['superseded_claim_ids'] = sorted(
        ['target-a', 'target-b']
    )
    content_hash = binding._hash(binding._content_document(value))
    value['content_hash'] = content_hash
    value['id'] = binding.binding_identity(
        org='org-a', project_subject_id=item.id, content_hash=content_hash,
    )
    with pytest.raises(binding.ProjectEvidenceBindingError, match='cycle'):
        binding.verify_project_evidence_binding(value)


def test_pure_reasoning_preserves_conflict_and_correction(project_intelligence_database):
    item = subject()
    first, second, correction = scenario(item.id)
    original_binding = binding.load_project_evidence_binding(
        item.id, [first.id, second.id], org='org-a',
    )
    original = intelligence.build_project_intelligence(original_binding)
    assert original.reported_stage.value == 'construction'
    assert original.reported_stage.evidence_state == 'supported'
    assert original.grid_connection_target.evidence_state == 'conflicting'
    assert {group.predicate for group in original.conflicts} == {
        'target_grid_connection_date',
    }

    corrected_binding = binding.load_project_evidence_binding(
        item.id, [first.id, second.id, correction.id], org='org-a',
    )
    corrected = intelligence.build_project_intelligence(corrected_binding)
    assert corrected.grid_connection_target.evidence_state == 'supported'
    assert [target.date.isoformat() for target in corrected.grid_connection_target.targets] == [
        '2032-09-15',
    ]
    assert intelligence.build_project_intelligence(original_binding) == original


@pytest.mark.parametrize('planning,construction,stage,state', [
    (None, 'paused', 'construction', 'supported'),
    ('refused', None, 'unclear', 'insufficient_evidence'),
    (None, 'cancelled', 'unclear', 'insufficient_evidence'),
    ('submitted', 'completed', 'construction_complete', 'supported'),
])
def test_stage_rules_do_not_invent_lifecycle_states(
    project_intelligence_database, planning, construction, stage, state,
):
    item = subject(name='Synthetic ' + str((planning, construction)))
    bundle = commit_bundle(
        item.id, 'stage-' + (planning or construction), planning=planning,
        construction=construction, target='2032-01-01',
    )
    result = intelligence.build_project_intelligence(
        binding.load_project_evidence_binding(item.id, [bundle.id], org='org-a')
    )
    assert result.reported_stage.value == stage
    assert result.reported_stage.evidence_state == state


def test_incompatible_construction_stages_remain_conflicting(
        project_intelligence_database):
    item = subject()
    not_started = commit_bundle(
        item.id, 'not-started', planning='approved', construction='not_started',
    )
    underway = commit_bundle(
        item.id, 'underway', construction='under_construction',
        recorded='2030-03-02T11:00:00Z',
    )
    result = intelligence.build_project_intelligence(
        binding.load_project_evidence_binding(
            item.id, [not_started.id, underway.id], org='org-a',
        )
    )
    assert result.construction_status.evidence_state == 'conflicting'
    assert result.reported_stage.value == 'unclear'
    assert result.reported_stage.evidence_state == 'conflicting'
    conflict = next(group for group in result.conflicts
                    if group.predicate == 'construction_status')
    assert {claim_id for value in conflict.values for claim_id in value.claim_ids} == {
        'construction-not-started', 'construction-underway',
    }


def test_elapsed_target_uses_evidence_as_of_not_wall_clock(project_intelligence_database):
    item = subject()
    bundle = commit_bundle(
        item.id, 'elapsed', target='2029-12-31',
        recorded='2030-01-01T00:00:00Z',
    )
    result = intelligence.build_project_intelligence(
        binding.load_project_evidence_binding(item.id, [bundle.id], org='org-a')
    )
    assert result.grid_connection_target.targets[0].temporal_state == 'elapsed_unverified'
    assert 'elapsed_grid_target_unverified' in {
        question.code for question in result.unresolved_questions
    }
    assert result.reported_stage.evidence_state == 'insufficient_evidence'


def test_missing_statuses_stay_insufficient_and_trace_to_retained_source(
        project_intelligence_database):
    item = subject()
    bundle = commit_bundle(item.id, 'unknowns', target='2032-01-01')
    value = binding.load_project_evidence_binding(item.id, [bundle.id], org='org-a')
    result = intelligence.build_project_intelligence(value)
    assert result.planning_status.evidence_state == 'insufficient_evidence'
    assert result.construction_status.evidence_state == 'insufficient_evidence'
    assert {question.code for question in result.unresolved_questions} >= {
        'missing_planning_status', 'missing_construction_status',
    }
    reference = result.grid_connection_target.references[0]
    bound_claim = next(entry for entry in value.claims
                       if entry.claim.id == reference.claim_id)
    source = next(entry for entry in value.sources
                  if entry.source.id == reference.source_record_id)
    assert reference.source_version == source.source.source_version
    assert reference.exact_passage == bound_claim.claim.locator.exact_passage


def test_run_api_is_idempotent_historical_and_read_only(
    project_intelligence_database, client,
):
    item = subject()
    first, second, correction = scenario(item.id)
    request = {'evidence_bundle_ids': [second.id, first.id]}
    created = client.post(
        f'/api/project-subjects/{item.id}/intelligence-runs', json=request,
    )
    assert created.status_code == 200, created.text
    run = created.json()
    repeated = client.post(
        f'/api/project-subjects/{item.id}/intelligence-runs', json={
            'evidence_bundle_ids': [first.id, second.id],
        },
    )
    assert repeated.status_code == 200
    assert repeated.json() == run
    before = table_count(project_intelligence_database, core.project_intelligence_runs)
    listed = client.get(f'/api/project-subjects/{item.id}/intelligence-runs')
    read = client.get(f'/api/project-intelligence-runs/{run["id"]}')
    assert listed.status_code == read.status_code == 200
    assert listed.json()[0]['id'] == run['id']
    assert read.json() == run
    assert table_count(project_intelligence_database, core.project_intelligence_runs) == before

    newer = client.post(
        f'/api/project-subjects/{item.id}/intelligence-runs', json={
            'evidence_bundle_ids': [first.id, second.id, correction.id],
        },
    )
    assert newer.status_code == 200 and newer.json()['id'] != run['id']
    assert client.get(
        f'/api/project-intelligence-runs/{run["id"]}'
    ).json() == run


def test_v1_history_uses_its_registered_implementation_not_the_current_pointer(
        project_intelligence_database, monkeypatch):
    item = subject()
    first, _, _ = scenario(item.id)
    run = store.run_project_intelligence(item.id, {
        'evidence_bundle_ids': [first.id],
    }, org='org-a')
    different_version_id = store.project_intelligence_run_identity(
        org='org-a', project_subject_id=item.id,
        evidence_binding_id=run.evidence_binding_id,
        module_id=run.module_id, module_version='project_intelligence_v2',
        input_binding_version=run.input_binding_version,
        model_signature=run.model_signature,
    )
    assert different_version_id != run.id
    monkeypatch.setattr(store, 'CURRENT_IMPLEMENTATION_KEY', (
        store.MODULE_ID, 'project_intelligence_v2', store.BINDING_VERSION,
    ))
    assert store.get_project_intelligence_run(run.id, org='org-a') == run


def test_concurrent_identical_runs_reuse_one_winner(project_intelligence_database):
    item = subject()
    first, second, _ = scenario(item.id)
    barrier = Barrier(5)

    def execute():
        barrier.wait()
        return store.run_project_intelligence(item.id, {
            'evidence_bundle_ids': [first.id, second.id],
        }, org='org-a')

    with ThreadPoolExecutor(max_workers=5) as pool:
        runs = list(pool.map(lambda _: execute(), range(5)))
    assert len({run.id for run in runs}) == 1
    assert len({run.created for run in runs}) == 1
    assert table_count(project_intelligence_database, core.project_intelligence_runs) == 1


def test_tenant_isolation_invalid_selection_and_tampering_fail_closed(
    project_intelligence_database, client,
):
    item = subject()
    first, _, _ = scenario(item.id)
    other = subject(org='org-b', name='Other tenant subject')
    with pytest.raises(Exception):
        binding.load_project_evidence_binding(
            other.id, [first.id], org='org-b',
        )
    duplicate = client.post(
        f'/api/project-subjects/{item.id}/intelligence-runs', json={
            'evidence_bundle_ids': [first.id, first.id],
        },
    )
    assert duplicate.status_code == 422
    run = store.run_project_intelligence(item.id, {
        'evidence_bundle_ids': [first.id],
    }, org='org-a')
    with project_intelligence_database.begin() as connection:
        connection.execute(update(core.project_intelligence_runs).where(
            core.project_intelligence_runs.c.id == run.id,
        ).values(result={'forged': True}))
    response = client.get(f'/api/project-intelligence-runs/{run.id}')
    assert response.status_code == 409
    assert 'manifest_key' not in response.text
