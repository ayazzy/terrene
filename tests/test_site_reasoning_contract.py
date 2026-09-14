"""Public snapshot-bound Site reasoning contract and compatibility checks."""
from copy import deepcopy
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from backend import api, core
from backend.earth import fingerprint
from backend.screening_context_store import run_screening_from_snapshot
from test_wetland_module_runs import (
    commit,
    module_database,
    saved,
    table_count,
)


@pytest.fixture
def client(module_database, monkeypatch):
    monkeypatch.setattr(api, 'engine', module_database)
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    with TestClient(api.app) as test_client:
        yield test_client
    api.app.dependency_overrides.clear()


def catalogue_url(snapshot):
    return f'/api/sites/{snapshot.site_id}/reasoning-inputs'


def run_catalogue_url(snapshot):
    return f'/api/sites/{snapshot.site_id}/reasoning-runs'


def test_catalogue_is_verified_read_only_and_publishes_exact_safe_envelope(
    client, module_database,
):
    payload = saved()
    snapshot = commit(module_database, payload)
    manifest_before = core.load_object(snapshot.manifest_key)
    assessment_before = fingerprint(payload)
    counts_before = {
        table.name: table_count(module_database, table)
        for table in (
            core.land_evidence_snapshots,
            core.land_evidence_snapshot_members,
            core.land_evidence_snapshot_links,
            core.land_evidence_snapshot_origins,
            core.module_runs,
            core.assessments,
        )
    }

    response = client.get(catalogue_url(snapshot))
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    result = response.json()
    assert result['contract_version'] == 'site_reasoning_input_catalogue_v1'
    assert result['site_id'] == snapshot.site_id
    assert result['current_boundary_version'] == snapshot.boundary_version
    assert result['current_boundary_geometry_fingerprint'] == (
        snapshot.boundary_geometry_fingerprint
    )
    assert len(result['modules']) == 1
    module = result['modules'][0]
    assert module['module_id'] == 'wetland_restoration'
    assert module['module_version'] == 'wetland_restoration_v0_1'
    assert module['input_binding_version'] == 'wetland_input_binding_v1'
    assert module['model_spec']['environment_version'] is None
    assert module['model_spec']['refresh_sources'] is False
    assert module['model_spec']['signature'] == module['model_signature']

    assert len(result['snapshots']) == 1
    item = result['snapshots'][0]
    assert item['snapshot_id'] == snapshot.id
    assert item['content_hash'] == snapshot.content_hash
    assert item['current_boundary'] is True
    assert item['source_count'] == len(item['sources'])
    assert item['observation_count'] > 0
    assert item['evidence_gap_count'] > 0
    assert item['run_request'] == {
        'contract_version': 'site_reasoning_run_request_v1',
        'site_id': snapshot.site_id,
        'evidence_snapshot_id': snapshot.id,
        'evidence_content_hash': snapshot.content_hash,
        'boundary_version': snapshot.boundary_version,
        'boundary_geometry_fingerprint': snapshot.boundary_geometry_fingerprint,
        'module_id': module['module_id'],
        'module_version': module['module_version'],
        'input_binding_version': module['input_binding_version'],
        'model_signature': module['model_signature'],
        'model_spec': module['model_spec'],
    }
    serialized = json.dumps(result)
    assert 'manifest_key' not in serialized
    assert 'storage_reference' not in serialized
    assert 'raw_reference_ids' not in serialized

    assert {
        table.name: table_count(module_database, table)
        for table in (
            core.land_evidence_snapshots,
            core.land_evidence_snapshot_members,
            core.land_evidence_snapshot_links,
            core.land_evidence_snapshot_origins,
            core.module_runs,
            core.assessments,
        )
    } == counts_before
    assert core.load_object(snapshot.manifest_key) == manifest_before
    with module_database.connect() as connection:
        retained = connection.execute(select(core.assessments.c.result)).scalar_one()
    assert fingerprint(retained) == assessment_before


