"""Raster acquisition isolation, native-grid validation and missing-data semantics."""
import json

import httpx
import numpy as np
import pytest
from pydantic import ValidationError
from pyproj import Transformer
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import box, mapping, Polygon, MultiPolygon
from shapely.ops import transform

from backend import core, acquisition as service, acquisition_sources as sources, acquisition_rasters as raster
from backend.acquisition_contracts import AcquisitionError, AcquisitionRequest, BinaryArtifact, digest, encode
from test_geographic_acquisition import database, profile, Provider, request

TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True).transform


def geographic(geometry):
    return mapping(transform(TO_WGS84, geometry))


@pytest.fixture
def raster_profile(database):
    data = encode({'version': sources.FULL_EXTENT_COVERAGE_VERSION, 'endpoint': sources.FULL_EXTENT_COVERAGE_URL,
                   'synthetic': True, 'feature': {'type': 'Feature',
                   'properties': {'CTRY24CD': 'E92000001'}, 'geometry': mapping(box(-2, 51, 2, 53))}})
    sha = digest(data)
    core.store_object_immutable(sources._profile_key(sha), data)
    return sha


def lidar_request(sha, key='terrain', area=None):
    return {**request(sha, key, area or geographic(box(449202, 208542, 449222, 208562))),
            'source_id': 'environment_agency.lidar_dtm_1m', 'adapter_version': 'ea_lidar_dtm_wcs_v1'}


def description():
    return f'''<wcs:CoverageDescriptions xmlns:wcs="http://www.opengis.net/wcs/2.0"
        xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:swe="http://www.opengis.net/swe/2.0">
      <wcs:CoverageDescription><wcs:CoverageId>{raster.COVERAGE}</wcs:CoverageId>
      <gml:boundedBy><gml:Envelope srsName="http://www.opengis.net/def/crs/EPSG/0/27700" axisLabels="E N">
      <gml:lowerCorner>80000 4000</gml:lowerCorner><gml:upperCorner>656000 665000</gml:upperCorner>
      </gml:Envelope></gml:boundedBy><gml:offsetVector>1 0</gml:offsetVector>
      <gml:offsetVector>0 -1</gml:offsetVector><swe:field name="Elevation"><swe:Quantity>
      <swe:uom code="W.m-2.Sr-1"/></swe:Quantity></swe:field>
      </wcs:CoverageDescription></wcs:CoverageDescriptions>'''.encode()


class RasterProvider:
    def __init__(self, area, fault=None, values=None):
        self.calls = []
        self.fault = fault
        self.descriptions = 0
        _, self.bounds = raster.request_window(area)
        left, bottom, right, top = self.bounds
        width, height = right-left, top-bottom
        data = np.full((height, width), 50, dtype='float32')
        if values:
            values(data)
        if fault == 'invalid_values':
            data[0, 0] = -32768
        profile = dict(driver='GTiff', count=1, dtype='float32', width=width, height=height,
                       nodata=-9999, crs='EPSG:27700', transform=from_origin(left, top, 1, 1))
        if fault == 'crs': profile['crs'] = 'EPSG:4326'
        if fault == 'resampled': profile['transform'] = from_origin(left, top, 2, 2)
        if fault == 'off_target': profile['transform'] = from_origin(left+1, top, 1, 1)
        if fault == 'nodata': profile['nodata'] = None
        if fault == 'truncated_extent':
            profile['width'] -= 1
            data = data[:, :-1]
        with MemoryFile() as f:
            with f.open(**profile) as ds: ds.write(data, 1)
            self.content = f.read()

    def handle(self, req):
        assert str(req.url).startswith(raster.SERVICE)
        self.calls.append(req)
        if self.fault == 'network':
            raise httpx.ConnectError('PRIVATE failure details', request=req)
        if req.url.params['request'] == 'DescribeCoverage':
            self.descriptions += 1
            content = description()
            if self.fault == 'identity': content = content.replace(raster.COVERAGE.encode(), b'wrong')
            if self.fault == 'metadata_grid': content = content.replace(b'>1 0<', b'>2 0<')
            if self.fault == 'metadata_units': content = content.replace(b'W.m-2.Sr-1', b'cm')
            if self.fault == 'changed' and self.descriptions > 1: content += b'<!--updated-->'
            if self.fault == 'metadata_limit': content += b' ' * 100
            return httpx.Response(200, content=content)
        assert req.url.params['request'] == 'GetCoverage'
        assert req.url.params.get_list('subset') == [v for k,v in raster.raster_parameters(self.bounds) if k == 'subset']
        assert not any('scale' in key.lower() for key in req.url.params)
        return httpx.Response(200, content=b'<ExceptionReport/>' if self.fault == 'exception' else self.content)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self.handle))


