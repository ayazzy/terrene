"""Authenticated retained-capture discovery, truthful filtering and integrity boundaries."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest
from shapely.geometry import box, mapping, Polygon
from sqlalchemy import update, delete, event

from backend import core, acquisition as store, acquisition_catalogue as catalogue, api
from backend.acquisition_contracts import encode, digest
from test_geographic_acquisition import database, profile, request, Provider
from test_weather_acquisition import request as weather_request, Provider as WeatherProvider
from test_satellite_acquisition import Provider as SatelliteProvider
from test_lidar_acquisition import raster_profile, lidar_request, RasterProvider


@pytest.fixture
def client(database):
    api.app.dependency_overrides[api.organization] = lambda: 'org'
    with TestClient(api.app, raise_server_exceptions=False) as client:
        yield client
    api.app.dependency_overrides.clear()


def capture(profile, key='vector', org='org', area=None):
    return store.acquire(org, request(profile,key,area),client=Provider().client())


def manifest_of(summary, org='org'):
    key=store._object_key(org,summary['manifest_sha256'])
    return key,store._load(org,{'key':key,'sha256':summary['manifest_sha256']})


def test_mixed_families_safe_exact_capture_contract(client,profile,raster_profile):
    vector=capture(profile)
    weather=store.acquire('org',weather_request(),client=WeatherProvider('gaps').client())
    satellite=SatelliteProvider()
    imagery=store.acquire('org',satellite.request(),client=satellite.client())
    terrain_request=lidar_request(raster_profile)
    terrain=store.acquire('org',terrain_request,client=RasterProvider(terrain_request['area']).client())
    originals={v['acquisition_id']:v for v in (vector,weather,imagery,terrain)}
    response=client.get('/api/acquisitions')
    assert response.status_code==200,response.text
    assert response.headers['cache-control']=='no-store'
    data=response.json()
    assert data['contract_version']=='acquisition_catalogue_v1'
    assert data['scan_complete'] and data['next_cursor'] is None
    assert len(data['entries'])==4
    by_family={e['family']:e for e in data['entries']}
    assert by_family['vector']['evidence_time']['kind']=='unknown'
    assert by_family['raster']['evidence_time']['kind']=='unknown'
    assert by_family['satellite']['evidence_time']['start'].startswith('2025-06-19T11:17:06')
    w=by_family['weather_timeseries']
    assert w['requested_geometry']==weather_request()['point']
    assert w['evidence_time']=={'kind':'interval','start':'2024-02-28T00:00:00+00:00','end_exclusive':'2024-03-02T00:00:00+00:00'}
    assert next(c for c in w['counts'] if c['series']=='WS10M')['present']==0
    for entry in data['entries']:
        original=originals[entry['acquisition_id']]
        assert entry['manifest_sha256']==original['manifest_sha256']
        assert entry['attempt_id']==original['attempt_id']
        assert entry['artifact_verification']=='not_performed' and entry['manifest_verified']
        detail=client.get(entry['detail_path'])
        assert detail.status_code==200,detail.text
        assert detail.headers['cache-control']=='no-store'
        assert detail.json()['entry']=={**entry,'artifact_verification':'verified'}
        assert {a['role']:a['sha256'] for a in detail.json()['artifacts']}=={k:v['sha256'] for k,v in original['artifact_checksums'].items()}
    serialized=json.dumps(data)
    for private in ('idempotency_key','coverage_profile_sha256','diagnostics','"org"','https://','objects/'):
        assert private not in serialized


def test_browse_reads_only_manifests_and_detail_detects_corrupt_artifact(client,profile,monkeypatch):
    summary=capture(profile)
    key,manifest=manifest_of(summary)
    original=store._load;reads=[]
    def recording(org,ref):
        reads.append(ref['key'])
        return original(org,ref)
    monkeypatch.setattr(store,'_load',recording)
    assert client.get('/api/acquisitions').status_code==200
    assert reads==[key]
    ref=manifest['artifacts']['normalized_selection']
    core.store_object(ref['key'],b'corrupted private artifact')
    response=client.get('/api/acquisitions')
    assert response.status_code==200
    entry=response.json()['entries'][0]
    assert entry['artifact_verification']=='not_performed'
    failed=client.get(entry['detail_path'])
    assert failed.status_code==500
    assert failed.json()=={'detail':'Retained acquisition could not be verified'}
    assert failed.headers['cache-control']=='no-store'


def test_geometry_intersection_holes_and_counts_are_not_clipped(client,profile):
    outer=box(-1.30,51.75,-1.28,51.77)
    hole=box(-1.295,51.755,-1.285,51.765)
    summary=capture(profile,area=mapping(Polygon(outer.exterior.coords,[hole.exterior.coords])))
    assert client.get('/api/acquisitions',params={'bbox':'-1.294,51.756,-1.286,51.764'}).json()['entries']==[]
    all_entry=client.get('/api/acquisitions').json()['entries'][0]
    clipped=client.get('/api/acquisitions',params={'bbox':'-1.301,51.749,-1.299,51.751'}).json()['entries'][0]
    assert clipped==all_entry
    assert clipped['acquisition_id']==summary['acquisition_id']


def test_weather_point_does_not_expand_to_model_grid(client):
    store.acquire('org',weather_request(),client=WeatherProvider().client())
    assert len(client.get('/api/acquisitions',params={'bbox':'-1.256,51.744,-1.254,51.746'}).json()['entries'])==1
    assert client.get('/api/acquisitions',params={'bbox':'-1.250,51.740,-1.240,51.750'}).json()['entries']==[]


@pytest.mark.parametrize('start,end,expected',[
    ('2024-02-27','2024-02-27',0),('2024-02-28','2024-02-28',1),
    ('2024-02-29','2024-02-29',1),('2024-03-01','2024-03-01',1),('2024-03-02','2024-03-02',0),
])
def test_weather_inclusive_dates_and_unknown_vector_dates(client,profile,start,end,expected):
    capture(profile)
    store.acquire('org',weather_request(),client=WeatherProvider().client())
    entries=client.get('/api/acquisitions',params={'start_date':start,'end_date':end}).json()['entries']
    assert len(entries)==expected
    assert all(e['family']=='weather_timeseries' for e in entries)


def test_satellite_filters_actual_observation_and_capture_basis_is_explicit(client,profile):
    satellite=SatelliteProvider()
    store.acquire('org',satellite.request(),client=satellite.client())
    vector=capture(profile)
    for day,count in [('2025-06-01',0),('2025-06-19',1),('2025-06-30',0)]:
        response=client.get('/api/acquisitions',params={'start_date':day,'end_date':day})
        assert len(response.json()['entries'])==count
    day=vector['completed'][:10]
    params={'start_date':day,'end_date':day,'time_basis':'capture'}
    entries=client.get('/api/acquisitions',params=params).json()['entries']
    assert len(entries)==2
    assert next(e for e in entries if e['family']=='vector')['evidence_time']['kind']=='unknown'


def test_pagination_ties_filters_and_tenant_bound_cursor(client,profile):
    values=[capture(profile,str(i)) for i in range(4)]
    with core.engine.begin() as c:
        c.execute(update(store.requests).values(created='2025-01-01T00:00:00+00:00'))
    ids=[];params={'limit':1};first_cursor=None
    while True:
        response=client.get('/api/acquisitions',params=params)
        assert response.status_code==200,response.text
        page=response.json();ids.extend(e['acquisition_id'] for e in page['entries'])
        if page['scan_complete']: break
        first_cursor=first_cursor or page['next_cursor']
        params['cursor']=page['next_cursor']
    assert ids==sorted([v['acquisition_id'] for v in values],reverse=True)
    assert len(set(ids))==4
    assert client.get('/api/acquisitions',params={'limit':2,'cursor':first_cursor}).status_code==422
    assert client.get('/api/acquisitions',params={'limit':1,'cursor':first_cursor,'bbox':'-2,51,0,53'}).status_code==422
    api.app.dependency_overrides[api.organization]=lambda:'other'
    assert client.get('/api/acquisitions',params={'limit':1,'cursor':first_cursor}).status_code==422
    assert client.get('/api/acquisitions').json()['entries']==[]
    assert client.get('/api/acquisitions/'+values[0]['acquisition_id'],params={'attempt_id':values[0]['attempt_id']}).status_code==404


def test_bounded_scan_can_return_empty_page_with_continuation(client,profile):
    for i in range(catalogue.SCAN_LIMIT+2): capture(profile,str(i))
    params={'source_id':'nasa.power_merra2_daily'}
    first=client.get('/api/acquisitions',params=params).json()
    assert first['entries']==[] and first['scanned_count']==50 and not first['scan_complete']
    second=client.get('/api/acquisitions',params={**params,'cursor':first['next_cursor']}).json()
    assert second['entries']==[] and second['scanned_count']==2 and second['scan_complete']
    assert second['next_cursor'] is None


def test_failed_attempts_and_inflight_requests_are_not_catalogue_entries(client,profile):
    failed=store.acquire('org',request(profile,'retry'),client=Provider(failure='network').client())
    assert client.get('/api/acquisitions').json()['entries']==[]
    success=capture(profile,'retry')
    entry=client.get('/api/acquisitions').json()['entries'][0]
    assert entry['attempt_id']==success['attempt_id']!=failed['attempt_id']
    path='/api/acquisitions/'+success['acquisition_id']
    assert client.get(path).status_code==422
    assert client.get(path,params={'attempt_id':failed['attempt_id']}).status_code==404
    for state in ('pending','running'):
        with core.engine.begin() as c: c.execute(update(store.requests).values(state=state))
        assert client.get('/api/acquisitions').json()['entries']==[]


@pytest.mark.parametrize('fault',['request_hash','missing_attempt','manifest_bytes','manifest_envelope','source_identity','geometry','count'])
def test_corrupt_retained_metadata_fails_closed_and_sanitized(client,profile,fault):
    summary=capture(profile)
    key,manifest=manifest_of(summary)
    if fault=='request_hash':
        with core.engine.begin() as c: c.execute(update(store.requests).values(request_hash='private-secret'))
    elif fault=='missing_attempt':
        with core.engine.begin() as c: c.execute(delete(store.attempts))
    elif fault=='manifest_bytes': core.store_object(key,b'private-secret')
    else:
        if fault=='manifest_envelope': manifest['attempt_id']='private-secret'
        elif fault=='source_identity': manifest['source']['source_id']='private-secret'
        elif fault=='geometry': manifest['geometry_fingerprint']='private-secret'
        else: manifest['result']['feature_count']=-1
        content=encode(manifest);sha=digest(content)
        new_key=store._object_key('org',sha);core.store_object_immutable(new_key,content)
        with core.engine.begin() as c: c.execute(update(store.attempts).values(manifest_key=new_key,manifest_sha256=sha))
    response=client.get('/api/acquisitions')
    assert response.status_code==500,response.text
    assert response.json()=={'detail':'Retained acquisition could not be verified'}


@pytest.mark.parametrize('params',[
    {'bbox':''},{'bbox':'NaN,0,1,2'},{'bbox':'0,0,Infinity,2'},{'bbox':'2,0,1,2'},
    {'bbox':'-181,0,1,2'},{'bbox':'0,0,1'},{'bbox':'0,0,1,91'},
    {'start_date':'2024-01-01'},{'end_date':'2024-01-01'},
    {'start_date':'2024-02-01','end_date':'2024-01-01'},
    {'start_date':'9999-12-31','end_date':'9999-12-31'},
    {'limit':0},{'limit':21},{'source_id':'made_up'},{'time_basis':'forecast'},
    {'cursor':'invalid'},{'cursor':'x'*2001},{'org':'another-tenant'},
])
def test_invalid_query_is_rejected(client,params):
    assert client.get('/api/acquisitions',params=params).status_code==422


def test_gets_do_not_write_or_contact_providers(client,profile,monkeypatch):
    summary=capture(profile)
    before={p.relative_to(core.ROOT):digest(p.read_bytes()) for p in (core.ROOT/'objects').rglob('*') if p.is_file()}
    def reject_write(*args,**kwargs): raise AssertionError('Unexpected object write')
    monkeypatch.setattr(core,'store_object',reject_write)
    monkeypatch.setattr(core,'store_object_immutable',reject_write)
    from backend import acquisition_sources
    monkeypatch.setattr(acquisition_sources.BoundedClient,'__init__',reject_write)
    def read_only(conn,cursor,statement,params,context,many):
        assert statement.lstrip().upper().startswith('SELECT'),statement
    event.listen(core.engine,'before_cursor_execute',read_only)
    try:
        entry=client.get('/api/acquisitions').json()['entries'][0]
        assert client.get(entry['detail_path']).status_code==200
        assert store.read_acquisition('org',summary['acquisition_id'])==summary
    finally: event.remove(core.engine,'before_cursor_execute',read_only)
    after={p.relative_to(core.ROOT):digest(p.read_bytes()) for p in (core.ROOT/'objects').rglob('*') if p.is_file()}
    assert before==after


def test_authentication_validates_signed_tenant_claims(database,profile,monkeypatch):
    # Local public key replaces only JWKS retrieval. Actual JWT signature/claim
    # validation and production organization dependency execute unchanged.
    summary=capture(profile)
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    monkeypatch.setenv('CRC_ENV','production')
    monkeypatch.setenv('SUPABASE_URL','https://auth.test')
    monkeypatch.setattr(jwt.PyJWKClient,'get_signing_key_from_jwt',lambda self,token:SimpleNamespace(key=private.public_key()))
    client=TestClient(api.app,raise_server_exceptions=False) # no hosted lifespan/deployment claim
    claims={'sub':'user','exp':int(datetime.now(timezone.utc).timestamp())+300,'aud':'authenticated',
        'iss':'https://auth.test/auth/v1','app_metadata':{'org_id':'org'}}
    def headers(value): return {'Authorization':'Bearer '+jwt.encode(value,private,algorithm='RS256')}
    assert client.get('/api/acquisitions').status_code==401
    assert client.get('/api/acquisitions',headers={'Authorization':'Bearer invalid','X-Org-Id':'org'}).status_code==401
    assert client.get('/api/acquisitions',headers=headers(claims)).json()['entries'][0]['acquisition_id']==summary['acquisition_id']
    for change in ({'exp':1},{'aud':'wrong'},{'iss':'https://other.test'},{'app_metadata':{}},{'app_metadata':{'org_id':3}}):
        assert client.get('/api/acquisitions',headers=headers({**claims,**change})).status_code==401
    other=headers({**claims,'app_metadata':{'org_id':'other'}})
    assert client.get('/api/acquisitions',headers=other).json()['entries']==[]
    path='/api/acquisitions/'+summary['acquisition_id']
    assert client.get(path,params={'attempt_id':summary['attempt_id']},headers=other).status_code==404
    assert client.get(path,params={'attempt_id':summary['attempt_id']}).status_code==401
    forged=jwt.encode(claims,rsa.generate_private_key(public_exponent=65537,key_size=2048),algorithm='RS256')
    assert client.get('/api/acquisitions',headers={'Authorization':'Bearer '+forged}).status_code==401


def test_openapi_has_typed_read_only_routes(client):
    schema=client.get('/openapi.json').json()
    for path,model in [('/api/acquisitions','AcquisitionCatalogue'),('/api/acquisitions/{id}','AcquisitionDetail')]:
        assert set(schema['paths'][path])=={'get'}
        assert schema['paths'][path]['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/'+model)
