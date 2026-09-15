"""Daily weather provenance, missingness, immutable history and native-unit checks."""
from datetime import datetime, timezone
import json

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import select,func

from backend import acquisition as service, acquisition_weather as weather, core
from backend.acquisition_contracts import AcquisitionError, encode, parse_request
from test_geographic_acquisition import database


def request(key='weather'):
    return {'contract_version':'geographic_weather_request_v1','source_id':weather.SOURCE,'adapter_version':weather.ADAPTER,
        'point':{'type':'Point','coordinates':[-1.255,51.745]},'start_date':'2024-02-28','end_date':'2024-03-01',
        'time_standard':'UTC','idempotency_key':key}


class Provider:
    def __init__(self, fault=None): self.calls=[];self.fault=fault
    def response(self,req):
        start=req.url.params['start'];end=req.url.params['end']
        value={'type':'Feature','geometry':{'type':'Point','coordinates':[-1.255,51.745,112.12]},
            'header':{'title':'NASA/POWER Source Native Resolution Daily Data','api':{'name':'POWER Daily API','version':'v2.9.7'},
                'sources':['MERRA2','POWER'],'fill_value':-999.0,'time_standard':'UTC','start':start,'end':end},
            'messages':[],'parameters':{k:{'units':v[0],'longname':v[1]} for k,v in weather.VARIABLES.items()},
            'properties':{'parameter':{k:{d:({'T2M':10,'T2M_MIN':0,'T2M_MAX':20,'PRECTOTCORR':0,'WS10M':2,'RH2M':70}[k])
                for d in ['20240228','20240229','20240301'] if start <= d <= end} for k in weather.VARIABLES}},
            'times':{'process':len(self.calls)}}
        if self.fault=='unit': value['parameters']['T2M']['units']='K'
        if self.fault=='model': value['header']['sources']=['GEOSIT','POWER']
        if self.fault=='time': value['header']['time_standard']='LST'
        if self.fault=='location': value['geometry']['coordinates'][0]+=1
        if self.fault=='fill': value['header']['fill_value']=-9999
        if self.fault=='warning': value['messages']=['synthetic warning']
        if self.fault=='variable': del value['properties']['parameter']['WS10M']
        if self.fault=='extra_date': value['properties']['parameter']['WS10M']['20240302']=1
        if self.fault=='negative_rain': value['properties']['parameter']['PRECTOTCORR']['20240228']=-1
        if self.fault=='temperature': value['properties']['parameter']['T2M_MAX']['20240228']=-5
        if self.fault=='bool': value['properties']['parameter']['WS10M']['20240228']=True
        if self.fault=='changed' and len(self.calls)>1: value['properties']['parameter']['RH2M']['20240228']=80
        if self.fault=='gaps':
            del value['properties']['parameter']['WS10M']['20240228']
            value['properties']['parameter']['WS10M']['20240229']=None
            value['properties']['parameter']['WS10M']['20240301']=-999
        if self.fault=='empty':
            for parameter in value['properties']['parameter'].values(): parameter.clear()
        return value
    def handle(self,req):
        self.calls.append(req)
        assert str(req.url).startswith(weather.ENDPOINT)
        assert req.url.params['time-standard']=='UTC' and req.url.params['community']=='AG'
        if self.fault=='network': raise httpx.ConnectError('synthetic',request=req)
        if self.fault=='redirect': return httpx.Response(302,headers={'location':'http://127.0.0.1/private'})
        if self.fault=='duplicate': return httpx.Response(200,content=b'{"type":"Feature","type":"Other"}')
        if self.fault=='nan': return httpx.Response(200,content=b'{"x":NaN}')
        return httpx.Response(200,json=self.response(req))
    def client(self): return httpx.Client(transport=httpx.MockTransport(self.handle))


def test_capture_leap_day_units_original_bytes_and_no_legacy_writes(database):
    tables=(core.sites,core.assessments,core.datasets,core.features,core.land_evidence_snapshots,core.module_runs)
    with core.engine.connect() as c:
        before={t.name:c.execute(select(func.count()).select_from(t)).scalar_one() for t in tables}
    p=Provider();value=service.acquire('org',request(),client=p.client())
    assert value['state']=='succeeded' and len(p.calls)==2
    assert value['result']['evidence_kind']=='modelled_reanalysis' and value['result']['native_grid_cell_id'] is None
    assert value['result']['variables']['PRECTOTCORR']['unit']=='mm/day'
    series=service.read_acquisition_artifact('org',value['acquisition_id'],'series')
    rain=next(r for r in series['variables'] if r['variable']=='PRECTOTCORR')['daily']
    assert [r['date'] for r in rain]==['2024-02-28','2024-02-29','2024-03-01']
    assert all(r['value']==0 and r['state']=='present' for r in rain)
    raw=service.read_acquisition_artifact('org',value['acquisition_id'],'provider_response_before')
    assert isinstance(raw,bytes) and json.loads(raw)['header']['sources']==['MERRA2','POWER']
    assert service.acquire('org',request(),client=p.client())==value and len(p.calls)==2
    with core.engine.connect() as c:
        assert {t.name:c.execute(select(func.count()).select_from(t)).scalar_one() for t in tables}==before


