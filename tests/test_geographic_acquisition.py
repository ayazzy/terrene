"""Synthetic adapter, persistence, isolation and legacy-compatibility regressions."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import time

import httpx
import pytest
from pydantic import ValidationError
from shapely.geometry import box, mapping
from sqlalchemy import create_engine, delete, insert, select, update

from backend import core, acquisition as service, acquisition_sources as sources
from backend.acquisition_contracts import AcquisitionError, AcquisitionRequest, digest, encode, validate_area


@pytest.fixture
def database(tmp_path, monkeypatch):
    url = os.getenv('CRC_TEST_DATABASE_URL')
    if url and not url.endswith('/crc_test'):
        raise RuntimeError('Acquisition tests require disposable crc_test database')
    engine = create_engine(url or 'sqlite:///' + str(tmp_path / 'acquisition.db'))
    monkeypatch.setattr(core, 'engine', engine)
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    core.init()
    with engine.begin() as c:
        c.execute(delete(service.attempts))
        c.execute(delete(service.requests))
    yield engine
    engine.dispose()


@pytest.fixture
def profile(database):
    # Deliberately synthetic coverage, never bundled as an England boundary.
    data = encode({'version': sources.COVERAGE_VERSION, 'endpoint': sources.COVERAGE_URL,
                   'synthetic': True, 'feature': {'type': 'Feature',
                   'properties': {'CTRY24CD': 'E92000001'}, 'geometry': mapping(box(-2, 51, 2, 53))}})
    sha = digest(data)
    core.store_object_immutable(sources._profile_key(sha), data)
    return sha


def request(profile, key='test-1', area=None):
    return {'contract_version': 'geographic_acquisition_request_v1',
            'source_id': 'natural_england.sssi', 'adapter_version': 'sssi_arcgis_v1',
            'coverage_profile_sha256': profile, 'area': area or mapping(box(-1.30, 51.75, -1.28, 51.77)),
            'temporal': {'mode': 'current_publication'}, 'idempotency_key': key}


def feature(oid=1, geometry=None):
    return {'type': 'Feature', 'id': oid, 'properties': {'OBJECTID': oid, 'REF_CODE': f'SYNTHETIC-{oid}'},
            'geometry': geometry or mapping(box(-1.31, 51.74, -1.29, 51.76))}


class Provider:
    def __init__(self, features=None, failure=None):
        self.features = [feature()] if features is None else features
        self.failure = failure
        self.calls = []
        self.metadata_calls = 0
        self.ids_calls = 0

    def handle(self, req):
        self.calls.append(req)
        params = req.url.params
        if self.failure == 'network':
            raise httpx.ConnectError('SENSITIVE provider details must never escape', request=req)
        if not req.url.path.endswith('/query'):
            self.metadata_calls += 1
            value = {'geometryType': 'esriGeometryPolygon', 'objectIdField': 'OBJECTID',
                     'extent': {'spatialReference': {'wkid': 27700}},
                     'fields': [{'name': 'OBJECTID', 'type': 'esriFieldTypeOID'}, {'name': 'REF_CODE'}],
                     'maxRecordCount': 1000, 'editingInfo': {'lastEditDate': 100}}
            if self.failure == 'changed' and self.metadata_calls > 1:
                value['editingInfo']['lastEditDate'] = 101
            if self.failure == 'schema':
                value['objectIdField'] = 'WRONG'
        elif params.get('returnIdsOnly') == 'true':
            self.ids_calls += 1
            ids = [f['properties']['OBJECTID'] for f in self.features]
            if self.failure == 'ids_changed' and self.ids_calls > 1:
                ids = []
            value = {'objectIdFieldName': 'OBJECTID', 'objectIds': ids}
        else:
            ids = [int(i) for i in params['objectIds'].split(',')]
            values = [f for f in self.features if f['properties']['OBJECTID'] in ids]
            value = {'type': 'FeatureCollection', 'features': values}
            if self.failure == 'truncated':
                value['exceededTransferLimit'] = True
            if self.failure == 'missing':
                value['features'] = []
        return httpx.Response(200, json=value)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))


@pytest.mark.parametrize('lon,lat', [(-1.3,51.75),(-3.2,51.5),(-4.2,55.85),(-1.15,60.15),(-6,54.6)])
def test_geometry_accepts_all_uk_nations_and_northern_island(lon, lat):
    assert validate_area(mapping(box(lon, lat, lon+.001, lat+.001)))


def test_geometry_identity_is_stable_without_coordinate_rounding(profile):
    a = request(profile)
    b = deepcopy(a)
    b['area']['coordinates'] = [list(reversed(b['area']['coordinates'][0]))]
    assert AcquisitionRequest.model_validate(a).geometry_fingerprint == AcquisitionRequest.model_validate(b).geometry_fingerprint
    c = deepcopy(a)
    c['area'] = mapping(box(-1.300000001, 51.75, -1.28, 51.77))
    assert AcquisitionRequest.model_validate(a).geometry_fingerprint != AcquisitionRequest.model_validate(c).geometry_fingerprint


@pytest.mark.parametrize('geometry', [
    {'type':'Point', 'coordinates':[-1,52]},
    {'type':'Polygon','coordinates':[[[-1,52],[-1.1,52],[-1.1,52.1]]]},
    {'type':'Polygon','coordinates':[[[-1,52],[-1.1,52.1],[-1.1,52],[-1,52.1],[-1,52]]]},
    {'type':'Polygon','coordinates':[[[-1,52],[float('nan'),52],[-1.1,52.1],[-1,52]]]},
    mapping(box(-8,50,2,60)),
])
def test_invalid_geometry_rejected(geometry):
    with pytest.raises(ValueError):
        validate_area(geometry)


@pytest.mark.parametrize('area', [mapping(box(-4,52,-3.99,52.01)), mapping(box(-4,56,-3.99,56.01)),
                                  mapping(box(-6,54.6,-5.99,54.61)), mapping(box(-1.2,60,-1.19,60.01)),
                                  mapping(box(-2.001,52,-1.999,52.001))])
def test_source_coverage_rejection_makes_no_sssi_request(profile, area):
    provider = Provider()
    result = service.acquire('org', request(profile, area=area), client=provider.client())
    assert result['state'] == 'failed' and result['error_code'] == 'unsupported_geography'
    assert result['result'] is None and provider.calls == []


def test_temporal_request_is_not_silently_substituted(profile):
    value = request(profile)
    value['temporal'] = {'mode':'interval', 'start':'2010-01-01', 'end':'2020-01-01'}
    provider = Provider()
    result = service.acquire('org', value, client=provider.client())
    assert result['error_code'] == 'unsupported_time' and not provider.calls
    value['temporal'] = {'mode':'current_publication','start':'2020'}
    with pytest.raises(ValidationError):
        AcquisitionRequest.model_validate(value)


def test_success_empty_is_distinct_from_failure(profile):
    result = service.acquire('org', request(profile), client=Provider([]).client())
    assert result['state'] == 'succeeded'
    assert result['result']['feature_count'] == 0
    assert result['result']['completeness'] == 'complete_provider_selection'
    assert result['result']['observation_time'] is None


def test_idempotency_refresh_org_isolation_and_reload(profile, database):
    provider = Provider()
    first = service.acquire('org', request(profile), client=provider.client())
    calls = len(provider.calls)
    same = service.acquire('org', request(profile), client=provider.client())
    assert same == first and len(provider.calls) == calls
    database.dispose()  # Drop pooled connections; reload from database + objects.
    assert service.read_acquisition('org', first['acquisition_id']) == first
    with pytest.raises(AcquisitionError, match='not_found'):
        service.read_acquisition('other', first['acquisition_id'])
    other = service.acquire('other', request(profile), client=provider.client())
    assert other['acquisition_id'] != first['acquisition_id']
    changed = request(profile, area=mapping(box(-1.2,51.7,-1.19,51.71)))
    with pytest.raises(AcquisitionError, match='idempotency_conflict'):
        service.acquire('org', changed, client=provider.client())
    refresh = service.acquire('org', request(profile, key='refresh'), client=Provider(failure='network').client())
    assert refresh['state'] == 'failed' and refresh['result'] is None
    assert service.read_acquisition('org', first['acquisition_id']) == first
    assert 'geographic-acquisition/' not in json.dumps(first)


@pytest.mark.parametrize('failure,code', [('network','network_failure'),('truncated','incomplete_selection'),
    ('missing','inconsistent_feature_ids'),('changed','source_changed_during_capture'),
    ('ids_changed','source_changed_during_capture'),('schema','source_schema_changed')])
def test_failures_retained_retry_appends_history(profile, failure, code):
    first = service.acquire('org', request(profile), client=Provider(failure=failure).client())
    assert first['error_code'] == code and first['result'] is None
    assert 'SENSITIVE' not in json.dumps(first)
    second = service.acquire('org', request(profile), client=Provider().client())
    assert second['acquisition_id'] == first['acquisition_id'] and second['state'] == 'succeeded'
    assert len(second['attempts']) == 2 and second['attempts'][0]['error_code'] == code
    old = service.read_acquisition('org', first['acquisition_id'], attempt_id=first['attempt_id'])
    assert old['manifest_sha256'] == first['manifest_sha256'] and old['state'] == 'failed'


def test_normalization_preserves_original_geometry_and_full_selected_feature(profile):
    bowtie = {'type':'Polygon','coordinates':[[[-1.30,51.75],[-1.29,51.76],[-1.30,51.76],[-1.29,51.75],[-1.30,51.75]]]}
    result = service.acquire('org', request(profile), client=Provider([feature(1,bowtie), feature(2)]).client())
    assert result['state'] == 'succeeded' and result['result']['feature_count'] == 2
    def artifact(name):
        sha = result['artifact_checksums'][name]['sha256']
        return json.loads(core.load_object(service._object_key('org', sha)))
    assert artifact('assembled_provider_candidates')['features'][0]['geometry'] == bowtie
    assert artifact('normalized_selection')['features'][0]['geometry']['type'] == 'MultiPolygon'
    assert artifact('normalization_lineage')[0]['repaired'] is True
    assert artifact('normalized_selection')['features'][1]['geometry'] == json.loads(encode(feature(2)['geometry']))


def test_polygon_selection_does_not_treat_envelope_as_area(profile):
    area = {'type':'Polygon','coordinates':[[[-1.30,51.75],[-1.28,51.75],[-1.30,51.77],[-1.30,51.75]]]}
    outside = feature(1,mapping(box(-1.283,51.763,-1.281,51.765)))
    result = service.acquire('org', request(profile, area=area), client=Provider([outside]).client())
    assert result['result']['candidate_count'] == 1 and result['result']['feature_count'] == 0


def test_pagination_and_feature_limits(profile, monkeypatch):
    monkeypatch.setitem(sources.LIMITS, 'batch_size', 1)
    provider = Provider([feature(1),feature(2)])
    result = service.acquire('org', request(profile), client=provider.client())
    assert result['state'] == 'succeeded'
    assert sum('objectIds' in r.url.params for r in provider.calls) == 2
    monkeypatch.setitem(sources.LIMITS,'max_features',1)
    result = service.acquire('org', request(profile,'limit'), client=provider.client())
    assert result['error_code'] == 'feature_limit'


@pytest.mark.parametrize('limit', ['max_response_bytes','max_total_bytes'])
def test_byte_limits_fail_closed(profile, monkeypatch, limit):
    monkeypatch.setitem(sources.LIMITS,limit,100)
    result = service.acquire('org', request(profile), client=Provider().client())
    assert result['state'] == 'failed' and result['error_code'] == 'byte_limit'


@pytest.mark.parametrize('target', ['manifest','artifact','coverage','envelope'])
def test_corrupt_or_contradictory_history_fails_integrity(profile, database, target):
    result = service.acquire('org', request(profile), client=Provider().client())
    if target == 'envelope':
        with database.begin() as c:
            c.execute(update(service.attempts).values(state='failed').where(service.attempts.c.id==result['attempt_id']))
    else:
        if target == 'manifest':
            key = service._object_key('org', result['manifest_sha256'])
        elif target == 'coverage':
            key = sources._profile_key(profile)
        else:
            key = service._object_key('org', result['artifact_checksums']['normalized_selection']['sha256'])
        (core.ROOT / 'objects' / key).write_text('{}')
    with pytest.raises(AcquisitionError, match='integrity_failure'):
        service.read_acquisition('org', result['acquisition_id'])


def test_storage_failure_is_not_success_and_can_retry(profile, monkeypatch):
    original = core.store_object_immutable
    def fail(*a, **k):
        raise OSError('PRIVATE STORAGE PATH')
    monkeypatch.setattr(core, 'store_object_immutable', fail)
    first = service.acquire('org', request(profile), client=Provider().client())
    assert first['error_code'] == 'storage_failure' and first['manifest_sha256'] is None
    monkeypatch.setattr(core, 'store_object_immutable', original)
    second = service.acquire('org', request(profile), client=Provider().client())
    assert second['state'] == 'succeeded' and len(second['attempts']) == 2


def test_claim_recovery_fences_stale_publisher(profile, database):
    typed = AcquisitionRequest.model_validate(request(profile))
    row = service._register('org', typed)
    old_claim = service._claim(row)
    with pytest.raises(AcquisitionError, match='in_progress'):
        service.acquire('org', typed, client=Provider().client())
    with database.begin() as c:
        c.execute(update(service.requests).where(service.requests.c.id==row['id']).values(lease=time.time()-1))
    result = service.acquire('org', typed, client=Provider().client())
    assert result['state'] == 'succeeded' and result['attempts'][0]['error_code'] == 'interrupted'
    with pytest.raises(AcquisitionError, match='claim_lost'):
        service._finish(row, old_claim, 'succeeded', None, core.now(), None)
    assert service.read_acquisition('org', row['id']) == result


def test_concurrent_requests_publish_one_attempt(profile):
    provider = Provider()
    def run():
        try:
            return service.acquire('org', request(profile), client=provider.client())
        except AcquisitionError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    successes = [r for r in results if isinstance(r,dict)]
    assert successes and len({r['attempt_id'] for r in successes}) == 1
    assert len(successes[0]['attempts']) == 1
    assert provider.metadata_calls == 2


def test_legacy_catalogue_assessment_selection_and_saved_result_unchanged(profile, database, monkeypatch):
    from fastapi.testclient import TestClient
    from backend import api
    monkeypatch.setattr(api, 'engine', database)
    api.app.dependency_overrides[api.organization] = lambda: 'legacy-org'
    dataset_id = core.uid()
    retained = {'synthetic': True, 'historical_result': {'mapped_area': 123}}
    old_id = core.uid()
    with database.begin() as c:
        c.execute(insert(core.datasets).values(id=dataset_id,key='synthetic-acquisition-regression',state='available',
                  retrieved=core.now(),metadata={'synthetic':True,'bbox':list(core.PILOT)}))
        c.execute(insert(core.assessments).values(id=old_id,org='legacy-org',state='succeeded',result=retained))
        before = core.latest(c)
    try:
        with TestClient(api.app) as client:
            site = client.post('/api/sites', json={'name':'Synthetic compatibility test','geometry':request(profile)['area']}).json()
            acquired = service.acquire('legacy-org', request(profile), client=Provider().client())
            assert acquired['state'] == 'succeeded'
            job = client.post('/api/sites/'+site['id']+'/assessments')
            assert job.status_code == 200, job.text
            with database.connect() as c:
                assert core.latest(c) == before
                row = c.execute(select(core.assessments).where(core.assessments.c.id==job.json()['id'])).mappings().one()
                assert row['dataset_ids'] == sorted(r['id'] for r in before)
                assert c.execute(select(core.assessments.c.result).where(core.assessments.c.id==old_id)).scalar_one() == retained
    finally:
        api.app.dependency_overrides.clear()
        with database.begin() as c:
            c.execute(delete(core.datasets).where(core.datasets.c.id==dataset_id))
            c.execute(delete(core.assessments).where(core.assessments.c.org=='legacy-org'))
            c.execute(delete(core.sites).where(core.sites.c.org=='legacy-org'))


def test_prepare_coverage_uses_fixed_official_source_and_retains_profile(database):
    calls=[]
    def provider(req):
        calls.append(str(req.url))
        if req.url.path.endswith('/query'):
            value={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'CTRY24CD':'E92000001'},
                    'geometry':mapping(box(-2,51,2,53))}]}
        elif '/items/' in req.url.path:
            value={'id':sources.COVERAGE_ITEM.rsplit('/',1)[1],'owner':'ONSGeography_data','synthetic':True}
        else:
            value={'synthetic':True}
        return httpx.Response(200,json=value)
    result=sources.prepare_coverage(client=httpx.Client(transport=httpx.MockTransport(provider)))
    profile,geometry=sources.load_coverage(result['coverage_profile_sha256'])
    assert geometry.covers(box(-1.3,51.7,-1.2,51.8))
    assert profile['item_metadata']['synthetic'] is True
    assert len(calls)==3 and all(u.startswith((sources.COVERAGE_ITEM,sources.COVERAGE_URL)) for u in calls)


def test_missing_profile_and_unknown_source_do_not_fetch(database):
    provider=Provider()
    value=request('0'*64)
    result=service.acquire('org',value,client=provider.client())
    assert result['error_code']=='coverage_not_prepared' and not provider.calls
    value['source_id']='https://unregistered.invalid'
    with pytest.raises(ValidationError):
        service.acquire('org',value,client=provider.client())
    assert not provider.calls


def test_source_non_polygon_never_becomes_empty_evidence(profile):
    result=service.acquire('org',request(profile),client=Provider([feature(1,{'type':'Point','coordinates':[-1.29,51.76]})]).client())
    assert result['error_code']=='invalid_source_geometry_or_identity'
    assert result['result'] is None
    assert 'assembled_provider_candidates' in result['artifact_checksums']


def test_network_deadline_is_an_explicit_failure(profile, monkeypatch):
    provider=Provider()
    clock=[0.0]
    monkeypatch.setattr(sources.time,'monotonic',lambda:clock[0])
    original=provider.handle
    def delayed(req):
        response=original(req)
        clock[0]+=181
        return response
    result=service.acquire('org',request(profile),client=httpx.Client(transport=httpx.MockTransport(delayed)))
    assert result['error_code']=='network_deadline'


def test_interrupted_publication_does_not_expose_orphaned_success(profile,database,monkeypatch):
    finish=service._finish
    def interrupt(*args):
        raise RuntimeError('simulated process death after object write')
    monkeypatch.setattr(service,'_finish',interrupt)
    with pytest.raises(RuntimeError):
        service.acquire('org',request(profile),client=Provider().client())
    with database.begin() as c:
        row=c.execute(select(service.requests)).mappings().one()
        assert row['state']=='running' and row['completed_attempt_id'] is None
        c.execute(update(service.requests).where(service.requests.c.id==row['id']).values(lease=time.time()-1))
    monkeypatch.setattr(service,'_finish',finish)
    result=service.acquire('org',request(profile),client=Provider().client())
    assert result['state']=='succeeded' and result['attempts'][0]['error_code']=='interrupted'
    assert len(result['attempts'])==2


def test_multi_polygon_and_hole_geometry_keep_their_support():
    one=box(-6,54.6,-5.999,54.601)
    two=box(-1.15,60.15,-1.149,60.151)
    value={'type':'MultiPolygon','coordinates':[mapping(one)['coordinates'],mapping(two)['coordinates']]}
    assert validate_area(value)['type']=='MultiPolygon'
    hole={'type':'Polygon','coordinates':[list(box(-1.3,51.7,-1.2,51.8).exterior.coords),
            list(box(-1.28,51.72,-1.22,51.78).exterior.coords)]}
    assert len(validate_area(hole)['coordinates'])==2


def test_request_coordinate_and_payload_bounds():
    from backend.acquisition_contracts import MAX_COORDINATES
    geometry={'type':'Polygon','coordinates':[[[-1,52]]*(MAX_COORDINATES+1)]}
    with pytest.raises(ValueError,match='coordinate_limit'):
        validate_area(geometry)
    with pytest.raises(ValueError,match='payload_limit'):
        validate_area({'type':'Polygon','coordinates':[],'unexpected':'x'*500000})
