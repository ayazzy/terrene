"""Dated imagery, calibration identity, bounded native range IO and evidence isolation."""
from copy import deepcopy
import json

import httpx
import numpy as np
import pytest
from pydantic import ValidationError
from pyproj import Transformer
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.windows import Window
from shapely.geometry import box, mapping, Polygon
from shapely.ops import transform
from sqlalchemy import select, func

from backend import acquisition as service, acquisition_satellite as satellite, core
from backend.acquisition_contracts import AcquisitionError, BinaryArtifact, digest, encode, parse_request
from backend.satellite_ranges import ReplaySource, RangeSource
from backend.acquisition_sources import BoundedClient
from test_geographic_acquisition import database


def geographic(polygon):
    return mapping(transform(Transformer.from_crs(32630,4326,always_xy=True).transform,polygon))


class Provider:
    def __init__(self, fault=None, fill=None):
        self.fault, self.calls, self.metadata_calls, self.range_calls = fault, [], 0, 0
        self.scene = 'S2C_T30UXC_20250619T110803_L2A'
        self.item = {'type':'Feature','stac_version':'1.0.0','id':self.scene,'collection':satellite.COLLECTION,
            'geometry':geographic(box(600000,5690220,709800,5800020)),
            'properties':{'datetime':'2025-06-19T11:17:06.796000Z','platform':'sentinel-2c',
                'constellation':'sentinel-2','proj:epsg':32630,'eo:cloud_cover':70,
                's2:product_type':'S2MSI2A','s2:processing_baseline':'05.11',
                's2:product_uri':'SYNTHETIC_PRODUCT.SAFE'},'assets':{},'links':[]}
        self.content = {}
        for key,(name,resolution) in satellite.BANDS.items():
            dtype = 'uint8' if key == 'scl' else 'uint16'
            data = np.full((64,64),4 if key == 'scl' else 1500,dtype=dtype)
            if fill: fill(key,data)
            with MemoryFile() as memory:
                with memory.open(driver='GTiff',width=109800//resolution,height=109800//resolution,count=1,
                                 dtype=dtype,crs='EPSG:32630',transform=from_origin(600000,5800020,resolution,resolution),
                                 nodata=0,tiled=True,blockxsize=256,blockysize=256,compress='deflate',sparse_ok=True) as ds:
                    ds.write(data,1,window=Window(0,0,64,64))
                content = memory.read()
            self.content[key] = content
            self.item['assets'][key] = {'href':satellite.ASSET_ROOT+satellite.COLLECTION+'/30/U/XC/2025/6/'+self.scene+'/'+name+'.tif',
                'type':'image/tiff; application=geotiff; profile=cloud-optimized','gsd':resolution,
                'proj:shape':[109800//resolution]*2,'proj:transform':[resolution,0,600000,0,-resolution,5800020],
                'raster:bands':[{'nodata':0,'data_type':dtype,'spatial_resolution':resolution,
                    **({} if key == 'scl' else {'scale':0.0001,'offset':-0.1})}],
                'file:size':len(content),'file:checksum':'1220'+digest(content),
                **({} if key == 'scl' else {'eo:bands':[{'name':name,'common_name':key}]})}
        self.area = geographic(box(600100,5799720,600300,5799920))

    def request(self,key='satellite',area=None):
        return {'contract_version':'geographic_satellite_request_v1','source_id':satellite.SOURCE,
            'adapter_version':satellite.ADAPTER,'area':area or self.area,
            'temporal':{'mode':'interval','start':'2025-06-01T00:00:00Z','end':'2025-06-30T23:59:59Z'},
            'scene_id':self.scene,'scene_metadata_sha256':digest(encode(self.item)), 'idempotency_key':key}

    def handle(self,request):
        self.calls.append(request)
        if request.url.host == 'earth-search.aws.element84.com':
            if request.url.path.endswith('/search'):
                return httpx.Response(200,json={'type':'FeatureCollection','features':[self.item],
                    'links':[{'rel':'next','href':'https://untrusted.example/next'}] if self.fault == 'next_page' else []})
            assert request.url.path.endswith('/items/'+self.scene)
            self.metadata_calls += 1
            item = deepcopy(self.item)
            if self.fault == 'metadata_change' and self.metadata_calls > 1: item['properties']['updated'] = 'changed'
            return httpx.Response(200,json=item)
        key = next(key for key,asset in self.item['assets'].items() if asset['href'] == str(request.url))
        self.range_calls += 1
        start,end = map(int,request.headers['range'].removeprefix('bytes=').split('-'))
        assert request.headers['accept-encoding'] == 'identity'
        content = self.content[key][start:end+1]
        headers={'content-range':f'bytes {start}-{end}/{len(self.content[key])}','etag':'"stable"'}
        if self.fault == 'no_etag': headers.pop('etag')
        if self.fault == 'wrong_range': headers['content-range'] = 'bytes 0-1/2'
        if self.fault == 'changed_asset' and self.range_calls > 1: headers['etag'] = '"changed"'
        if self.fault == 'truncated': content = content[:-1]
        if self.fault == 'network': raise httpx.ConnectError('synthetic',request=request)
        if self.fault == 'redirect': return httpx.Response(302,headers={'location':'http://127.0.0.1/private'})
        return httpx.Response(200 if self.fault == 'full_response' else 206,headers=headers,content=content)

    def client(self): return httpx.Client(transport=httpx.MockTransport(self.handle))


@pytest.fixture
def provider(database): return Provider()


def test_capture_native_bands_classification_calibration_and_readonly_retry(provider):
    tables = (core.sites,core.assessments,core.datasets,core.features,core.land_evidence_snapshots,core.module_runs)
    with core.engine.connect() as c:
        before = {table.name:c.execute(select(func.count()).select_from(table)).scalar_one() for table in tables}
    request = provider.request()
    result = service.acquire('org',request,client=provider.client())
    assert result['state'] == 'succeeded', result['error_code']
    bands = result['result']['bands']
    assert bands['red']['area_cell_count'] == bands['red']['valid_cell_count'] == 400
    assert bands['scl']['area_cell_count'] == bands['scl']['class_counts']['vegetation'] == 100
    assert bands['red']['calibration']['offset'] == -0.1
    assert result['result']['observation_time'] != result['started']
    assert result['result']['scene_cloud_cover_percent'] == 70  # not the local classification
    count = len(provider.calls)
    assert service.acquire('org',request,client=provider.client()) == result
    assert service.read_acquisition('org',result['acquisition_id']) == result
    assert len(provider.calls) == count
    with core.engine.connect() as c:
        assert {table.name:c.execute(select(func.count()).select_from(table)).scalar_one() for table in tables} == before
    for key in satellite.BANDS:
        raw = service.read_acquisition_artifact('org',result['acquisition_id'],key+'_window')
        with MemoryFile(raw) as memory, memory.open() as ds:
            assert ds.res == (satellite.BANDS[key][1],)*2
            assert np.all(ds.read(1) == (4 if key == 'scl' else 1500))


def test_captured_source_ranges_reproduce_every_native_window_without_network(provider):
    result = service.acquire('org',provider.request(),client=provider.client())
    artifacts = {name:service.read_acquisition_artifact('org',result['acquisition_id'],name) for name in result['artifact_checksums']}
    for key in satellite.BANDS:
        source = ReplaySource(artifacts['source_ranges'][key],artifacts,key)
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
            with rasterio.open(key+'.tif',opener=source.open,driver='GTiff') as ds:
                raw,summary = satellite.read_window(ds,result['request']['area'],provider.item['assets'][key],key,32630)
        assert raw == artifacts[key+'_window']
        assert summary == result['result']['bands'][key]


@pytest.mark.parametrize('fault,code',[
    ('metadata_change','source_changed_during_capture'),('no_etag','satellite_range_identity_invalid'),
    ('wrong_range','satellite_range_identity_invalid'),('truncated','satellite_range_truncated'),
    ('full_response','satellite_range_not_honoured'),('redirect','satellite_range_not_honoured'),
    ('changed_asset','source_changed_during_capture'),('network','network_failure')])
def test_unsafe_or_changed_responses_fail_and_retry_preserves_failed_history(database,fault,code):
    provider = Provider(fault)
    failed = service.acquire('org',provider.request(),client=provider.client())
    assert failed['error_code'] == code and failed['result'] is None
    provider.fault = None
    success = service.acquire('org',provider.request(),client=provider.client())
    assert success['state'] == 'succeeded'
    assert service.read_acquisition('org',success['acquisition_id'],attempt_id=failed['attempt_id'])['manifest_sha256'] == failed['manifest_sha256']


@pytest.mark.parametrize('change,code',[
    ('pin','scene_metadata_changed'),('url','unsafe_satellite_asset_url'),('scale','satellite_calibration_changed'),
    ('grid','satellite_asset_grid_mismatch'),('time','scene_outside_interval'),('area','scene_does_not_cover_area'),
    ('scene','satellite_scene_schema_changed')])
def test_request_and_metadata_constraints_before_asset_access(provider,change,code):
    if change == 'url': provider.item['assets']['red']['href'] = 'http://127.0.0.1/private'
    if change == 'scale': provider.item['assets']['red']['raster:bands'][0]['scale'] = 1
    if change == 'grid': provider.item['assets']['red']['proj:transform'][2] += 10
    if change == 'time': provider.item['properties']['datetime'] = '2024-06-19T11:00:00Z'
    if change == 'scene': provider.item['collection'] = 'sentinel-2-l2a'
    req = provider.request(area=mapping(box(-8,55,-7.99,55.01)) if change == 'area' else None)
    if change == 'pin': req['scene_metadata_sha256'] = '0'*64
    result = service.acquire('org',req,client=provider.client())
    assert result['error_code'] == code and provider.range_calls == 0


@pytest.mark.parametrize('start,end', [('2025-06-01','2025-06-30'),('2025-06-02T00:00:00Z','2025-06-01T00:00:00Z'),
    ('2020-01-01T00:00:00Z','2025-06-01T00:00:00Z'),('2025-02-30T00:00:00Z','2025-06-01T00:00:00Z')])
def test_intervals_are_explicit_valid_utc_and_bounded(provider,start,end):
    request = provider.request();request['temporal'].update(start=start,end=end)
    with pytest.raises(ValidationError): parse_request(request)


def test_no_source_role_or_historical_request_hash_changes(provider):
    from test_geographic_acquisition import request
    from backend.acquisition_contracts import AcquisitionRequest
    old = AcquisitionRequest.model_validate(request('0'*64))
    assert parse_request(old).model_dump() == old.model_dump()
    assert 'scene_id' not in old.model_dump()
    value = provider.request(); value['source_id'] = 'environment_agency.lidar_dtm_1m'
    with pytest.raises(ValidationError): parse_request(value)


@pytest.mark.parametrize('mode',['all_missing','some_missing','clouds','unknown_class'])
def test_nodata_and_provider_cloud_classes_are_not_clear_ground(database,mode):
    def fill(key,data):
        if mode == 'all_missing': data[:] = 0
        if mode == 'some_missing': data[:,15] = 0
        if mode == 'clouds' and key == 'scl': data[:] = 9
        if mode == 'unknown_class' and key == 'scl': data[:] = 12
    provider = Provider(fill=fill)
    result = service.acquire('org',provider.request(),client=provider.client())
    if mode == 'unknown_class':
        assert result['error_code'] == 'satellite_scl_schema_changed'
        return
    assert result['state'] == 'succeeded'
    bands = result['result']['bands']
    if mode == 'all_missing': assert bands['red']['coverage_state'] == 'no_valid_cells'
    if mode == 'some_missing': assert bands['red']['coverage_state'] == 'partial'
    if mode == 'clouds':
        assert bands['scl']['class_counts']['cloud_high_probability'] == 100
        assert bands['red']['coverage_state'] == 'complete'  # presence, not clear ground


def test_polygon_holes_and_small_area_centres(provider):
    polygon = Polygon(box(600100,5799720,600300,5799920).exterior.coords,
                      [box(600160,5799780,600240,5799860).exterior.coords])
    result = service.acquire('org',provider.request(area=geographic(polygon)),client=provider.client())
    assert result['result']['bands']['red']['area_cell_count'] == 336
    assert result['result']['bands']['scl']['area_cell_count'] == 84
    tiny = provider.request('tiny',geographic(box(600101,5799721,600102,5799722)))
    assert service.acquire('org',tiny,client=provider.client())['error_code'] == 'no_sample_cell_centres'


def test_discovery_is_readonly_and_exposes_incomplete_page(provider):
    provider.fault = 'next_page'
    result = satellite.discover(provider.area,provider.request()['temporal'],client=provider.client())
    assert not result['selection_complete'] and len(result['candidates']) == 1
    assert result['candidates'][0]['scene_metadata_sha256'] == digest(encode(provider.item))
    assert len(provider.calls) == 1 and provider.range_calls == 0
    with core.engine.connect() as c:
        assert c.execute(select(func.count()).select_from(service.requests)).scalar_one() == 0


def test_corruption_and_cross_org_reads_fail(provider):
    result = service.acquire('org',provider.request(),client=provider.client())
    with pytest.raises(AcquisitionError,match='not_found'): service.read_acquisition('other',result['acquisition_id'])
    sha = result['artifact_checksums']['red_window']['sha256']
    key = service._object_key('org',sha).removesuffix('.json')+'.bin'
    (core.ROOT/'objects'/key).write_bytes(b'corrupt')
    with pytest.raises(AcquisitionError,match='integrity_failure'): service.read_acquisition('org',result['acquisition_id'])


def test_range_budgets_and_no_sidecar_access(provider):
    reader = BoundedClient(provider.client(),max_total=1)
    source = RangeSource(reader,provider.item['assets']['red'],'red',{},satellite.LIMITS)
    with pytest.raises(FileNotFoundError): source.open('red.tif.aux.xml')
    assert not provider.calls
    with pytest.raises(AcquisitionError,match='byte_limit'): source.get(0,100)
    source = RangeSource(BoundedClient(provider.client()),provider.item['assets']['red'],'red',{},dict(satellite.LIMITS,max_response_bytes=10))
    with pytest.raises(AcquisitionError,match='satellite_range_limit'): source.get(0,100)


@pytest.mark.parametrize('live',[False,True])
def test_verifier_replays_all_original_ranges_and_fresh_live_samples(provider,live):
    from scripts.verify_satellite_acquisition import verify_satellite
    summary = service.acquire('org',provider.request(),client=provider.client())
    before = len(provider.calls)
    result = verify_satellite('org',summary,live=live,client=provider.client())
    assert result['offline_source_range_replay_match']
    assert len(result['samples']) == (15 if live else 0)
    if not live: assert len(provider.calls) == before


def test_verifier_detects_different_live_pixels_even_with_unchanged_metadata_and_etag(provider):
    from scripts.verify_satellite_acquisition import verify_satellite
    summary = service.acquire('org',provider.request(),client=provider.client())
    changed = Provider(fill=lambda key,data:data.fill(0))
    for key,content in changed.content.items():
        original_size = len(provider.content[key])
        assert len(content) <= original_size
        provider.content[key] = content+b'\0'*(original_size-len(content))
    with pytest.raises(AcquisitionError,match='independent_satellite_sample_mismatch'):
        verify_satellite('org',summary,client=provider.client())


def test_window_limits_fail_before_pixel_allocation(provider,monkeypatch):
    monkeypatch.setitem(satellite.LIMITS,'max_window_cells_per_band',10)
    result = service.acquire('org',provider.request(),client=provider.client())
    assert result['error_code'] == 'satellite_window_limit'
    assert 'blue_window' not in result['artifact_checksums']


def test_scene_pin_is_part_of_idempotent_request_identity(provider):
    value = provider.request()
    service.acquire('org',value,client=provider.client())
    value['scene_metadata_sha256'] = '0'*64
    with pytest.raises(AcquisitionError,match='idempotency_conflict'):
        service.acquire('org',value,client=provider.client())


def test_operator_cli_uses_new_contract_without_changing_legacy_defaults(provider,tmp_path,monkeypatch,capsys):
    path = tmp_path/'request.json'; path.write_bytes(encode(provider.request()))
    original = satellite.fetch_satellite
    monkeypatch.setattr(satellite,'fetch_satellite',lambda request,**kwargs:original(request,**{**kwargs,'client':provider.client()}))
    assert service.main(['acquire','--org','org','--request',str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['result']['scene_id'] == provider.scene
    assert service.main(['sources','--adapter-version',satellite.ADAPTER]) == 0
    assert json.loads(capsys.readouterr().out)['source_id'] == satellite.SOURCE


def test_missing_band_is_explicit_failure_before_asset_reads(provider):
    del provider.item['assets']['nir']
    result = service.acquire('org',provider.request(),client=provider.client())
    assert result['error_code'] == 'satellite_scene_schema_changed' and provider.range_calls == 0


def test_raster_grid_is_checked_against_catalogue(provider):
    provider.item['properties']['proj:epsg'] = 32631
    result = service.acquire('org',provider.request(),client=provider.client())
    assert result['error_code'] == 'satellite_raster_grid_mismatch'


def test_range_request_count_and_deadline_are_hard_limits(provider):
    reader = BoundedClient(provider.client())
    source = RangeSource(reader,provider.item['assets']['red'],'red',{},dict(satellite.LIMITS,max_range_requests=1))
    assert len(source.get(0,20)) == 20
    with pytest.raises(AcquisitionError,match='satellite_range_limit'): source.get(20,40)
    reader.deadline = 0
    source = RangeSource(reader,provider.item['assets']['red'],'red',{},satellite.LIMITS)
    with pytest.raises(AcquisitionError,match='network_deadline'): source.get(40,60)


def test_empty_discovery_is_not_fabricated_imagery(provider):
    client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={
        'type':'FeatureCollection','features':[],'links':[]})))
    result=satellite.discover(provider.area,provider.request()['temporal'],client=client)
    assert result['candidates'] == [] and result['selection_complete']
    assert 'does not establish no observations' in result['selection_semantics']