@pytest.mark.parametrize('fault,code',[
 ('unit','weather_unit_or_schema_changed'),('model','weather_source_identity_changed'),('time','weather_time_mismatch'),
 ('location','weather_location_mismatch'),('fill','weather_fill_schema_changed'),('warning','weather_provider_warning'),
 ('variable','weather_variable_schema_changed'),('extra_date','weather_unexpected_date'),('negative_rain','weather_value_out_of_range'),
 ('temperature','weather_temperature_inconsistent'),('bool','weather_value_out_of_range'),('changed','source_changed_during_capture'),
 ('network','network_failure'),('redirect','network_failure'),('duplicate','invalid_weather_json'),('nan','invalid_weather_json')])
def test_unsafe_responses_fail_and_retry_preserves_history(database,fault,code):
    p=Provider(fault);failed=service.acquire('org',request(),client=p.client())
    assert failed['state']=='failed' and failed['error_code']==code and failed['result'] is None
    p.fault=None
    success=service.acquire('org',request(),client=p.client())
    assert success['state']=='succeeded'
    old=service.read_acquisition('org',success['acquisition_id'],attempt_id=failed['attempt_id'])
    assert old['manifest_sha256']==failed['manifest_sha256']


@pytest.mark.parametrize('fault',['gaps','empty'])
def test_missing_values_are_explicit_not_zero_or_fabricated_dates(database,fault):
    p=Provider(fault);value=service.acquire('org',request(),client=p.client())
    assert value['state']=='succeeded'
    coverage=value['result']['variables']['WS10M']
    assert coverage['availability']=='no_valid_days' and coverage['missing_days']==3
    if fault=='gaps': assert coverage['missingness_counts']=={'present':0,'provider_fill':1,'provider_null':1,'absent_date':1}
    rows=service.read_acquisition_artifact('org',value['acquisition_id'],'series')['variables']
    assert all(day['value'] is None for r in rows if r['variable']=='WS10M' for day in r['daily'])


@pytest.mark.parametrize('change',[
 {'start_date':'2024-02-30'},{'start_date':'2023-01-01'},{'end_date':'2024-02-01'},{'start_date':'1980-01-01','end_date':'1980-01-02'},
 {'time_standard':'LST'},{'point':{'type':'Point','coordinates':[181,51]}},{'point':{'type':'Point','coordinates':[0,0,4]}},
 {'point':{'type':'Polygon','coordinates':[]}},{'source_id':'nasa.other'}, {'area':{}},])
def test_typed_point_and_interval_contract_rejects_ambiguous_inputs(change):
    with pytest.raises(ValidationError): parse_request({**request(),**change})


def test_recent_period_fails_before_provider_access(database):
    today=datetime.now(timezone.utc).date().isoformat();p=Provider()
    value=service.acquire('org',{**request(),'start_date':today,'end_date':today},client=p.client())
    assert value['error_code']=='weather_period_not_mature' and p.calls==[]


def test_tenant_isolation_tampering_and_idempotency(database):
    value=service.acquire('org',request(),client=Provider().client())
    with pytest.raises(AcquisitionError,match='not_found'): service.read_acquisition('other',value['acquisition_id'])
    with pytest.raises(AcquisitionError,match='idempotency_conflict'):
        service.acquire('org',{**request(),'point':{'type':'Point','coordinates':[0,51]}},client=Provider().client())
    sha=value['artifact_checksums']['provider_response_before']['sha256']
    key=service._object_key('org',sha).removesuffix('.json')+'.bin';(core.ROOT/'objects'/key).write_bytes(b'corrupt')
    with pytest.raises(AcquisitionError,match='integrity_failure'): service.read_acquisition('org',value['acquisition_id'])


def test_byte_limit(database,monkeypatch):
    monkeypatch.setitem(weather.LIMITS,'max_response_bytes',10)
    result=service.acquire('org',request(),client=Provider().client())
    assert result['error_code']=='byte_limit'


def test_cli_dispatch(database,tmp_path,monkeypatch,capsys):
    original=weather.fetch_weather
    monkeypatch.setattr(weather,'fetch_weather',lambda request,**kwargs:original(request,**{**kwargs,'client':Provider().client()}))
    path=tmp_path/'weather.json';path.write_bytes(encode(request()))
    assert service.main(['acquire','--org','org','--request',str(path)])==0
    assert json.loads(capsys.readouterr().out)['result']['source_model']=='MERRA-2'


@pytest.mark.parametrize('live',[False,True])
def test_offline_replay_and_independent_daily_verification(database,live):
    from scripts.verify_weather_acquisition import verify_weather
    p=Provider();summary=service.acquire('org',request(),client=p.client());before=len(p.calls)
    result=verify_weather('org',summary,live=live,client=p.client())
    assert result['offline_response_replay_match']
    assert len(result['samples'])==(18 if live else 0)
    assert len(p.calls)-before==(3 if live else 0)


def test_verifier_detects_changed_live_values(database):
    from scripts.verify_weather_acquisition import verify_weather
    p=Provider();summary=service.acquire('org',request(),client=p.client());p.fault='changed'
    with pytest.raises(AcquisitionError,match='independent_weather_sample_mismatch'):
        verify_weather('org',summary,client=p.client())


def test_unknown_evidence_fields_are_not_silently_discarded():
    req=parse_request(request());p=Provider()
    value=p.response(httpx.Request('GET',weather.ENDPOINT,params=weather.parameters(req)))
    value['new_quality_flags']=['unreviewed']
    with pytest.raises(AcquisitionError,match='weather_response_schema_changed'):
        weather.normalize(value,req)
