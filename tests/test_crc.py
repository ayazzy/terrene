import os,tempfile,time,json
os.environ['CRC_ENV']='development'
os.environ['CRC_DATA_DIR']=tempfile.mkdtemp(prefix='crc-test-')
test_url=os.environ.get('CRC_TEST_DATABASE_URL')
if test_url and not test_url.endswith('/crc_test'):raise RuntimeError('Postgres tests require a disposable database named crc_test')
os.environ['DATABASE_URL']=test_url or 'sqlite:///'+os.environ['CRC_DATA_DIR']+'/test.db'
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box,mapping,shape
from shapely.ops import transform
from sqlalchemy import delete,insert,select,update
from backend.core import *
from backend.api import app,organization
from backend import worker

@pytest.fixture(autouse=True)
def setup():
    init()
    with engine.begin() as c:
        for t in [design_revisions,design_alternatives,infrastructure_projects,
                  module_runs,land_evidence_snapshot_origins,
                  land_evidence_snapshot_links,land_evidence_snapshot_members,
                  land_evidence_snapshots,sites,assessments,features,datasets]:
            c.execute(delete(t))
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client():
    with TestClient(app) as c:yield c

def geom():return mapping(transform(backward,box(450000,210000,450100,210100)))
def source(state='available',bounds=PILOT):
    id=uid()
    with engine.begin() as c:
        c.execute(insert(datasets).values(id=id,key='synthetic-test-only',state=state,retrieved=now(),metadata={'name':'SYNTHETIC TEST FIXTURE','url':'https://example.invalid/synthetic','bbox':bounds,'limitations':'Synthetic test data only','synthetic':True}))
        g=geom();a,b,d,e=shape(g).bounds
        fid=uid();c.execute(insert(features).values(id=fid,dataset_id=id,geometry=g,minx=a,miny=b,maxx=d,maxy=e))
        if engine.dialect.name=='postgresql':c.execute(text('UPDATE features SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) WHERE id=:id'),{'g':json.dumps(g),'id':fid})
    return id

def create(client):
    r=client.post('/api/sites',json={'name':'Test site','geometry':geom()});assert r.status_code==200,r.text;return r.json()

def test_projected_area_and_actual_overlay(client):
    source();s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json();worker.once();r=client.get('/api/assessments/'+a['id']).json()['result']
    assert r['area_ha']==pytest.approx(1,abs=.002)
    assert r['findings'][0]['measured']==pytest.approx(1,abs=.002)
    assert r['findings'][0]['geometry']

@pytest.mark.parametrize('state,bounds',[('unavailable',PILOT),('available',[-1,51,-.9,51.1])])
def test_missing_is_unknown(client,state,bounds):
    source(state,bounds);s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json();worker.once();r=client.get('/api/assessments/'+a['id']).json()
    assert r['state']=='partial' and r['result']['findings'][0]['measured'] is None

@pytest.mark.parametrize('g',[
 {'type':'Polygon','coordinates':[[[-1.3,51.7],[-1.2,51.8],[-1.3,51.8],[-1.2,51.7],[-1.3,51.7]]]},
 {'type':'Polygon','coordinates':[[[-1.3,51.7],[-1.2,51.7],[-1.2,51.8]]]},
 {'type':'Point','coordinates':[-1.3,51.7]},
 {'type':'Polygon','coordinates':[[[450000,200000],[450100,200000],[450100,200100],[450000,200000]]]}])
def test_invalid_boundaries_rejected(client,g):assert client.post('/api/sites',json={'name':'bad','geometry':g}).status_code==422

def test_history_dedupe_report_and_decision(client):
    ds=source();s=create(client);endpoint='/api/sites/'+s['id'];a=client.post(endpoint+'/assessments').json();assert client.post(endpoint+'/assessments').json()['id']==a['id'];worker.once()
    assert client.patch(endpoint,json={'notes':'note','status':'Investigate','expected_version':1}).json()['version']==1
    g=mapping(transform(backward,box(450000,210000,450200,210100)))
    assert client.patch(endpoint,json={'geometry':g,'expected_version':1}).json()['version']==2
    assert client.patch(endpoint,json={'geometry':g,'expected_version':1}).status_code==409
    old=client.get('/api/assessments/'+a['id']).json();assert old['version']==1 and old['geometry']==s['geometry']
    new=client.post(endpoint+'/assessments').json();assert new['id']!=a['id'];worker.once()
    assert len(client.get(endpoint+'/assessments').json())==2
    report=client.get('/api/assessments/'+a['id']+'/report');assert report.status_code==200 and 'Historical assessment' in report.text and ds in report.text and 'Investigate' in report.text

