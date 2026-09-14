"""Synthetic Scotland source isolation, component identity and retained-history tests."""
from copy import deepcopy
import json

import httpx
import pytest
from pydantic import ValidationError
from shapely.geometry import box, mapping

from backend import core, acquisition as service, acquisition_sources as sources
from backend.acquisition_contracts import AcquisitionRequest, AcquisitionError, encode, digest
from test_geographic_acquisition import database, profile, Provider, request


@pytest.fixture
def scotland_profile(database):
    payload = {'version':sources.SCOTLAND_COVERAGE_VERSION,'endpoint':sources.FULL_EXTENT_COVERAGE_URL,
               'coordinate_precision_decimal_degrees':10,
               'synthetic':True,'feature':{'type':'Feature','properties':{'CTRY24CD':'S92000003'},
                                         'geometry':mapping(box(-8,54.8,0,61))}}
    data=encode(payload);sha=digest(data)
    core.store_object_immutable(sources._profile_key(sha),data)
    return sha


def scottish_request(sha, key='scottish-test'):
    return {**request(sha,key,area=mapping(box(-3.2,55.93,-3.14,55.97))),
            'source_id':'naturescot.sssi','adapter_version':'naturescot_sssi_arcgis_v1'}


def component(oid=1, code=91):
    return {'type':'Feature','id':oid,'geometry':mapping(box(-3.18,55.94,-3.17,55.95)),
            'properties':{'OBJECTID':oid,'PA_CODE':code,'STATUS':'Current','TYPE':'MIXED',
                          'UPDATED':1386288000000,'NAME':'SYNTHETIC SSSI'}}


class ScottishProvider(Provider):
    def __init__(self, features=None, failure=None):
        super().__init__([component(1),component(2)] if features is None else features, failure)
        self.item_calls=0

    def handle(self, req):
        if str(req.url).startswith(sources.SCOTLAND_ITEM):
            self.calls.append(req);self.item_calls+=1
            value={'id':sources.SCOTLAND_ITEM.rsplit('/',1)[1],'owner':'SNH_Maps','orgId':'LM9GyVFsughzHdbO',
                   'url':sources.SCOTLAND_URL.rsplit('/',1)[0],'type':'Feature Service',
                   'licenseInfo':'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'}
            if self.failure=='owner':value['owner']='untrusted-copy'
            if self.failure=='licence':value['licenseInfo']=None
            if self.failure=='item_changed' and self.item_calls>1:value['modified']=123
            return httpx.Response(200,json=value)
        assert str(req.url).startswith(sources.SCOTLAND_URL)
        response=super().handle(req)
        if not req.url.path.endswith('/query'):
            value=response.json()
            value['serviceItemId']=sources.SCOTLAND_ITEM.rsplit('/',1)[1]
            value['fields']=[{'name':'OBJECTID','type':'esriFieldTypeOID'},
                {'name':'PA_CODE','type':'esriFieldTypeInteger'}, {'name':'STATUS','type':'esriFieldTypeString'},
                {'name':'TYPE','type':'esriFieldTypeString'}, {'name':'UPDATED','type':'esriFieldTypeDate'}]
            if self.failure=='schema':value['fields'][1]['type']='esriFieldTypeString'
            return httpx.Response(200,json=value)
        return response


def test_components_keep_shared_designation_identity_and_provider_attributes(scotland_profile):
    provider=ScottishProvider()
    result=service.acquire('org',scottish_request(scotland_profile),client=provider.client())
    assert result['state']=='succeeded'
    assert result['source']['publisher']=='NatureScot' and result['source']['jurisdiction']=='Scotland'
    assert result['result']['feature_count']==2 and result['result']['designation_count']==1
    assert result['result']['native_feature_ids']==[1,2]
    assert result['result']['native_designation_ids']==[91]
    assert result['result']['observation_time'] is None and result['result']['publication_time'] is None
    sha=result['artifact_checksums']['normalized_selection']['sha256']
    features=json.loads(core.load_object(service._object_key('org',sha)))['features']
    assert [f['properties'] for f in features]==[component(1)['properties'],component(2)['properties']]
    assert {'provider_item_before','provider_item_after'} <= result['artifact_checksums'].keys()
    original=len(provider.calls)
    assert service.acquire('org',scottish_request(scotland_profile),client=provider.client())==result
    assert len(provider.calls)==original
    assert service.read_acquisition('org',result['acquisition_id'])==result
    with pytest.raises(AcquisitionError,match='not_found'):
        service.read_acquisition('other-org',result['acquisition_id'])