def test_exact_envelope_creates_one_idempotent_module_run_only(
    client, module_database,
):
    payload = saved()
    snapshot = commit(module_database, payload)
    manifest_before = core.load_object(snapshot.manifest_key)
    request = client.get(catalogue_url(snapshot)).json()['snapshots'][0]['run_request']
    url = f'/api/sites/{snapshot.site_id}/reasoning-runs'

    first = client.post(url, json=request)
    assert first.status_code == 200, first.text
    second = client.post(url, json=request)
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    run = first.json()
    assert run['site_id'] == snapshot.site_id
    assert run['boundary_version'] == snapshot.boundary_version
    assert run['evidence_snapshot_id'] == snapshot.id
    assert run['evidence_content_hash'] == snapshot.content_hash
    assert run['module_id'] == request['module_id']
    assert run['module_version'] == request['module_version']
    assert run['input_binding_version'] == request['input_binding_version']
    assert run['model_signature'] == request['model_signature']
    assert run['model_spec'] == request['model_spec']
    assert table_count(module_database, core.module_runs) == 1
    assert table_count(module_database, core.land_evidence_snapshots) == 1
    assert table_count(module_database, core.assessments) == 1
    assert core.load_object(snapshot.manifest_key) == manifest_before


def test_run_catalogue_is_read_only_safe_and_excludes_screening_context(
    client, module_database,
):
    payload = saved()
    snapshot = commit(module_database, payload)
    screening = run_screening_from_snapshot(snapshot.id, org='org-a')
    request = client.get(catalogue_url(snapshot)).json()['snapshots'][0]['run_request']
    wetland = client.post(run_catalogue_url(snapshot), json=request).json()
    counts_before = {
        table.name: table_count(module_database, table)
        for table in (core.module_runs, core.land_evidence_snapshots, core.assessments)
    }

    response = client.get(run_catalogue_url(snapshot))
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    result = response.json()
    assert result['contract_version'] == 'site_reasoning_run_catalogue_v1'
    assert result['site_id'] == snapshot.site_id
    assert result['current_boundary_version'] == snapshot.boundary_version
    assert len(result['runs']) == 1
    item = result['runs'][0]
    assert item['id'] == wetland['id']
    assert item['id'] != screening.id
    assert item['evidence_snapshot_id'] == snapshot.id
    assert item['evidence_content_hash'] == snapshot.content_hash
    assert item['current_boundary'] is True
    assert item['module_id'] == 'wetland_restoration'
    assert item['module_version'] == 'wetland_restoration_v0_1'
    assert item['input_binding_version'] == 'wetland_input_binding_v1'
    assert item['result_band'] == payload['wetland_model']['overall']['band']
    assert item['result_score'] == payload['wetland_model']['overall']['score']
    assert item['data_coverage_available'] == (
        payload['wetland_model']['evidence_summary']['data_coverage']['available']
    )
    assert item['missing_input_count'] == len(payload['wetland_model']['missing_inputs'])
    assert set(item) == {
        'id', 'content_hash', 'site_id', 'boundary_version',
        'evidence_snapshot_id', 'evidence_content_hash', 'evidence_as_of',
        'current_boundary', 'module_id', 'module_version',
        'input_binding_version', 'model_signature', 'result_band',
        'result_score', 'data_coverage_available', 'data_coverage_required',
        'missing_input_count', 'review_flag_count', 'synthetic', 'created',
        'completed',
    }
    assert {
        table.name: table_count(module_database, table)
        for table in (core.module_runs, core.land_evidence_snapshots, core.assessments)
    } == counts_before


def test_empty_run_catalogue_is_valid_and_tenant_scoped(client, module_database):
    snapshot = commit(module_database, saved())
    response = client.get(run_catalogue_url(snapshot))
    assert response.status_code == 200
    assert response.json()['runs'] == []

    api.app.dependency_overrides[api.organization] = lambda: 'org-b'
    response = client.get(run_catalogue_url(snapshot))
    assert response.status_code == 404
    assert response.json()['detail'] == 'Record not found'


@pytest.mark.parametrize('change', ['content_hash', 'boundary', 'model_spec'])
def test_stale_or_contradictory_envelope_fails_closed(
    client, module_database, change,
):
    snapshot = commit(module_database, saved())
    request = client.get(catalogue_url(snapshot)).json()['snapshots'][0]['run_request']
    if change == 'content_hash':
        request['evidence_content_hash'] = '0' * 64
    elif change == 'boundary':
        request['boundary_version'] += 1
    else:
        request['model_spec']['config']['high_threshold'] = 66
    response = client.post(
        f'/api/sites/{snapshot.site_id}/reasoning-runs', json=request,
    )
    assert response.status_code == 409
    assert 'published immutable snapshot and model envelope' in response.json()['detail']
    assert table_count(module_database, core.module_runs) == 0


