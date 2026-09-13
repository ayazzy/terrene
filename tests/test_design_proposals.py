"""Sprint 001 acceptance: versioned infrastructure design proposals."""
from copy import deepcopy
import json
import os

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, mapping, shape
from sqlalchemy import create_engine, delete, func, select, update

from backend import api, core
from backend import land_evidence_store as evidence_store
from backend.land_evidence import project_land_evidence
from test_wetland_module_runs import insert_assessment, legacy_observation
from synthetic_assessment import synthetic_assessment


@pytest.fixture
def proposal_api(tmp_path, monkeypatch):
    database_path = tmp_path / 'design-proposals.db'
    database_url = os.getenv('CRC_TEST_DATABASE_URL') or 'sqlite:///' + str(database_path)
    database = create_engine(database_url, pool_pre_ping=True)
    monkeypatch.setattr(core, 'engine', database)
    monkeypatch.setattr(api, 'engine', database)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    tables = (
        core.design_revisions, core.design_alternatives,
        core.infrastructure_projects, core.module_runs,
        core.land_evidence_snapshot_origins, core.land_evidence_snapshot_links,
        core.land_evidence_snapshot_members, core.land_evidence_snapshots,
        core.assessments, core.sites,
    )
    if os.getenv('CRC_TEST_DATABASE_URL'):
        with database.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    with TestClient(api.app) as client:
        yield client, database_url, database, monkeypatch
    api.app.dependency_overrides.clear()
    if os.getenv('CRC_TEST_DATABASE_URL'):
        with core.engine.begin() as connection:
            for table in tables:
                connection.execute(delete(table))
    core.engine.dispose()


def saved():
    return synthetic_assessment()


def commit_baseline(database, *, org='org-a', site_id=None, assessment_id='assessment-1'):
    payload = saved()
    original_site_id = payload['environmental_state']['location_id']
    if site_id is not None:
        payload = json.loads(json.dumps(payload).replace(original_site_id, site_id))
    site_id = payload['environmental_state']['location_id']
    insert_assessment(database, payload, assessment_id=assessment_id, org=org)
    core.store_object(
        f'{org}/boundaries/{site_id}/1.json', json.dumps(payload['geometry']),
    )
    snapshot = evidence_store.create_snapshot_from_legacy_assessment(
        assessment_id, org=org,
    )
    return payload, snapshot


def footprint(site_geometry, feature_id, *, offset=0, outside=False,
              role='development_footprint'):
    site = shape(site_geometry)
    if outside:
        minx, miny, maxx, maxy = site.bounds
        width = max(maxx - minx, .001)
        geometry = box(maxx + width * .05, miny, maxx + width * .15,
                       miny + max((maxy - miny) * .1, .0001))
    else:
        point = site.representative_point()
        delta = .000001 * (offset + 1)
        geometry = box(point.x - delta, point.y - delta,
                       point.x + delta, point.y + delta)
        assert site.covers(geometry)
    return {
        'type': 'FeatureCollection',
        'name': 'Exact submitted design',
        'features': [{
            'type': 'Feature', 'id': feature_id,
            'properties': {
                'role': role, 'label': f'Footprint {feature_id}',
                'designer_note': 'retained exactly',
            },
            'geometry': json.loads(json.dumps(mapping(geometry))),
        }],
    }


def create_project(client, site_id, snapshot_id, name='Solar Project'):
    response = client.post('/api/projects', json={
        'name': name, 'project_type': 'solar', 'site_id': site_id,
        'evidence_snapshot_id': snapshot_id,
    })
    assert response.status_code == 200, response.text
    return response.json()


def create_alternative(client, project_id, name):
    response = client.post(f'/api/projects/{project_id}/alternatives',
                           json={'name': name})
    assert response.status_code == 200, response.text
    return response.json()