@pytest.mark.parametrize('source,adapter',[('natural_england.sssi','naturescot_sssi_arcgis_v1'),
                                          ('naturescot.sssi','sssi_arcgis_v2')])
def test_source_adapter_pairs_are_bound_before_persistence(scotland_profile,source,adapter):
    value={**scottish_request(scotland_profile),'source_id':source,'adapter_version':adapter}
    with pytest.raises(ValidationError,match='source_adapter_mismatch'):
        AcquisitionRequest.model_validate(value)


def test_english_profile_cannot_establish_scottish_coverage(profile):
    provider=ScottishProvider()
    result=service.acquire('org',scottish_request(profile),client=provider.client())
    assert result['error_code']=='coverage_version_mismatch' and not provider.calls


@pytest.mark.parametrize('bounds',[(-1.3,51.7,-1.2,51.8),(-6,54.6,-5.99,54.61),(-3.2,51.5,-3.19,51.51),
                                    (-2,54.799,-1.999,54.801),(-14,57.5,-13.99,57.51)])
def test_unsupported_area_is_not_silently_clipped(scotland_profile,bounds):
    value=scottish_request(scotland_profile);value['area']=mapping(box(*bounds))
    provider=ScottishProvider()
    result=service.acquire('org',value,client=provider.client())
    assert result['error_code']=='unsupported_geography' and not provider.calls


def test_shetland_geometry_and_scotland_profile_are_supported(scotland_profile):
    value=scottish_request(scotland_profile);value['area']=mapping(box(-1.3,60.1,-1.29,60.11))
    assert sources.validate_capabilities(AcquisitionRequest.model_validate(value))['version']==sources.SCOTLAND_COVERAGE_VERSION


def test_historical_time_rejected_before_provider_access(scotland_profile):
    value=scottish_request(scotland_profile)
    value['temporal']={'mode':'interval','start':'2010-01-01','end':'2020-01-01'}
    provider=ScottishProvider()
    assert service.acquire('org',value,client=provider.client())['error_code']=='unsupported_time'
    assert not provider.calls


@pytest.mark.parametrize('failure,code',[('owner','source_identity_or_terms_changed'),('licence','source_identity_or_terms_changed'),
    ('schema','source_schema_changed'),('item_changed','source_changed_during_capture'),
    ('truncated','incomplete_selection'),('missing','inconsistent_feature_ids'),('changed','source_changed_during_capture')])
def test_scottish_failures_are_explicit_and_retry_appends(scotland_profile,failure,code):
    first=service.acquire('org',scottish_request(scotland_profile),client=ScottishProvider(failure=failure).client())
    assert first['error_code']==code and first['result'] is None
    second=service.acquire('org',scottish_request(scotland_profile),client=ScottishProvider().client())
    assert second['state']=='succeeded' and len(second['attempts'])==2
    assert service.read_acquisition('org',first['acquisition_id'],attempt_id=first['attempt_id'])['manifest_sha256']==first['manifest_sha256']


@pytest.mark.parametrize('field,value,code',[('PA_CODE',None,'invalid_source_geometry_or_identity'),
    ('PA_CODE',True,'invalid_source_geometry_or_identity'),('STATUS','Denotified','unsupported_designation_status_or_type'),
    ('TYPE','SSSI','unsupported_designation_status_or_type'),('UPDATED','2013','invalid_provider_record_update')])
def test_source_semantics_are_not_coerced_or_silently_filtered(scotland_profile,field,value,code):
    f=component();f['properties'][field]=value
    result=service.acquire('org',scottish_request(scotland_profile),client=ScottishProvider([f]).client())
    assert result['error_code']==code and result['result'] is None
    assert 'assembled_provider_candidates' in result['artifact_checksums']


