"""DSM identity isolation and explicit, read-only native LIDAR pairing."""
import json

import httpx
import pytest
from pydantic import ValidationError
from shapely.geometry import box, Polygon
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from sqlalchemy import select, func

from backend import acquisition as service, acquisition_rasters as raster, acquisition_sources as sources, core
from backend.acquisition_contracts import AcquisitionError, AcquisitionRequest, digest, encode
from backend.lidar_pairing import read_lidar_pair
from test_lidar_acquisition import database, raster_profile, lidar_request, RasterProvider, geographic


def dsm_request(sha, key='surface', area=None):
    return {**lidar_request(sha,key,area), 'source_id':'environment_agency.lidar_dsm_last_return_1m',
            'adapter_version':'ea_lidar_dsm_wcs_v1'}


class SurfaceProvider(RasterProvider):
    def __init__(self, area, fault=None, values=None):
        super().__init__(area, fault, values or (lambda data: data.fill(65)))
        self.source_calls = []

    def handle(self, req):
        self.source_calls.append(req)
        assert str(req.url).startswith(raster.DSM_SERVICE)
        assert req.url.params['coverageId'] == raster.DSM_COVERAGE
        translated = httpx.Request('GET',str(req.url).replace(raster.DSM_SERVICE,raster.SERVICE).replace(raster.DSM_COVERAGE,raster.COVERAGE))
        response = super().handle(translated)
        if req.url.params['request'] == 'DescribeCoverage' and self.fault != 'dtm_identity':
            return httpx.Response(200,content=response.content.replace(raster.COVERAGE.encode(),raster.DSM_COVERAGE.encode()))
        return response


def captures(sha, *, terrain_values=None, surface_values=None, surface_area=None, area=None):
    terrain = lidar_request(sha,area=area)
    surface = dsm_request(sha,area=surface_area or area)
    dtm = service.acquire('org',terrain,client=RasterProvider(terrain['area'],values=terrain_values).client())
    dsm = service.acquire('org',surface,client=SurfaceProvider(surface['area'],values=surface_values).client())
    return dtm,dsm


def pair(dtm,dsm,org='org'):
    return read_lidar_pair(org,dtm_acquisition_id=dtm['acquisition_id'],dsm_acquisition_id=dsm['acquisition_id'])


def test_surface_capture_uses_separate_source_and_processing_identity(raster_profile):
    value = dsm_request(raster_profile)
    provider = SurfaceProvider(value['area'])
    result = service.acquire('org',value,client=provider.client())
    assert result['state'] == 'succeeded' and len(provider.source_calls) == 3
    assert result['source']['source_id'] == value['source_id']
    assert result['source']['endpoint'] == raster.DSM_SERVICE
    assert result['result']['publisher_coverage_id'] == raster.DSM_COVERAGE
    assert result['result']['raster']['processing_version'] == raster.DSM_PROCESSING_VERSION
    assert 'vegetation' in result['source']['surface_semantics']
    assert result['result']['observation_time'] is None
    assert service.read_acquisition_artifact('org',result['acquisition_id'],'native_raster') == provider.content
    assert service.acquire('org',value,client=provider.client()) == result and len(provider.source_calls) == 3


@pytest.mark.parametrize('fault,code',[
    ('dtm_identity','raster_source_schema_changed'),('metadata_units','raster_source_schema_changed'),
    ('resampled','raster_grid_mismatch'),('off_target','raster_extent_mismatch'),
    ('nodata','raster_nodata_undefined'),('changed','source_changed_during_capture'),
    ('network','network_failure'),('exception','invalid_raster_response'),
])
def test_dsm_failures_never_substitute_terrain_or_empty_evidence(raster_profile,fault,code):
    value = dsm_request(raster_profile)
    failed = service.acquire('org',value,client=SurfaceProvider(value['area'],fault).client())
    assert failed['error_code'] == code and failed['result'] is None
    success = service.acquire('org',value,client=SurfaceProvider(value['area']).client())
    assert success['state'] == 'succeeded' and len(success['attempts']) == 2
    assert service.read_acquisition('org',success['acquisition_id'],attempt_id=failed['attempt_id'])['manifest_sha256'] == failed['manifest_sha256']


