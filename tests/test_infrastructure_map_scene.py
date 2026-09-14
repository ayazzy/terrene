"""Native infrastructure map-scene contract and immutable snapshot reads."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import shape

from backend import api, core
from backend import land_evidence_store as store
from backend.infrastructure_map_scene import build_infrastructure_map_scene
from backend.land_evidence import (
    BUILDING_HEIGHT_REGISTRY_VERSION,
    BUILT_WORLD_REGISTRY_VERSION,
    project_land_evidence,
)
from test_openmap_local import (
    synthetic_assessment, synthetic_summary, with_building_heights,
    with_built_world,
)
from test_wetland_module_runs import insert_assessment, module_database, table_count


REAL_ROOT = Path(__file__).parents[1] / 'data/verification/england-real-openmap-local-2026-04'


@pytest.fixture
def client(module_database, monkeypatch):
    monkeypatch.setattr(api, 'engine', module_database)
    api.app.dependency_overrides[api.organization] = lambda: 'org-a'
    with TestClient(api.app) as value:
        yield value
    api.app.dependency_overrides.clear()


def retained(name='oxford-station', suffix='after'):
    return json.loads((REAL_ROOT / f'{name}-{suffix}.json').read_text())


def persist_retained(module_database, name='oxford-station', suffix='after'):
    payload = retained(name, suffix)
    insert_assessment(module_database, payload, assessment_id='scene-assessment')
    return store.create_snapshot_from_legacy_assessment(
        'scene-assessment', org='org-a',
    )


def keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(keys(item) for item in value))
    return set()


def test_oxford_scene_is_deterministic_wgs84_tenant_scoped_and_read_only(
    client, module_database, monkeypatch,
):
    snapshot = persist_retained(module_database)
    manifest_before = core.load_object(snapshot.manifest_key)
    tables = (
        core.land_evidence_snapshots, core.land_evidence_snapshot_members,
        core.land_evidence_snapshot_links, core.land_evidence_snapshot_origins,
        core.module_runs,
    )
    counts_before = {table.name: table_count(module_database, table) for table in tables}

    def deny_write(*args, **kwargs):
        raise AssertionError('Map-scene GET attempted persistence')

    monkeypatch.setattr(core, 'store_object', deny_write)
    monkeypatch.setattr(core, 'store_object_immutable', deny_write)
    url = f'/api/land-evidence-snapshots/{snapshot.id}/map-scene'
    first = client.get(url)
    second = client.get(url)
    assert first.status_code == 200, first.text
    assert first.json() == second.json()
    assert first.headers['cache-control'] == 'no-store'
    result = first.json()
    assert result['contract_version'] == 'infrastructure_map_scene_v1'
    assert result['snapshot'] == {
        'id': snapshot.id, 'schema_version': snapshot.schema_version,
        'registry_version': BUILT_WORLD_REGISTRY_VERSION,
        'content_hash': snapshot.content_hash,
        'created': snapshot.created.isoformat().replace('+00:00', 'Z'),
    }
    assert result['site']['id'] == snapshot.site_id
    assert result['boundary']['version'] == snapshot.boundary_version
    assert result['boundary']['geometry_fingerprint'] == snapshot.boundary_geometry_fingerprint
    assert result['presentation_crs'] == 'EPSG:4326'
    assert result['authoritative_geometry_crs'] == 'EPSG:27700'
    assert {layer['id']: layer['feature_count'] for layer in result['layers']} == {
        'buildings': 5, 'functional_sites': 2,
        'railway_tracks': 7, 'railway_stations': 1,
    }
    assert all(
        feature['properties']['height']['state'] == 'unsupported'
        for feature in result['features']
        if feature['properties']['object_type'] == 'building'
    )
    assert next(
        item for item in result['capabilities']
        if item['id'] == 'evidence_backed_building_extrusion'
    )['state'] == 'unsupported'
    for feature in result['features']:
        west, south, east, north = shape(feature['geometry']).bounds
        assert -180 <= west <= east <= 180
        assert -90 <= south <= north <= 90
        assert feature['properties']['geometry_fingerprint']
        assert feature['properties']['relationships']
    assert not keys(result) & {
        'source_geometry', 'raw_reference_ids', 'storage_reference',
        'manifest_key', 'assets', 'source_feature_id',
    }
    assert {table.name: table_count(module_database, table) for table in tables} == counts_before
    assert core.load_object(snapshot.manifest_key) == manifest_before

    api.app.dependency_overrides[api.organization] = lambda: 'org-b'
    assert client.get(url).status_code == 404


def test_v4_scene_links_height_evidence_and_never_extrudes_a_gap(
    client, module_database,
):
    _, summary = synthetic_summary()
    projection = project_land_evidence(with_building_heights(
        with_built_world(synthetic_assessment(), summary)
    ))
    snapshot = store.persist_land_evidence_snapshot(
        projection, org='org-a', site_id=projection.identity.legacy_location_id,
    )
    response = client.get(
        f'/api/land-evidence-snapshots/{snapshot.id}/map-scene'
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['snapshot']['registry_version'] == BUILDING_HEIGHT_REGISTRY_VERSION
    buildings = [
        item for item in result['features']
        if item['properties']['object_type'] == 'building'
    ]
    assert len(buildings) == 3
    available = [
        item['properties']['height'] for item in buildings
        if item['properties']['height']['state'] in ('available', 'partial')
    ]
    gaps = [
        item['properties']['height'] for item in buildings
        if item['properties']['height']['state'] == 'gap'
    ]
    assert len(available) == 2 and len(gaps) == 1
    assert all(item['extrusion_height_m'] == item['p90_height_m'] for item in available)
    assert gaps[0]['extrusion_height_m'] is None
    assert gaps[0]['reason_code'] == 'footprint_too_small'
    building_layer = next(item for item in result['layers'] if item['id'] == 'buildings')
    assert building_layer['height_available_count'] == 2
    assert building_layer['height_gap_count'] == 1
    assert building_layer['height_unsupported_count'] == 0
    assert next(
        item for item in result['capabilities']
        if item['id'] == 'evidence_backed_building_extrusion'
    )['state'] == 'partial'
    assert {source['provider'] for source in result['sources']} == {
        'Environment Agency', 'Ordnance Survey',
    }


def test_historical_pre_built_snapshot_has_explicit_unsupported_scene(
    client, module_database,
):
    snapshot = persist_retained(module_database, suffix='pre-built')
    response = client.get(
        f'/api/land-evidence-snapshots/{snapshot.id}/map-scene'
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['features'] == []
    assert all(layer['state'] == 'unsupported' for layer in result['layers'])
    assert all(capability['state'] in ('unsupported', 'unavailable')
               for capability in result['capabilities'])


def test_presenter_rejects_snapshot_manifest_identity_mismatch(module_database):
    snapshot = persist_retained(module_database)
    projection = store.load_land_evidence_snapshot(snapshot.id, org='org-a')
    changed = snapshot.model_copy(update={'content_hash': '0' * 64})
    with pytest.raises(ValueError, match='do not match'):
        build_infrastructure_map_scene(changed, projection)
    mismatched = snapshot.model_copy(update={'site_id': 'another-site'})
    with pytest.raises(ValueError, match='do not match'):
        build_infrastructure_map_scene(mismatched, projection)