def test_known_empty_and_null_update_stay_distinct(scotland_profile):
    empty=service.acquire('org',scottish_request(scotland_profile,'empty'),client=ScottishProvider([]).client())
    assert empty['state']=='succeeded' and empty['result']['designation_count']==0
    f=component();f['properties']['UPDATED']=None
    unknown=service.acquire('org',scottish_request(scotland_profile,'unknown-date'),client=ScottishProvider([f]).client())
    assert unknown['state']=='succeeded' and unknown['result']['observation_time'] is None


def test_english_history_is_not_rebound_by_scottish_capture(profile,scotland_profile):
    old=service.acquire('org',request(profile),client=Provider().client())
    old_bytes=core.load_object(service._object_key('org',old['manifest_sha256']))
    new=service.acquire('org',scottish_request(scotland_profile),client=ScottishProvider().client())
    assert new['state']=='succeeded' and service.read_acquisition('org',old['acquisition_id'])==old
    assert core.load_object(service._object_key('org',old['manifest_sha256']))==old_bytes


@pytest.mark.parametrize('extra_precision',[False,True])
def test_scotland_coverage_preparation_uses_exact_country(database,extra_precision):
    calls=[]
    def provider(req):
        calls.append(req)
        if '/items/' in req.url.path:
            value={'id':sources.FULL_EXTENT_COVERAGE_ITEM.rsplit('/',1)[1],'owner':'ONSGeography_data',
                   'type':'Feature Service','url':sources.FULL_EXTENT_COVERAGE_URL.rsplit('/',1)[0]}
        elif req.url.path.endswith('/query'):
            assert req.url.params['where']=="CTRY24CD='S92000003'"
            assert req.url.params['geometryPrecision']=='10'
            value={'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:4326'}},
                   'features':[{'type':'Feature','properties':{'CTRY24CD':'S92000003'},'geometry':mapping(box(-8,54.8,0,61))}]}
            if extra_precision:
                value=json.loads(encode(value))
                ring=value['features'][0]['geometry']['coordinates'][0]
                ring[0][0]=ring[-1][0]=-0.0000000000001
        else:value={'geometryType':'esriGeometryPolygon','extent':{'spatialReference':{'wkid':27700}}}
        return httpx.Response(200,json=value)
    client=httpx.Client(transport=httpx.MockTransport(provider))
    if extra_precision:
        with pytest.raises(AcquisitionError,match='coverage_precision_mismatch'):
            sources.prepare_coverage(adapter_version='naturescot_sssi_arcgis_v1',client=client)
        return
    result=sources.prepare_coverage(adapter_version='naturescot_sssi_arcgis_v1',client=client)
    assert result['country']=='Scotland'
    profile,_=sources.load_coverage(result['coverage_profile_sha256'],expected_version=sources.SCOTLAND_COVERAGE_VERSION)
    assert profile['feature']['properties']['CTRY24CD']=='S92000003' and len(calls)==4


@pytest.mark.parametrize('wrong_codes',[False,True])
def test_independent_verifier_checks_components_and_designations(scotland_profile,monkeypatch,wrong_codes):
    from scripts import verify_geographic_acquisition as verification
    result=service.acquire('org',scottish_request(scotland_profile),client=ScottishProvider().client())
    class IndependentProvider(ScottishProvider):
        def handle(self,req):
            if req.url.params.get('returnGeometry')=='false':
                rows=[{'attributes':{'OBJECTID':i,'PA_CODE':999 if wrong_codes else 91}} for i in (1,2)]
                return httpx.Response(200,json={'features':rows})
            return super().handle(req)
    provider=IndependentProvider()
    monkeypatch.setattr(verification,'BoundedClient',lambda:sources.BoundedClient(provider.client()))
    if wrong_codes:
        with pytest.raises(AcquisitionError,match='independent_designation_mismatch'):
            verification.verify('org',result['acquisition_id'])
    else:
        checked=verification.verify('org',result['acquisition_id'])
        assert checked['independent_selection_match'] and checked['independent_designation_match']
        assert checked['designation_count']==1 and checked['feature_count']==2