def test_source_roles_cannot_be_confused(raster_profile):
    with pytest.raises(ValidationError,match='source_adapter_mismatch'):
        AcquisitionRequest.model_validate({**dsm_request(raster_profile),'source_id':'environment_agency.lidar_dtm_1m'})
    with pytest.raises(AcquisitionError,match='source_adapter_mismatch'):
        raster.fetch_dtm(AcquisitionRequest.model_validate(dsm_request(raster_profile)))
    dtm,dsm = captures(raster_profile)
    for first,second in [(dsm,dtm),(dtm,dtm),(dsm,dsm)]:
        with pytest.raises(AcquisitionError,match='lidar_pair_source_mismatch'):
            pair(first,second)


def test_pair_is_read_only_reproducible_and_never_claims_same_survey(raster_profile):
    dtm,dsm = captures(raster_profile)
    tables = (service.requests,service.attempts,core.sites,core.assessments,core.datasets,
              core.features,core.land_evidence_snapshots,core.module_runs)
    with core.engine.connect() as c:
        before = {t.name:c.execute(select(func.count()).select_from(t)).scalar_one() for t in tables}
    objects = sorted(str(p) for p in (core.ROOT/'objects').rglob('*'))
    result = pair(dtm,dsm)
    assert result == pair(dtm,dsm)
    assert result['grid_compatible'] and result['paired_coverage']['paired_valid_cell_count'] == 400
    assert result['same_survey_confirmed'] is None
    assert result['temporal_compatibility'] == 'unverified_local_survey_dates'
    assert result['inputs']['dtm']['manifest_sha256'] == dtm['manifest_sha256']
    assert result['inputs']['dsm']['native_raster_sha256'] == dsm['artifact_checksums']['native_raster']['sha256']
    assert digest(encode({k:v for k,v in result.items() if k != 'compatibility_fingerprint'})) == result['compatibility_fingerprint']
    with core.engine.connect() as c:
        assert {t.name:c.execute(select(func.count()).select_from(t)).scalar_one() for t in tables} == before
    assert sorted(str(p) for p in (core.ROOT/'objects').rglob('*')) == objects


