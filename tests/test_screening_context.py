"""Screening v1 product path, immutable history and retained-source semantics."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from backend import api, core, module_runs
from backend.earth import fingerprint
from backend import land_evidence_store as store
from backend.land_evidence import project_land_evidence
from backend.screening_context import (
    BINDING_VERSION, MODULE_ID, MODULE_VERSION, ScreeningConfig, ScreeningResult,
    build_screening_context, screening_spec,
)
from backend.wetland import run_wetland
from backend.wetland_binding import bind_wetland_input
from backend.screening_context_store import (
    get_screening_run, prepare_screening_context, read_assessment_context,
    run_screening_from_snapshot,
)
from test_wetland_module_runs import (
    module_database, insert_assessment, model_spec_from, table_count, legacy_observation,
)

REAL_ROOT = Path(__file__).parents[1] / 'data/verification/england-real-openmap-local-2026-04'


def payload(name='port-meadow', suffix='after'):
    return json.loads((REAL_ROOT / f'{name}-{suffix}.json').read_text())


@pytest.fixture
def client(module_database, monkeypatch):
    monkeypatch.setattr(api, 'engine', module_database)
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    with TestClient(api.app) as client:
        yield client
    api.app.dependency_overrides.clear()


def saved(module_database, name='port-meadow', assessment_id='assessment', suffix='after'):
    p = payload(name, suffix)
    insert_assessment(module_database, p, assessment_id=assessment_id)
    return p


def facts(run):
    return [f for g in run.result['groups'] for f in g['facts']]


def gaps(run):
    return [g for group in run.result['groups'] for g in group['gaps']]


def test_explicit_action_and_read_only_discovery_reuse_exact_run(client, module_database):
    original = saved(module_database)
    url = '/api/assessments/assessment/screening-context'
    assert client.get(url).json() is None
    assert client.get(url + '/report').status_code == 409
    assert table_count(module_database, core.land_evidence_snapshots) == 0
    assert table_count(module_database, core.module_runs) == 0
    first = client.post(url)
    assert first.status_code == 200, first.text
    second = client.post(url)
    assert second.json() == first.json() == client.get(url).json()
    run = first.json()
    assert client.get('/api/screening-context-runs/' + run['id']).json() == run
    assert table_count(module_database, core.module_runs) == 1
    snapshot = store.create_snapshot_from_legacy_assessment('assessment', org='org-a')
    assert snapshot.id == run['evidence_snapshot_id']
    assert run['result']['boundary_geometry_fingerprint'] == fingerprint(original['geometry'])
    with module_database.connect() as c:
        assert c.execute(select(core.assessments.c.result)).scalar_one() == original


@pytest.mark.parametrize('state,result_kind', [
    ('queued', 'saved'), ('running', 'saved'), ('failed', 'saved'),
    ('completed', 'none'), ('partial', 'none'), ('completed', 'historical'),
])
def test_unusable_assessments_cannot_prepare(client, module_database, state, result_kind):
    original = saved(module_database)
    result = original if result_kind == 'saved' else None if result_kind == 'none' else {'old': True}
    with module_database.begin() as c:
        c.execute(update(core.assessments).values(state=state, result=result))
    response = client.post('/api/assessments/assessment/screening-context')
    assert response.status_code == 409
    assert table_count(module_database, core.land_evidence_snapshots) == 0
    assert table_count(module_database, core.module_runs) == 0


def test_unsupported_historical_discovery_is_explicit_and_read_only(client, module_database):
    saved(module_database)
    with module_database.begin() as connection:
        connection.execute(update(core.assessments).values(result={'old': True}))
    response = client.get('/api/assessments/assessment/screening-context')
    assert response.status_code == 409
    assert 'predates supported land evidence' in response.json()['detail']
    assert table_count(module_database, core.land_evidence_snapshots) == 0
    assert table_count(module_database, core.land_evidence_snapshot_origins) == 0
    assert table_count(module_database, core.module_runs) == 0
    with module_database.connect() as connection:
        assert connection.execute(select(core.assessments.c.result)).scalar_one() == {'old': True}


def test_partial_terminal_assessment_with_saved_evidence_is_usable(client, module_database):
    saved(module_database)
    with module_database.begin() as c:
        c.execute(update(core.assessments).values(state='partial'))
    assert client.post('/api/assessments/assessment/screening-context').status_code == 200


def test_wrong_organization_and_missing_records_are_not_found(client, module_database, monkeypatch):
    saved(module_database)
    run = client.post('/api/assessments/assessment/screening-context').json()
    api.app.dependency_overrides[api.organization] = lambda: 'org-b'
    for method, path in [('post', '/api/assessments/assessment/screening-context'),
                         ('get', '/api/assessments/assessment/screening-context'),
                         ('get', '/api/assessments/assessment/screening-context/report'),
                         ('get', '/api/screening-context-runs/' + run['id'])]:
        assert getattr(client, method)(path).status_code == 404
    api.app.dependency_overrides.clear()
    monkeypatch.setenv('CRC_ENV', 'production')
    assert client.post('/api/assessments/assessment/screening-context').status_code == 401


def test_changed_evidence_boundary_rules_module_and_config_have_distinct_identities(module_database):
    p = saved(module_database)
    first = prepare_screening_context('assessment', org='org-a')
    changed = deepcopy(p)
    legacy_observation(changed, 'terrain.elevation_m')['value'] += .125
    snapshot = store.persist_land_evidence_snapshot(project_land_evidence(changed), org='org-a', site_id=first.site_id)
    second = run_screening_from_snapshot(snapshot.id, org='org-a')
    changed_boundary = deepcopy(p)
    changed_boundary['environmental_state']['boundary_version'] += 1
    changed_boundary['boundary_version'] = 2
    state = changed_boundary['environmental_state']
    for domain in state['normalized'].values():
        for observations in domain.values():
            for observation in observations:
                observation['spatial']['geometry_or_cell_reference'] = state['location_id'] + '/boundary/2'
    for observation in state['derived'].values():
        observation['spatial']['geometry_or_cell_reference'] = state['location_id'] + '/boundary/2'
    for finding in changed_boundary['findings']:
        finding['boundary_version'] = 2
    projection = project_land_evidence(changed_boundary)
    snapshot2 = store.persist_land_evidence_snapshot(projection, org='org-a', site_id=first.site_id)
    third = run_screening_from_snapshot(snapshot2.id, org='org-a')
    configured = run_screening_from_snapshot(first.evidence_snapshot_id, org='org-a',
                                             config=ScreeningConfig(include_cross_source_context=False))
    assert configured.result['cross_source_contexts'] == []
    assert len({first.id, second.id, third.id, configured.id}) == 4
    kwargs = dict(org='org-a', evidence_snapshot_id=first.evidence_snapshot_id, module_id=MODULE_ID,
                  module_version=MODULE_VERSION, input_binding_version=BINDING_VERSION,
                  model_signature=first.model_signature)
    assert module_runs.module_run_identity(**{**kwargs, 'module_version': 'site_screening_context_v2'}) != first.id
    assert module_runs.module_run_identity(**{**kwargs, 'input_binding_version': 'screening_context_binding_v2'}) != first.id
    assert get_screening_run(first.id, org='org-a') == first


def test_historical_snapshot_origin_and_wetland_runs_remain_exact(module_database):
    old = saved(module_database, suffix='pre-built', assessment_id='old')
    snapshot = store.create_snapshot_from_legacy_assessment('old', org='org-a')
    manifest = core.load_object(snapshot.manifest_key)
    wetland = module_runs.run_wetland_from_snapshot(snapshot.id, org='org-a', spec=model_spec_from(old))
    saved(module_database, assessment_id='new')
    with module_database.begin() as c:
        c.execute(update(core.sites).values(version=2))
    historical = prepare_screening_context('old', org='org-a')
    current = prepare_screening_context('new', org='org-a')
    assert historical.evidence_snapshot_id == snapshot.id != current.evidence_snapshot_id
    assert historical.boundary_version == 1
    assert core.load_object(snapshot.manifest_key) == manifest
    assert module_runs.get_module_run(wetland.id, org='org-a') == wetland
    assert wetland.result == run_wetland(bind_wetland_input(project_land_evidence(old), old['geometry']), model_spec_from(old))
    assert read_assessment_context('old', org='org-a') == historical
    assert any('predates built-world' in x for x in historical.result['limitations'])


def test_known_zero_partial_search_and_source_semantics_are_preserved(module_database):
    saved(module_database, 'redbridge')
    run = prepare_screening_context('assessment', org='org-a')
    by_definition = {f['definition_id']: f for f in facts(run)}
    built = by_definition['built.building.mapped_overlap_fraction']
    assert built['known_zero'] and built['value']['value'] == 0
    assert any('does not prove real-world absence' in x['text'] for x in run.result['mapped_zero_qualifications'])
    assert not any(f['definition_id'].startswith('transport.') and f['definition_id'].endswith('.distance_min') for f in facts(run))
    assert any(g['reason_code'] == 'partial_search_coverage' and g['state'] == 'partial_coverage' for g in gaps(run))
    wc = by_definition['built.mapped_built_up_fraction']
    assert wc['value']['value'] > 0
    assert wc['id'] != built['id']
    ctx = next(x for x in run.result['cross_source_contexts'] if x['id'] == 'built_semantics')
    assert {wc['id'], built['id']} <= set(ctx['references']['observation_ids'])
    assert 'denominators' in ctx['text']
    phi = by_definition['ecology.priority_habitat.any_mapped_overlap_fraction']
    assert phi['value']['value'] > 0
    assert 'inventory' in phi['limitations'].lower()
    assert phi['references']['source_feature_reference_ids']
    assert all('blocker' not in q['text'] for q in run.result['review_questions'])


def test_all_retained_oxford_cases_are_offline_deterministic_traceable_and_non_scoring(module_database, monkeypatch):
    import socket
    def deny(*args, **kwargs):
        raise AssertionError('Module attempted network IO')
    # PostgreSQL itself needs sockets; block provider requests in both database modes.
    import httpx
    monkeypatch.setattr(httpx, 'get', deny)
    if module_database.dialect.name == 'sqlite':
        monkeypatch.setattr(socket, 'create_connection', deny)
    paths = sorted(REAL_ROOT.glob('*-after.json'))
    assert len(paths) == 12
    for path in paths:
        p = json.loads(path.read_text())
        insert_assessment(module_database, p, assessment_id=path.stem)
        # Compare to the pre-screening snapshot execution, including existing legacy gap semantics.
        snapshot = store.create_snapshot_from_legacy_assessment(path.stem, org='org-a')
        baseline = module_runs.run_wetland_from_snapshot(snapshot.id, org='org-a', spec=model_spec_from(p))
        run = prepare_screening_context(path.stem, org='org-a')
        assert run == prepare_screening_context(path.stem, org='org-a')
        projection = store.load_land_evidence_snapshot(run.evidence_snapshot_id, org='org-a')
        assert {f['id'] for f in facts(run)} == {o.id for o in projection.observations}
        assert {g['id'] for g in gaps(run)} == {g.id for g in projection.gaps}
        assert run.result['objects'] == [o.model_dump(mode='json') for o in sorted(projection.objects, key=lambda o: o.id)]
        for f in facts(run):
            original = next(o for o in projection.observations if o.id == f['id'])
            assert f['value'] == original.value.model_dump(mode='json')
            assert f['support'] == original.support.model_dump(mode='json')
        for gap in gaps(run):
            assert gap == next(g for g in projection.gaps if g.id == gap['id']).model_dump(mode='json')
        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()
        assert not (keys(run.result) & {'score', 'rank', 'ranking', 'confidence', 'recommendation', 'decision', 'storage_reference', 'manifest_key', 'assets'})
        wetland = module_runs.run_wetland_from_snapshot(run.evidence_snapshot_id, org='org-a', spec=model_spec_from(p))
        assert wetland == baseline
        assert run.completed >= run.created


def test_corruption_fails_and_never_overwrites_or_leaks_internal_locations(client, module_database):
    saved(module_database)
    url = '/api/assessments/assessment/screening-context'
    run = client.post(url).json()
    with module_database.begin() as c:
        c.execute(update(core.module_runs).values(result={**run['result'], 'signature': 'corrupt'}))
    assert client.get(url).status_code == 500
    assert client.post(url).status_code == 500
    with module_database.connect() as c:
        assert c.execute(select(core.module_runs.c.result)).scalar_one()['signature'] == 'corrupt'
    snapshot = store.get_land_evidence_snapshot(run['evidence_snapshot_id'], org='org-a')
    (core.ROOT / 'objects' / snapshot.manifest_key).write_bytes(b'{}')
    response = client.get(url)
    assert response.status_code == 500
    assert snapshot.manifest_key not in response.text


def test_result_contract_rejects_forged_refs_extra_scoring_and_partial_minimum(module_database):
    saved(module_database, 'oxford-station')
    run = prepare_screening_context('assessment', org='org-a')
    with pytest.raises(ValueError):
        ScreeningResult.model_validate({**run.result, 'score': 0})
    forged = deepcopy(run.result)
    forged['review_questions'][0]['references']['observation_ids'] = ['invented']
    with pytest.raises(ValueError, match='Unresolved'):
        ScreeningResult.model_validate(forged)
    partial = deepcopy(run.result)
    f = next(f for g in partial['groups'] for f in g['facts'] if f['definition_id'] == 'transport.railway_track.distance_min')
    f['support'].update(coverage_status='partial', coverage_fraction=.5)
    with pytest.raises(ValueError, match='complete search'):
        ScreeningResult.model_validate(partial)


def test_html_export_is_escaped_self_contained_and_separates_mutable_review(client, module_database):
    p = saved(module_database, 'westgate')
    url = '/api/assessments/assessment/screening-context'
    run = client.post(url).json()
    with module_database.begin() as c:
        c.execute(update(core.assessments).values(site_name='<script>alert("site")</script>'))
        c.execute(update(core.sites).values(status='Hold', version=2))
    response = client.get(url + '/report')
    assert response.status_code == 200, response.text
    body = response.text
    assert '<script' not in body and '&lt;script&gt;' in body
    assert 'Current team review status at export' in body and 'Hold' in body
    assert 'Boundary v1' in body and 'current site boundary v2' in body
    assert 'not the historical review status' in body
    assert run['id'] in body and run['evidence_snapshot_id'] in body
    assert 'src=' not in body and '<link' not in body
    assert 'storage_reference' not in body and 'manifest_key' not in body
    projection = project_land_evidence(p)
    assert all(r.storage_reference not in body for r in projection.raw_references if r.storage_reference)
    assert all(o.id in body for o in projection.observations)
    assert client.get(url).json() == run
    assert response.headers['cache-control'] == 'no-store'