def test_tenant_isolation_including_files(client):
    source();app.dependency_overrides[organization]=lambda:'org-a';s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json();worker.once()
    app.dependency_overrides[organization]=lambda:'org-b'
    assert client.get('/api/sites').json()==[]
    for path in ['/api/sites/'+s['id']+'/assessments','/api/assessments/'+a['id'],'/api/assessments/'+a['id']+'/report']:assert client.get(path).status_code==404
    assert client.post('/api/sites/'+s['id']+'/assessments').status_code==404
    assert client.patch('/api/sites/'+s['id'],json={'status':'Hold','expected_version':1}).status_code==404

def test_retries_and_stale_worker_fencing(client,monkeypatch):
    source();s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json()
    first=worker.claim();assert first and worker.claim() is None
    with engine.begin() as c:c.execute(update(assessments).where(assessments.c.id==a['id']).values(lease=0))
    second=worker.claim();assert second['token']!=first['token'] and second['attempts']==2
    with engine.begin() as c:
        r=c.execute(update(assessments).where(assessments.c.id==a['id'],assessments.c.token==first['token']).values(state='completed'));assert r.rowcount==0
        c.execute(update(assessments).where(assessments.c.id==a['id']).values(lease=0))
    monkeypatch.setattr(worker,'analyze',lambda _:(_ for _ in ()).throw(RuntimeError('transient failure')))
    worker.once();assert client.get('/api/assessments/'+a['id']).json()['state']=='failed';assert worker.claim() is None

def test_expired_last_lease_terminates(client):
    source();s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json()
    with engine.begin() as c:c.execute(update(assessments).where(assessments.c.id==a['id']).values(state='running',attempts=3,lease=0))
    assert worker.claim() is None
    assert client.get('/api/assessments/'+a['id']).json()['state']=='failed'

def test_production_auth_fails_closed(monkeypatch):
    monkeypatch.setenv('CRC_ENV','production')
    from fastapi import HTTPException
    with pytest.raises(HTTPException):organization(None)
    with pytest.raises(HTTPException):organization('Bearer forged-token')

def test_signed_hosted_tokens_isolate_orgs(client,monkeypatch):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import ec
    from types import SimpleNamespace
    source();private=ec.generate_private_key(ec.SECP256R1());public=private.public_key()
    monkeypatch.setenv('CRC_ENV','production');monkeypatch.setenv('SUPABASE_URL','https://test.supabase.co')
    monkeypatch.setattr(jwt.PyJWKClient,'get_signing_key_from_jwt',lambda self,token:SimpleNamespace(key=public))
    # Do not exercise hosted storage in this authentication-focused unit test.
    monkeypatch.setattr('backend.api.store_object',lambda *args:None)
    def headers(org):
        token=jwt.encode({'sub':'user-'+org,'exp':time.time()+60,'aud':'authenticated','iss':'https://test.supabase.co/auth/v1','app_metadata':{'org_id':org},'user_metadata':{'org_id':'org-a'}},private,algorithm='ES256')
        return {'Authorization':'Bearer '+token}
    a=client.post('/api/sites',json={'name':'Private A','geometry':geom()},headers=headers('org-a'));assert a.status_code==200
    id=a.json()['id'];assert client.get('/api/sites',headers=headers('org-b')).json()==[]
    assert client.post('/api/sites/'+id+'/assessments',headers=headers('org-b')).status_code==404
    assert len(client.get('/api/sites',headers=headers('org-a')).json())==1

def test_retry_backoff_and_success(client,monkeypatch):
    source();s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json()
    original=worker.analyze
    monkeypatch.setattr(worker,'analyze',lambda _:(_ for _ in ()).throw(RuntimeError('temporary')))
    worker.once();r=client.get('/api/assessments/'+a['id']).json()
    assert r['state']=='queued' and r['attempts']==1 and worker.claim() is None
    with engine.begin() as c:c.execute(update(assessments).where(assessments.c.id==a['id']).values(lease=0))
    monkeypatch.setattr(worker,'analyze',original);worker.once();r=client.get('/api/assessments/'+a['id']).json()
    assert r['state']=='completed' and r['attempts']==2