@pytest.mark.parametrize('mode', ['disjoint','partial','empty','zero'])
def test_pair_counts_intersection_of_masks_not_minimum_source_fraction(raster_profile,mode):
    def terrain(data):
        if mode == 'disjoint': data[:,data.shape[1]//2:] = -9999
        if mode == 'partial': data[data.shape[0]//2,data.shape[1]//2] = -9999
        if mode == 'empty': data[:] = -9999
        if mode == 'zero': data[:] = 0
    def surface(data):
        data[:] = 65
        if mode == 'disjoint': data[:,:data.shape[1]//2] = -9999
        if mode == 'partial': data[data.shape[0]//2,data.shape[1]//2+1] = -9999
    dtm,dsm = captures(raster_profile,terrain_values=terrain,surface_values=surface)
    coverage = pair(dtm,dsm)['paired_coverage']
    expected = {'disjoint':0,'partial':398,'empty':0,'zero':400}[mode]
    assert coverage['paired_valid_cell_count'] == expected
    assert coverage['missing_pair_cell_count'] == 400-expected
    if mode == 'disjoint':
        assert dtm['result']['raster']['valid_cell_count'] > 0 and dsm['result']['raster']['valid_cell_count'] > 0
        assert coverage['coverage_state'] == 'no_valid_pairs'
    if mode == 'partial':
        assert coverage['dtm_only_valid_cell_count'] == coverage['dsm_only_valid_cell_count'] == 1


def test_pair_rejects_area_difference_organization_and_failed_capture(raster_profile):
    dtm,dsm = captures(raster_profile,surface_area=geographic(box(449203,208542,449223,208562)))
    with pytest.raises(AcquisitionError,match='lidar_pair_area_mismatch'): pair(dtm,dsm)
    with pytest.raises(AcquisitionError,match='not_found'): pair(dtm,dsm,'other')
    failed_request = dsm_request(raster_profile,key='failed')
    failed = service.acquire('org',failed_request,client=SurfaceProvider(failed_request['area'],'network').client())
    with pytest.raises(AcquisitionError,match='successful_capture_required'): pair(dtm,failed)


def test_pair_rejects_different_coverage_profiles_even_when_geometry_matches(raster_profile):
    dtm,dsm = captures(raster_profile)
    profile,_ = sources.load_coverage(raster_profile)
    data = encode({**profile,'synthetic_revision':2});sha = digest(data)
    core.store_object_immutable(sources._profile_key(sha),data)
    value = dsm_request(sha,key='other-profile')
    other = service.acquire('org',value,client=SurfaceProvider(value['area']).client())
    with pytest.raises(AcquisitionError,match='lidar_pair_coverage_profile_mismatch'): pair(dtm,other)


def test_pair_rejects_corrupt_native_raster(raster_profile):
    dtm,dsm = captures(raster_profile)
    sha = dsm['artifact_checksums']['native_raster']['sha256']
    key = service._object_key('org',sha).removesuffix('.json')+'.bin'
    (core.ROOT/'objects'/key).write_bytes(b'changed')
    with pytest.raises(AcquisitionError,match='integrity_failure'): pair(dtm,dsm)


def test_dtm_history_and_descriptor_do_not_change_after_surface_capture(raster_profile):
    before = sources.source_descriptor('ea_lidar_dtm_wcs_v1')
    value = lidar_request(raster_profile)
    dtm = service.acquire('org',value,client=RasterProvider(value['area']).client())
    manifest = core.load_object(service._object_key('org',dtm['manifest_sha256']))
    surface = dsm_request(raster_profile)
    service.acquire('org',surface,client=SurfaceProvider(surface['area']).client())
    assert sources.source_descriptor('ea_lidar_dtm_wcs_v1') == before
    assert service.read_acquisition('org',dtm['acquisition_id']) == dtm
    assert core.load_object(service._object_key('org',dtm['manifest_sha256'])) == manifest


def test_pair_cli_uses_explicit_capture_ids(raster_profile,capsys):
    dtm,dsm = captures(raster_profile)
    assert service.main(['pair-lidar','--org','org','--dtm-id',dtm['acquisition_id'],'--dsm-id',dsm['acquisition_id']]) == 0
    assert json.loads(capsys.readouterr().out) == pair(dtm,dsm)


def test_pair_preserves_polygon_holes(raster_profile):
    polygon = Polygon(box(449202,208542,449222,208562).exterior.coords,
                      [box(449208,208548,449214,208554).exterior.coords])
    dtm,dsm = captures(raster_profile,area=geographic(polygon))
    assert pair(dtm,dsm)['paired_coverage']['paired_valid_cell_count'] == 364


@pytest.mark.parametrize('mismatch',[False,True])
def test_independent_verifier_queries_dsm_not_dtm(raster_profile,monkeypatch,mismatch):
    from scripts import verify_lidar_acquisition as verifier
    from scripts.verify_geographic_acquisition import verify
    value = dsm_request(raster_profile)
    provider = SurfaceProvider(value['area'])
    result = service.acquire('org',value,client=provider.client())
    def independent(req):
        assert str(req.url).startswith(raster.DSM_SERVICE)
        assert req.url.params['coverageId'] == raster.DSM_COVERAGE
        if req.url.params['request'] == 'DescribeCoverage': return provider.handle(req)
        subset = req.url.params.get_list('subset')
        left,right = map(float,subset[0][2:-1].split(','))
        bottom,top = map(float,subset[1][2:-1].split(','))
        assert right-left == top-bottom == 1
        with MemoryFile(provider.content) as memory, memory.open() as ds:
            row,col = ds.index(left+.5,top-.5)
            data = ds.read(1)[row:row+1,col:col+1].copy()
        if mismatch: data += 1
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
        assert all(sample['elevation_m'] == 65 for sample in checked['samples'])
