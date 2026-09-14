"""Versioned extent-of-realm coverage, without broadening retained v1 requests."""
from copy import deepcopy
import json

import httpx
import pytest
from shapely.geometry import box, mapping

from backend import core, acquisition as service, acquisition_sources as sources
from backend.acquisition_contracts import AcquisitionError, digest, encode
from test_geographic_acquisition import database, profile, Provider, request


def retained_profile(version, geometry):
    data = encode({'version': version, 'endpoint': sources.COVERAGE_POLICIES[version][0],
                   'synthetic': True, 'feature': {'type': 'Feature', 'properties': {'CTRY24CD': 'E92000001'},
                                                 'geometry': geometry}})
    sha = digest(data)
    core.store_object_immutable(sources._profile_key(sha), data)
    return sha


@pytest.fixture
def profiles(database):
    full = box(-2, 51, 2, 53)
    hole = box(-1.295, 51.755, -1.285, 51.765)
    return (retained_profile(sources.COVERAGE_VERSION, mapping(full.difference(hole))),
            retained_profile(sources.FULL_EXTENT_COVERAGE_VERSION, mapping(full)))


def test_tidal_area_requires_explicit_new_version_and_preserves_old_failure(profiles):
    clipped, full = profiles
    provider = Provider()
    old = service.acquire('org', request(clipped), client=provider.client())
    assert old['error_code'] == 'unsupported_geography' and not provider.calls
    old_manifest = core.load_object(service._object_key('org', old['manifest_sha256']))
    new_request = request(full)
    new_request['adapter_version'] = 'sssi_arcgis_v2'
    with pytest.raises(AcquisitionError, match='idempotency_conflict'):
        service.acquire('org', new_request, client=provider.client())
    new_request['idempotency_key'] = 'explicit-v2-capture'
    new = service.acquire('org', new_request, client=provider.client())
    assert new['state'] == 'succeeded' and new['result']['feature_count'] == 1
    assert new['source']['capability_version'] == 'england_current_vector_v2'
    assert new['source']['coverage_profile_version'] == sources.FULL_EXTENT_COVERAGE_VERSION
    assert service.read_acquisition('org', old['acquisition_id']) == old
    assert core.load_object(service._object_key('org', old['manifest_sha256'])) == old_manifest
    calls = len(provider.calls)
    assert service.acquire('org', new_request, client=provider.client()) == new
    assert len(provider.calls) == calls


@pytest.mark.parametrize('adapter,index', [('sssi_arcgis_v1', 1), ('sssi_arcgis_v2', 0)])
def test_profiles_cannot_be_swapped_between_adapter_versions(profiles, adapter, index):
    provider = Provider()
    value = request(profiles[index])
    value['adapter_version'] = adapter
    result = service.acquire('org', value, client=provider.client())
    assert result['error_code'] == 'coverage_version_mismatch' and not provider.calls


@pytest.mark.parametrize('area', [box(-4, 52, -3.99, 52.01), box(-4, 56, -3.99, 56.01),
    box(-6,54.6,-5.99,54.61), box(-1.2,60,-1.19,60.01), box(-2.001,52,-1.999,52.001), box(3,52,3.01,52.01)])
def test_new_profile_still_rejects_other_nations_cross_border_and_offshore(profiles, area):
    provider = Provider()
    value = request(profiles[1], area=mapping(area))
    value['adapter_version'] = 'sssi_arcgis_v2'
    result = service.acquire('org', value, client=provider.client())
    assert result['error_code'] == 'unsupported_geography' and not provider.calls


def test_v1_success_manifest_and_descriptor_remain_identical(profile):
    before = deepcopy(sources.DESCRIPTOR)
    old = service.acquire('org', request(profile), client=Provider().client())
    sha = old['manifest_sha256']
    payload = core.load_object(service._object_key('org', sha))
    sources.source_descriptor('sssi_arcgis_v2')
    assert sources.source_descriptor() == before == old['source']
    assert core.load_object(service._object_key('org', sha)) == payload
    assert service.read_acquisition('org', old['acquisition_id']) == old


@pytest.mark.parametrize('fault,code', [(None,None), ('metadata','coverage_schema_changed'),
    ('changed','coverage_changed_during_capture'), ('crs','coverage_schema_changed'),
    ('country','invalid_coverage_geometry'), ('truncated','incomplete_coverage')])
def test_prepare_bfe_profile_checks_source_identity_and_consistency(database, fault, code):
    calls = []
    metadata_count = 0
    def handler(req):
        nonlocal metadata_count
        calls.append(str(req.url))
        if '/items/' in req.url.path:
            value = {'id':sources.FULL_EXTENT_COVERAGE_ITEM.rsplit('/',1)[1], 'owner':'ONSGeography_data',
                     'type':'Feature Service', 'url':sources.FULL_EXTENT_COVERAGE_URL.rsplit('/',1)[0]}
            if fault == 'metadata':
                value['url'] = 'https://unregistered.invalid'
        elif req.url.path.endswith('/query'):
            value = {'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:4326'}},
                     'features':[{'type':'Feature','properties':{'CTRY24CD':'E92000001'},
                                  'geometry':mapping(box(-2,51,2,53))}]}
            if fault == 'crs':
                value['crs']['properties']['name'] = 'EPSG:27700'
            if fault == 'country':
                value['features'][0]['properties']['CTRY24CD'] = 'W92000004'
            if fault == 'truncated':
                value['exceededTransferLimit'] = True
        else:
            metadata_count += 1
            value = {'geometryType':'esriGeometryPolygon', 'extent':{'spatialReference':{'wkid':27700}},
                     'editingInfo':{'lastEditDate':100}}
            if fault == 'changed' and metadata_count > 1:
                value['editingInfo']['lastEditDate'] = 101
        return httpx.Response(200,json=value)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    if code:
        with pytest.raises(AcquisitionError, match=code):
            sources.prepare_coverage(client=client, adapter_version='sssi_arcgis_v2')
        assert not list((core.ROOT/'objects/geographic-acquisition/coverage').glob('*.json'))
    else:
        prepared = sources.prepare_coverage(client=client, adapter_version='sssi_arcgis_v2')
        profile, _ = sources.load_coverage(prepared['coverage_profile_sha256'], expected_version=sources.FULL_EXTENT_COVERAGE_VERSION)
        assert profile['metadata'] == profile['metadata_after']
        assert profile['version'] == sources.FULL_EXTENT_COVERAGE_VERSION
        assert len(calls) == 4
    assert all(u.startswith((sources.FULL_EXTENT_COVERAGE_URL,sources.FULL_EXTENT_COVERAGE_ITEM)) for u in calls)


def test_cli_version_selection_is_explicit_and_default_stays_v1(capsys):
    assert service.main(['sources']) == 0
    assert json.loads(capsys.readouterr().out)['adapter_version'] == 'sssi_arcgis_v1'
    assert service.main(['sources','--adapter-version','sssi_arcgis_v2']) == 0
    assert json.loads(capsys.readouterr().out)['capability_version'] == 'england_current_vector_v2'