def create_revision(client, alternative_id, geometry, key, parent=None):
    response = client.post(f'/api/alternatives/{alternative_id}/revisions', json={
        'geometry': geometry, 'parent_revision_id': parent,
        'idempotency_key': key,
        'source_provenance': {
            'source': 'geojson_upload', 'source_reference': 'design-file.geojson',
            'notes': 'Sprint 001 acceptance fixture',
        },
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_api_flow_survives_reload_and_baseline_never_moves(proposal_api):
    client, database_url, database, monkeypatch = proposal_api
    payload, snapshot = commit_baseline(database)
    site_id = payload['environmental_state']['location_id']
    project = create_project(client, site_id, snapshot.id)
    assert project['baseline'] == {
        'snapshot_id': snapshot.id,
        'content_hash': snapshot.content_hash,
        'schema_version': snapshot.schema_version,
        'registry_version': snapshot.registry_version,
        'snapshot_created': snapshot.created.isoformat().replace('+00:00', 'Z'),
        'site_id': site_id,
        'boundary_version': 1,
        'boundary_geometry_fingerprint': snapshot.boundary_geometry_fingerprint,
    }
    assert 'manifest_key' not in json.dumps(project)
    assert client.get('/api/projects').json() == [project]
    assert client.get('/api/projects', params={'site_id': site_id}).json() == [project]

    option_a = create_alternative(client, project['id'], 'Option A')
    option_b = create_alternative(client, project['id'], 'Option B')
    assert client.get(f'/api/alternatives/{option_a["id"]}').json() == option_a
    assert client.get(f'/api/projects/{project["id"]}/alternatives').json() == [
        option_a, option_b,
    ]
    geometry_a1 = footprint(payload['geometry'], 'a-development')
    geometry_b1 = footprint(payload['geometry'], 'b-access', outside=True,
                            role='access_road_footprint')
    polygon_coordinates = geometry_b1['features'][0]['geometry']['coordinates']
    geometry_b1['features'][0]['geometry'] = {
        'type': 'MultiPolygon', 'coordinates': [polygon_coordinates],
    }
    geometry_a2 = footprint(payload['geometry'], 'a-development-v2', offset=1)
    a1 = create_revision(client, option_a['id'], geometry_a1, 'option-a-r1')
    b1 = create_revision(client, option_b['id'], geometry_b1, 'option-b-r1')
    a2 = create_revision(client, option_a['id'], geometry_a2, 'option-a-r2', a1['id'])

    assert a1['geometry'] == geometry_a1
    assert b1['geometry'] == geometry_b1
    assert a2['parent_revision_id'] == a1['id']
    assert [a1['revision_number'], a2['revision_number']] == [1, 2]
    assert not a1['extends_beyond_baseline']
    assert b1['extends_beyond_baseline']
    assert {a1['evidence_snapshot_id'], b1['evidence_snapshot_id'],
            a2['evidence_snapshot_id']} == {snapshot.id}
    assert all(revision['baseline'] == project['baseline'] for revision in (a1, b1, a2))
    assert all('manifest_key' not in json.dumps(revision) for revision in (a1, b1, a2))

    # The same retry key and exact payload returns the first immutable record,
    # even after the lineage head has advanced.
    assert create_revision(client, option_a['id'], geometry_a1,
                           'option-a-r1') == a1
    conflicting_retry = client.post(
        f'/api/alternatives/{option_a["id"]}/revisions', json={
            'geometry': geometry_a2, 'parent_revision_id': None,
            'idempotency_key': 'option-a-r1',
        },
    )
    assert conflicting_retry.status_code == 409
    stale = client.post(f'/api/alternatives/{option_a["id"]}/revisions', json={
        'geometry': geometry_a2, 'parent_revision_id': a1['id'],
        'idempotency_key': 'stale-edit',
    })
    assert stale.status_code == 409 and 'current head' in stale.json()['detail']

    # Reopen the SQLite database and retrieve all exact historical revisions.
    database.dispose()
    reloaded = create_engine(database_url, pool_pre_ping=True)
    monkeypatch.setattr(core, 'engine', reloaded)
    monkeypatch.setattr(api, 'engine', reloaded)
    core.init()
    assert client.get(f'/api/design-revisions/{a1["id"]}').json() == a1
    assert client.get(f'/api/design-revisions/{b1["id"]}').json() == b1
    assert client.get(f'/api/design-revisions/{a2["id"]}').json() == a2
    assert client.get(f'/api/alternatives/{option_a["id"]}/revisions').json() == [a1, a2]
    assert client.get(f'/api/design-revisions/{a1["id"]}').json()['geometry'] == geometry_a1

    # A later assessment and genuinely different committed snapshot do not
    # retarget either the project or any saved revision.
    changed = deepcopy(payload)
    legacy_observation(changed, 'terrain.elevation_m')['value'] += .125
    insert_assessment(reloaded, changed, assessment_id='assessment-2')
    newer = evidence_store.create_snapshot_from_legacy_assessment(
        'assessment-2', org='org-a',
    )
    assert newer.id != snapshot.id
    assert client.get(f'/api/projects/{project["id"]}').json() == project
    assert client.get(f'/api/design-revisions/{a2["id"]}').json()[
        'evidence_snapshot_id'
    ] == snapshot.id


@pytest.mark.parametrize('mutate', [
    lambda geometry: geometry.update(type='GeometryCollection'),
    lambda geometry: geometry['features'].append(deepcopy(geometry['features'][0])),
    lambda geometry: geometry['features'][0]['geometry'].update(type='Point', coordinates=[0, 0]),
    lambda geometry: geometry['features'][0]['geometry']['coordinates'][0].pop(),
    lambda geometry: geometry['features'][0]['geometry']['coordinates'][0][0].__setitem__(0, 181),
    lambda geometry: geometry['features'][0]['geometry']['coordinates'][0][0].__setitem__(0, 10**1000),
    lambda geometry: geometry['features'][0]['properties'].update(role='panel_array'),
    lambda geometry: geometry['features'][0]['properties'].pop('label'),
])
def test_invalid_geometry_and_duplicate_feature_ids_are_rejected(proposal_api, mutate):
    client, _, database, _ = proposal_api
    payload, snapshot = commit_baseline(database)
    project = create_project(client, payload['environmental_state']['location_id'], snapshot.id)
    alternative = create_alternative(client, project['id'], 'Option A')
    geometry = footprint(payload['geometry'], 'duplicate-or-invalid')
    mutate(geometry)
    response = client.post(f'/api/alternatives/{alternative["id"]}/revisions', json={
        'geometry': geometry, 'parent_revision_id': None, 'idempotency_key': 'invalid',
    })
    assert response.status_code == 422
    with database.connect() as connection:
        assert connection.execute(select(func.count()).select_from(
            core.design_revisions
        )).scalar_one() == 0


def test_cross_organisation_references_are_rejected_at_every_link(proposal_api):
    client, _, database, _ = proposal_api
    payload_a, snapshot_a = commit_baseline(database, org='org-a')
    project_a = create_project(
        client, payload_a['environmental_state']['location_id'], snapshot_a.id,
    )
    alternative_a = create_alternative(client, project_a['id'], 'Option A')

    payload_b, snapshot_b = commit_baseline(
        database, org='org-b', site_id='org-b-site', assessment_id='org-b-assessment',
    )
    api.app.dependency_overrides[api.organization] = lambda: 'org-b'
    assert client.get(f'/api/projects/{project_a["id"]}').status_code == 404
    assert client.post(f'/api/projects/{project_a["id"]}/alternatives',
                       json={'name': 'Intruding option'}).status_code == 404
    assert client.post(f'/api/alternatives/{alternative_a["id"]}/revisions', json={
        'geometry': footprint(payload_a['geometry'], 'intruding'),
        'idempotency_key': 'intruding',
    }).status_code == 404
    assert client.post('/api/projects', json={
        'name': 'Wrong Site', 'project_type': 'solar',
        'site_id': payload_a['environmental_state']['location_id'],
        'evidence_snapshot_id': snapshot_a.id,
    }).status_code == 404
    assert client.post('/api/projects', json={
        'name': 'Wrong Snapshot', 'project_type': 'solar',
        'site_id': payload_b['environmental_state']['location_id'],
        'evidence_snapshot_id': snapshot_a.id,
    }).status_code == 404

    project_b = create_project(
        client, payload_b['environmental_state']['location_id'], snapshot_b.id,
        name='Org B Solar',
    )
    alternative_b = create_alternative(client, project_b['id'], 'Option B')
    revision_b = create_revision(
        client, alternative_b['id'], footprint(payload_b['geometry'], 'b'), 'b-r1',
    )
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    assert client.post(f'/api/alternatives/{alternative_a["id"]}/revisions', json={
        'geometry': footprint(payload_a['geometry'], 'a'),
        'parent_revision_id': revision_b['id'], 'idempotency_key': 'foreign-parent',
    }).status_code == 404
    assert client.get(f'/api/design-revisions/{revision_b["id"]}').status_code == 404


def test_project_creation_rejects_missing_or_changed_historical_boundary(proposal_api):
    client, _, database, _ = proposal_api
    payload, snapshot = commit_baseline(database)
    site_id = payload['environmental_state']['location_id']
    boundary_path = (core.ROOT / 'objects' / 'org-a' / 'boundaries' /
                     site_id / '1.json')
    boundary_path.unlink()
    response = client.post('/api/projects', json={
        'name': 'Unverifiable', 'project_type': 'solar', 'site_id': site_id,
        'evidence_snapshot_id': snapshot.id,
    })
    assert response.status_code == 409

    core.store_object(f'org-a/boundaries/{site_id}/1.json', json.dumps({
        'type': 'Polygon',
    }))
    response = client.post('/api/projects', json={
        'name': 'Malformed', 'project_type': 'solar', 'site_id': site_id,
        'evidence_snapshot_id': snapshot.id,
    })
    assert response.status_code == 409

    core.store_object(f'org-a/boundaries/{site_id}/1.json', json.dumps(mapping(
        box(-1.3, 51.7, -1.2, 51.8)
    )))
    response = client.post('/api/projects', json={
        'name': 'Contradictory', 'project_type': 'solar', 'site_id': site_id,
        'evidence_snapshot_id': snapshot.id,
    })
    assert response.status_code == 409


def test_project_requires_snapshot_for_the_exact_selected_site(proposal_api):
    client, _, database, _ = proposal_api
    payload_one, snapshot_one = commit_baseline(database)
    payload_two, snapshot_two = commit_baseline(
        database, site_id='second-org-a-site', assessment_id='second-assessment',
    )
    for site_id, snapshot_id in [
        (payload_one['environmental_state']['location_id'], snapshot_two.id),
        (payload_two['environmental_state']['location_id'], snapshot_one.id),
    ]:
        response = client.post('/api/projects', json={
            'name': 'Mismatched baseline', 'project_type': 'solar',
            'site_id': site_id, 'evidence_snapshot_id': snapshot_id,
        })
        assert response.status_code == 409


def test_revision_append_revalidates_committed_snapshot_and_project_copy(proposal_api):
    client, _, database, _ = proposal_api
    payload, snapshot = commit_baseline(database)
    project = create_project(
        client, payload['environmental_state']['location_id'], snapshot.id,
    )
    alternative = create_alternative(client, project['id'], 'Option A')
    geometry = footprint(payload['geometry'], 'development')
    manifest_path = core.ROOT / 'objects' / snapshot.manifest_key
    manifest = manifest_path.read_bytes()
    manifest_path.unlink()

    missing = client.post(f'/api/alternatives/{alternative["id"]}/revisions', json={
        'geometry': geometry, 'parent_revision_id': None,
        'idempotency_key': 'missing-manifest',
    })
    assert missing.status_code == 409

    core.store_object_immutable(snapshot.manifest_key, manifest)
    with database.begin() as connection:
        connection.execute(update(core.infrastructure_projects).where(
            core.infrastructure_projects.c.id == project['id'],
        ).values(evidence_content_hash='tampered'))
    contradictory = client.post(
        f'/api/alternatives/{alternative["id"]}/revisions', json={
            'geometry': geometry, 'parent_revision_id': None,
            'idempotency_key': 'contradictory-project',
        },
    )
    assert contradictory.status_code == 409
    with database.connect() as connection:
        assert connection.execute(select(func.count()).select_from(
            core.design_revisions
        )).scalar_one() == 0


def test_revision_append_rejects_corrupt_lineage_head(proposal_api):
    client, _, database, _ = proposal_api
    payload, snapshot = commit_baseline(database)
    project = create_project(
        client, payload['environmental_state']['location_id'], snapshot.id,
    )
    alternative = create_alternative(client, project['id'], 'Option A')
    first = create_revision(
        client, alternative['id'], footprint(payload['geometry'], 'first'), 'first',
    )
    with database.begin() as connection:
        connection.execute(update(core.design_revisions).where(
            core.design_revisions.c.id == first['id'],
        ).values(geometry_fingerprint='tampered'))

    response = client.post(f'/api/alternatives/{alternative["id"]}/revisions', json={
        'geometry': footprint(payload['geometry'], 'second'),
        'parent_revision_id': first['id'], 'idempotency_key': 'second',
    })
    assert response.status_code == 409
    with database.connect() as connection:
        assert connection.execute(select(func.count()).select_from(
            core.design_revisions
        )).scalar_one() == 1