def test_request_is_strict_and_snapshot_ownership_does_not_leak(
    client, module_database,
):
    snapshot = commit(module_database, saved())
    request = client.get(catalogue_url(snapshot)).json()['snapshots'][0]['run_request']
    request['unexpected'] = True
    assert client.post(
        f'/api/sites/{snapshot.site_id}/reasoning-runs', json=request,
    ).status_code == 422

    other_site_id = 'other-site'
    with module_database.begin() as connection:
        connection.execute(insert(core.sites).values(
            id=other_site_id, org='org-a', name='Other Site', status='Unreviewed',
            version=1, geometry=saved()['geometry'], created=core.now(),
        ))
    request.pop('unexpected')
    request['site_id'] = other_site_id
    response = client.post(
        f'/api/sites/{other_site_id}/reasoning-runs', json=request,
    )
    assert response.status_code == 404
    assert response.json()['detail'] == 'Record not found'
    assert table_count(module_database, core.module_runs) == 0

    api.app.dependency_overrides[api.organization] = lambda: 'org-b'
    assert client.get(catalogue_url(snapshot)).status_code == 404
    assert client.post(
        f'/api/sites/{snapshot.site_id}/reasoning-runs', json=request,
    ).status_code == 404


def test_historical_boundary_is_explicit_and_remains_runnable(
    client, module_database,
):
    payload = saved()
    snapshot = commit(module_database, payload)
    core.store_object(
        f'org-a/boundaries/{snapshot.site_id}/{snapshot.boundary_version}.json',
        json.dumps({
            'type': 'Feature',
            'properties': {'historical': True},
            'geometry': payload['geometry'],
        }),
    )
    current_geometry = deepcopy(payload['geometry'])
    for position in current_geometry['coordinates'][0][0]:
        position[0] += .00001
    with module_database.begin() as connection:
        connection.execute(update(core.sites).where(
            core.sites.c.id == snapshot.site_id,
        ).values(version=snapshot.boundary_version + 1, geometry=current_geometry))

    result = client.get(catalogue_url(snapshot)).json()
    assert result['current_boundary_version'] == snapshot.boundary_version + 1
    assert result['snapshots'][0]['current_boundary'] is False
    request = result['snapshots'][0]['run_request']
    response = client.post(
        f'/api/sites/{snapshot.site_id}/reasoning-runs', json=request,
    )
    assert response.status_code == 200, response.text
    assert response.json()['boundary_version'] == snapshot.boundary_version
    runs = client.get(run_catalogue_url(snapshot)).json()['runs']
    assert len(runs) == 1
    assert runs[0]['current_boundary'] is False


def test_corrupt_module_run_returns_sanitized_catalogue_failure(
    client, module_database,
):
    snapshot = commit(module_database, saved())
    request = client.get(catalogue_url(snapshot)).json()['snapshots'][0]['run_request']
    run = client.post(run_catalogue_url(snapshot), json=request).json()
    with module_database.begin() as connection:
        connection.execute(update(core.module_runs).where(
            core.module_runs.c.id == run['id'],
        ).values(result={**run['result'], 'signature': 'corrupt'}))
    response = client.get(run_catalogue_url(snapshot))
    assert response.status_code == 500
    assert response.json()['detail'].startswith(
        'Site reasoning integrity check failed'
    )
    assert 'corrupt' not in response.text


def test_corrupt_committed_snapshot_returns_sanitized_integrity_failure(
    client, module_database,
):
    snapshot = commit(module_database, saved())
    (core.ROOT / 'objects' / snapshot.manifest_key).write_text('{}')
    response = client.get(catalogue_url(snapshot))
    assert response.status_code == 500
    assert response.json()['detail'].startswith('Site reasoning integrity check failed')
    assert snapshot.manifest_key not in response.text
    assert table_count(module_database, core.module_runs) == 0