def test_boundary_file_authorization(client):
    app.dependency_overrides[organization]=lambda:'org-a';s=create(client)
    path='/api/sites/'+s['id']+'/boundary/1'
    assert client.get(path).status_code==200
    app.dependency_overrides[organization]=lambda:'org-b'
    assert client.get(path).status_code==404

def test_flood_observation_has_explicit_limits_and_rule(client):
    ds=source()
    with engine.begin() as c:c.execute(update(datasets).where(datasets.c.id==ds).values(key='flood'))
    s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json();worker.once()
    f=client.get('/api/assessments/'+a['id']).json()['result']['findings'][0]
    assert f['measured']==pytest.approx(1,abs=.002)
    assert f['rule_version']=='crc-flood-1'
    assert 'flood-risk specialist' in f['interpretation'] and 'not evidence of wetland suitability' in f['interpretation']

def test_failed_flood_import_keeps_old_assessment_and_latest_unknown(client,monkeypatch):
    from backend import import_data
    ds=source()
    with engine.begin() as c:c.execute(update(datasets).where(datasets.c.id==ds).values(key='flood'))
    s=create(client);a=client.post('/api/sites/'+s['id']+'/assessments').json();worker.once()
    monkeypatch.setattr(import_data,'fetch_flood',lambda _:(_ for _ in ()).throw(RuntimeError('incomplete upstream page')))
    import_data.run(['flood'])
    catalog=client.get('/api/datasets').json();assert len(catalog)==1 and catalog[0]['state']=='unavailable'
    old=client.get('/api/assessments/'+a['id']).json()
    assert old['result']['findings'][0]['dataset_version']==ds and old['state']=='completed'
    new=client.post('/api/sites/'+s['id']+'/assessments').json();assert new['id']!=a['id'];worker.once()
    unknown=client.get('/api/assessments/'+new['id']).json()
    assert unknown['state']=='partial' and unknown['result']['findings'][0]['measured'] is None

def test_combined_flood_zone_union_does_not_double_count(client):
    ds=source();g=geom();a,b,d,e=shape(g).bounds;fid=uid()
    with engine.begin() as c:
        c.execute(update(datasets).where(datasets.c.id==ds).values(key='flood'))
        c.execute(insert(features).values(id=fid,dataset_id=ds,geometry=g,minx=a,miny=b,maxx=d,maxy=e))
        if engine.dialect.name=='postgresql':c.execute(text('UPDATE features SET geom=ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) WHERE id=:id'),{'g':json.dumps(g),'id':fid})
    s=create(client);job=client.post('/api/sites/'+s['id']+'/assessments').json();worker.once()
    result=client.get('/api/assessments/'+job['id']).json()['result']
    assert result['findings'][0]['measured']==pytest.approx(1,abs=.002)
    assert result['findings'][0]['percent']==pytest.approx(100)
    assert any('hydrological' in step for step in result['next_steps'])


def test_nature_pipeline_saved_with_pinned_model_and_report(client):
    ds=source()
    with engine.begin() as c:c.execute(update(datasets).where(datasets.c.id==ds).values(key='flood'))
    s=create(client);job=client.post('/api/sites/'+s['id']+'/assessments').json()
    assert job['model_spec']['model_version']=='wetland_restoration_v0_1'
    worker.once()
    saved=client.get('/api/assessments/'+job['id']).json()
    r=saved['result'];model=r['wetland_model'];earth=r['environmental_state']
    assert model['signature']==job['model_spec']['signature']
    assert model['overall']['band']=='INSUFFICIENT_DATA'
    assert model['synthetic']
    assert earth['normalized']['hydrology']['mapped_flood_extent_fraction'][0]['raw_source_ids']==[ds]
    assert earth['raw'][0]['source_version']==ds
    report=client.get('/api/assessments/'+job['id']+'/report').text
    assert 'Wetland restoration model' in report and 'INSUFFICIENT DATA' in report
    assert ds in report and 'Complete model configuration and provenance' in report
    assert 'SYNTHETIC INPUTS' in report