def test_native_bytes_roundtrip_idempotency_and_no_legacy_writes(raster_profile):
    from sqlalchemy import select, func
    tables = (core.sites, core.assessments, core.datasets, core.features, core.land_evidence_snapshots, core.module_runs)
    with core.engine.connect() as c:
        before = {t.name:c.execute(select(func.count()).select_from(t)).scalar_one() for t in tables}
    value = lidar_request(raster_profile)
    provider = RasterProvider(value['area'])
    result = service.acquire('org', value, client=provider.client())
    assert result['state'] == 'succeeded' and len(provider.calls) == 3
    coverage = result['result']['raster']
    assert coverage['area_cell_count'] == coverage['valid_cell_count'] == 400
    assert coverage['coverage_state'] == 'complete' and coverage['missing_cell_count'] == 0
    assert result['result']['observation_time'] is None and result['result']['publisher_release_id'] is None
    assert service.read_acquisition_artifact('org', result['acquisition_id'], 'native_raster') == provider.content
    assert service.read_acquisition_artifact('org', result['acquisition_id'], 'provider_description_before') == description()
    assert service.read_acquisition_artifact('org', result['acquisition_id'], 'raster_coverage') == coverage
    assert result['artifact_checksums']['native_raster']['sha256'] == digest(provider.content)
    assert service.acquire('org', value, client=provider.client()) == result and len(provider.calls) == 3
    assert service.read_acquisition('org', result['acquisition_id']) == result
    assert 'key' not in result['artifact_checksums']['native_raster']
    with core.engine.connect() as c:
        assert {t.name:c.execute(select(func.count()).select_from(t)).scalar_one() for t in tables} == before


