"""Replay retained COG ranges offline, then compare fresh live native pixel samples."""
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.windows import Window
from pyproj import Transformer
from shapely.geometry import shape
from shapely import intersects_xy

from backend import core, acquisition as service, acquisition_satellite as satellite
from backend.acquisition_contracts import AcquisitionError, encode
from backend.acquisition_sources import BoundedClient
from backend.satellite_ranges import ReplaySource, RangeSource


def verify_satellite(org, summary, *, live=True, client=None):
    if summary['state'] != 'succeeded' or summary['request']['adapter_version'] != satellite.ADAPTER:
        raise AcquisitionError('successful_satellite_capture_required')
    manifest = service._load(org,{'key':service._object_key(org,summary['manifest_sha256']),
                                 'sha256':summary['manifest_sha256']})
    artifacts = {key:service._load(org,ref) for key,ref in manifest['artifacts'].items()}
    item = artifacts['provider_item_before']
    area = summary['request']['area']
    epsg = item['properties']['proj:epsg']
    samples = []
    reader = BoundedClient(client,max_response=satellite.LIMITS['max_response_bytes'],
                           max_total=satellite.LIMITS['max_total_bytes'],
                           seconds=satellite.LIMITS['network_deadline_seconds'],request_timeout=40) if live else None
    endpoint = satellite.ENDPOINT+'/collections/'+satellite.COLLECTION+'/items/'+item['id']
    try:
        if live and encode(reader.get(endpoint,{})) != encode(item):
            raise AcquisitionError('provider_changed_since_capture')
        for key in satellite.BANDS:
            source = ReplaySource(artifacts['source_ranges'][key],artifacts,key)
            with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
                with rasterio.open(key+'.tif',opener=source.open,driver='GTiff') as ds:
                    content,coverage = satellite.read_window(ds,area,item['assets'][key],key,epsg)
            if source.error:
                raise source.error
            if coverage != summary['result']['bands'][key]:
                raise AcquisitionError('satellite_coverage_replay_mismatch')
            with MemoryFile(content) as replay, replay.open() as fresh, MemoryFile(artifacts[key+'_window']) as memory, memory.open() as saved:
                values = saved.read(1)
                if (fresh.profile != saved.profile or not np.array_equal(fresh.read(1),values)):
                    raise AcquisitionError('satellite_pixel_replay_mismatch')
                if not live:
                    continue
                # Independently locate cells using retained georeferencing and WGS84
                # point-in-polygon, not the acquisition's rasterized coverage mask.
                to_geo = Transformer.from_crs(epsg,4326,always_xy=True)
                polygon = shape(area)
                rows,cols = np.indices(values.shape)
                xs = saved.transform.c+(cols+.5)*saved.transform.a
                ys = saved.transform.f+(rows+.5)*saved.transform.e
                lons,lats = to_geo.transform(xs,ys)
                positions = np.argwhere(intersects_xy(polygon,lons,lats))
                if len(positions) == 0:
                    raise AcquisitionError('no_verification_samples')
                chosen = {tuple(map(int,positions[index])) for index in (0,len(positions)//2,len(positions)-1)}
                missing = next(((r,c) for r,c in positions if values[r,c] == 0),None)
                if missing: chosen.add(tuple(map(int,missing)))
                remote = RangeSource(reader,item['assets'][key],key,{},satellite.LIMITS)
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
                    with rasterio.open(key+'.tif',opener=remote.open,driver='GTiff') as ds:
                        for r,c in sorted(chosen):
                            x,y = saved.xy(r,c)
                            rr,cc = ds.index(x,y)
                            value = int(ds.read(1,window=Window(cc,rr,1,1))[0,0])
                            if remote.error: raise remote.error
                            if value != int(values[r,c]):
                                raise AcquisitionError('independent_satellite_sample_mismatch')
                            samples.append({'asset':key,'row':r,'column':c,'source_row':rr,'source_column':cc,
                                            'native_value':value,'is_nodata':value == 0,'independent_match':True})
                if remote.error: raise remote.error
                if remote.record['etag'] != artifacts['source_ranges'][key]['etag']:
                    raise AcquisitionError('provider_changed_since_capture')
        if live and encode(reader.get(endpoint,{})) != encode(item):
            raise AcquisitionError('provider_changed_since_capture')
        return {'verification_version':'satellite_native_capture_verification_v1','verified_at':core.now(),
                'acquisition_id':summary['acquisition_id'],'manifest_sha256':summary['manifest_sha256'],
                'scene_id':item['id'],'observation_time':item['properties']['datetime'],
                'offline_source_range_replay_match':True,'live_sample_match':True if live else None,'samples':samples,
                'live_decoded_bytes_received':reader.bytes_received if live else 0,
                'method':'Offline source-range reconstruction and native window/coverage replay; fresh live per-band single-cell comparisons when requested.',
                'limits':'Not a complete second download, whole-object checksum verification, ground-truth validation or change model.'}
    finally:
        if reader: reader.close()