def test_old_assessment_not_reused_after_model_introduced(client):
    source();s=create(client);path='/api/sites/'+s['id']+'/assessments'
    old=client.post(path).json();worker.once()
    with engine.begin() as c:
        result=dict(c.execute(select(assessments).where(assessments.c.id==old['id'])).mappings().one()['result'])
        result.pop('wetland_model');result.pop('environmental_state')
        c.execute(update(assessments).where(assessments.c.id==old['id']).values(model_spec=None,dedupe='legacy-fingerprint',result=result))
    new=client.post(path).json()
    assert new['id']!=old['id']
    assert 'predates the wetland model' in client.get('/api/assessments/'+old['id']+'/report').text
    assert client.get('/api/assessments/'+old['id']).json()['result']==result


def test_configuration_change_creates_new_job_and_worker_uses_pinned_config(client,monkeypatch):
    from backend.wetland import model_spec
    source();s=create(client);path='/api/sites/'+s['id']+'/assessments'
    old=client.post(path).json()
    config=model_spec()['config'];config['slope_zero_score_deg']=5
    new_spec=model_spec(config)
    monkeypatch.setattr('backend.api.model_spec',lambda:new_spec)
    new=client.post(path).json()
    assert old['id']!=new['id']
    worker.once();worker.once()
    assert client.get('/api/assessments/'+old['id']).json()['result']['wetland_model']['config']['slope_zero_score_deg']==10
    assert client.get('/api/assessments/'+new['id']).json()['result']['wetland_model']['config']['slope_zero_score_deg']==5


def test_import_keeps_original_before_geometry_repair(client,monkeypatch):
    from backend import import_data
    from pathlib import Path
    original={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'original_code':'KEEP'},
        'geometry':{'type':'Polygon','coordinates':[[[-1.3,51.7],[-1.2,51.8],[-1.3,51.8],[-1.2,51.7],[-1.3,51.7]]]}}]}
    monkeypatch.setattr(import_data,'fetch',lambda _:({},json.loads(json.dumps(original))))
    import_data.run(['sssi'])
    with engine.connect() as c:d=dict(c.execute(select(datasets)).mappings().one())
    assert d['state']=='available'
    root=ROOT/'objects'/'reference'/d['id']
    raw=json.loads((root/'source.json').read_text())
    normalized=json.loads((root/'normalized-geometry.json').read_text())
    assert raw==original
    assert not shape(raw['features'][0]['geometry']).is_valid
    assert shape(normalized['features'][0]['geometry']).is_valid
    assert normalized['features'][0]['properties']==original['features'][0]['properties']
    assert d['metadata']['reference_repairs']==1


def test_additive_model_migration_is_idempotent_and_preserves_legacy(tmp_path,monkeypatch):
    import backend.core as core
    from sqlalchemy import create_engine,inspect
    legacy=create_engine('sqlite:///'+str(tmp_path/'legacy.db'))
    with legacy.begin() as c:
        c.execute(text('CREATE TABLE assessments (id VARCHAR PRIMARY KEY, result JSON)'))
        c.execute(text('INSERT INTO assessments (id, result) VALUES (:id, :result)'), {'id':'saved','result':json.dumps({'v0':True})})
    monkeypatch.setattr(core,'engine',legacy)
    core.init();core.init()
    assert 'model_spec' in {c['name'] for c in inspect(legacy).get_columns('assessments')}
    with legacy.connect() as c:
        row=c.execute(text("SELECT result, model_spec FROM assessments WHERE id='saved'")).one()
        assert json.loads(row[0])=={'v0':True} and row[1] is None
    legacy.dispose()


def test_explicit_environment_refresh_creates_distinct_pinned_job(client):
    source();s=create(client);path='/api/sites/'+s['id']+'/assessments'
    original=client.post(path).json()
    assert client.post(path).json()['id']==original['id']
    fresh=client.post(path+'?refresh_environment=true').json()
    second=client.post(path+'?refresh_environment=true').json()
    assert len({original['id'],fresh['id'],second['id']})==3
    assert fresh['model_spec']['refresh_sources'] is True
    assert original['model_spec']['refresh_sources'] is False