@pytest.mark.parametrize('mode,expected,valid', [('partial','partial',399), ('empty','no_valid_cells',0), ('zero','complete',400)])
def test_missing_cells_never_become_zero_terrain(raster_profile,mode,expected,valid):
    value = lidar_request(raster_profile)
    def values(data):
        if mode == 'partial': data[data.shape[0]//2, data.shape[1]//2] = -9999
        if mode == 'empty': data[:] = -9999
        if mode == 'zero': data[:] = 0
    result = service.acquire('org', value, client=RasterProvider(value['area'],values=values).client())
    assert result['state'] == 'succeeded'
    assert result['result']['raster']['coverage_state'] == expected
    assert result['result']['raster']['valid_cell_count'] == valid
    assert result['result']['raster']['missing_cell_count'] == 400-valid
    assert 'statistics' not in result['result']


@pytest.mark.parametrize('polygon,total', [
    (Polygon(box(449202,208542,449222,208562).exterior.coords,
             [box(449208,208548,449214,208554).exterior.coords]),364),
    (MultiPolygon([box(449202,208542,449212,208552),box(449222,208542,449232,208552)]),200),
])
def test_polygon_holes_and_multipart_area_control_cell_denominator(raster_profile,polygon,total):
    value = lidar_request(raster_profile,area=geographic(polygon))
    result = service.acquire('org', value, client=RasterProvider(value['area']).client())
    assert result['result']['raster']['area_cell_count'] == total


@pytest.mark.parametrize('fault,code', [
    ('crs','raster_grid_mismatch'), ('resampled','raster_grid_mismatch'), ('off_target','raster_extent_mismatch'),
    ('truncated_extent','raster_extent_mismatch'), ('nodata','raster_nodata_undefined'),
    ('invalid_values','invalid_elevation_values'), ('exception','invalid_raster_response'),
    ('identity','raster_source_schema_changed'), ('metadata_grid','raster_source_schema_changed'),
    ('metadata_units','raster_source_schema_changed'),
    ('changed','source_changed_during_capture'), ('network','network_failure'),
])
def test_raster_failure_is_explicit_and_retry_retains_history(raster_profile,fault,code):
    value = lidar_request(raster_profile)
    failed = service.acquire('org', value, client=RasterProvider(value['area'],fault).client())
    assert failed['error_code'] == code and failed['result'] is None
    assert 'PRIVATE' not in json.dumps(failed)
    success = service.acquire('org', value, client=RasterProvider(value['area']).client())
    assert success['state'] == 'succeeded' and len(success['attempts']) == 2
    old = service.read_acquisition('org',failed['acquisition_id'],attempt_id=failed['attempt_id'])
    assert old['manifest_sha256'] == failed['manifest_sha256'] and old['error_code'] == code


def test_raster_artifact_integrity_and_organization_isolation(raster_profile):
    value = lidar_request(raster_profile)
    result = service.acquire('org',value,client=RasterProvider(value['area']).client())
    with pytest.raises(AcquisitionError,match='not_found'):
        service.read_acquisition_artifact('other',result['acquisition_id'],'native_raster')
    with pytest.raises(AcquisitionError,match='artifact_not_found'):
        service.read_acquisition_artifact('org',result['acquisition_id'],'../../elsewhere')
    sha = result['artifact_checksums']['native_raster']['sha256']
    key = service._object_key('org',sha).removesuffix('.json')+'.bin'
    (core.ROOT/'objects'/key).write_bytes(b'corrupt')
    with pytest.raises(AcquisitionError,match='integrity_failure'):
        service.read_acquisition('org',result['acquisition_id'])


def test_source_pair_and_historical_profile_cannot_be_reused(profile,raster_profile):
    value = lidar_request(raster_profile)
    with pytest.raises(ValidationError,match='source_adapter_mismatch'):
        AcquisitionRequest.model_validate({**value,'source_id':'natural_england.sssi'})
    provider = RasterProvider(value['area'])
    result = service.acquire('org',{**value,'coverage_profile_sha256':profile},client=provider.client())
    assert result['error_code'] == 'coverage_version_mismatch' and not provider.calls


@pytest.mark.parametrize('mode', ['time','outside','window','subpixel'])
def test_capability_and_window_limits_are_explicit(raster_profile,mode):
    value = lidar_request(raster_profile)
    provider = RasterProvider(value['area'])
    if mode == 'time': value['temporal'] = {'mode':'interval','start':'2020-01-01','end':'2020-02-01'}
    if mode == 'outside': value['area'] = mapping(box(-1.3,60.1,-1.29,60.11))
    if mode == 'window': value['area'] = geographic(box(449000,208000,452000,211000))
    if mode == 'subpixel':
        value['area'] = geographic(box(449202.1,208542.1,449202.2,208542.2))
        provider = RasterProvider(value['area'])
    result = service.acquire('org',value,client=provider.client())
    expected = {'time':'unsupported_time','outside':'unsupported_geography','window':'raster_window_limit','subpixel':'no_sample_cell_centres'}
    assert result['error_code'] == expected[mode]
    if mode != 'subpixel': assert not provider.calls


def test_metadata_and_total_download_budget_are_enforced(raster_profile,monkeypatch):
    value = lidar_request(raster_profile)
    monkeypatch.setitem(raster.LIMITS,'max_metadata_bytes',10)
    result = service.acquire('org',value,client=RasterProvider(value['area']).client())
    assert result['error_code'] == 'byte_limit'
    monkeypatch.setitem(raster.LIMITS,'max_metadata_bytes',2_000_000)
    monkeypatch.setitem(raster.LIMITS,'max_total_bytes',len(description())+100)
    result = service.acquire('org',value,client=RasterProvider(value['area']).client())
    assert result['error_code'] == 'byte_limit' and result['result'] is None


def test_rejects_xml_entity_declarations_and_outside_extent():
    with pytest.raises(AcquisitionError,match='raster_source_schema_changed'):
        raster.validate_description(b'<!DOCTYPE x [<!ENTITY x "x">]>'+description(),[449200,208500,449220,208520])
    with pytest.raises(AcquisitionError,match='outside_raster_extent'):
        raster.validate_description(description(),[1,1,10,10])


def test_legacy_vector_history_unchanged_by_binary_capture(profile,raster_profile):
    old = service.acquire('org',request(profile),client=Provider().client())
    old_bytes = core.load_object(service._object_key('org',old['manifest_sha256']))
    value = lidar_request(raster_profile)
    result = service.acquire('org',value,client=RasterProvider(value['area']).client())
    assert result['state'] == 'succeeded'
    assert service.read_acquisition('org',old['acquisition_id']) == old
    assert core.load_object(service._object_key('org',old['manifest_sha256'])) == old_bytes


def test_binary_kind_and_length_cannot_bypass_integrity(database):
    ref = service._store('org',BinaryArtifact(b'original','application/xml'))
    for patch in ({'media_type':'text/html'},{'bytes':1},{'key':'other.bin'}):
        with pytest.raises(AcquisitionError,match='integrity_failure'):
            service._load('org',{**ref,**patch})


@pytest.mark.parametrize('mismatch', [False, True])
def test_live_verifier_uses_separate_cell_queries_and_detects_mismatch(raster_profile,monkeypatch,mismatch):
    from scripts import verify_lidar_acquisition as verifier
    from scripts.verify_geographic_acquisition import verify
    value = lidar_request(raster_profile)
    def partial(data): data[data.shape[0]//2,data.shape[1]//2] = -9999
    provider = RasterProvider(value['area'],values=partial)
    result = service.acquire('org',value,client=provider.client())
    calls = []
    def independent(req):
        calls.append(req)
        if req.url.params['request'] == 'DescribeCoverage': return httpx.Response(200,content=description())
        subsets = req.url.params.get_list('subset')
        left,right = map(float,subsets[0][2:-1].split(','))
        bottom,top = map(float,subsets[1][2:-1].split(','))
        assert right-left == top-bottom == 1
        with MemoryFile(provider.content) as memory, memory.open() as ds:
            row,col = ds.index(left+.5,top-.5)
            data = ds.read(1)[row:row+1,col:col+1].copy()
        if mismatch and data[0,0] != -9999: data += 1
        with MemoryFile() as f:
            with f.open(driver='GTiff',width=1,height=1,count=1,dtype='float32',crs='EPSG:27700',
                        nodata=-9999,transform=from_origin(left,top,1,1)) as ds:
                ds.write(data,1)
            return httpx.Response(200,content=f.read())
    client = httpx.Client(transport=httpx.MockTransport(independent))
    monkeypatch.setattr(verifier,'BoundedClient',lambda **kw:sources.BoundedClient(client,**kw))
    if mismatch:
        with pytest.raises(AcquisitionError,match='independent_raster_sample_mismatch'):
            verify('org',result['acquisition_id'])
    else:
        checked = verify('org',result['acquisition_id'])
        assert checked['offline_replay_match'] and checked['independent_sample_match']
        assert len(calls) == 6 and len(checked['samples']) == 4
        assert any(not sample['valid'] and sample['elevation_m'] is None for sample in checked['samples'])
