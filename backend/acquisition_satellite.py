"""Explicit dated Sentinel-2 C1 captures; native samples, not interpreted change."""
from datetime import datetime, timezone
import math
import re
from typing import Literal

from pydantic import Field, model_validator
from pyproj import Transformer
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.windows import Window
from shapely.geometry import shape, mapping, box
from shapely.ops import transform

from backend.acquisition_contracts import (
    Contract, TemporalSelection, AcquisitionError, BinaryArtifact, validate_area,
    digest, encode, MAX_REQUEST_BYTES,
)

SOURCE = 'copernicus.sentinel2_c1_l2a_earthsearch'
ADAPTER = 'sentinel2_c1_native_window_v1'
PROCESSING = 'sentinel2_native_dn_and_scl_v1'
ENDPOINT = 'https://earth-search.aws.element84.com/v1'
COLLECTION = 'sentinel-2-c1-l2a'
ASSET_ROOT = 'https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/'
BANDS = {'blue': ('B02', 10), 'green': ('B03', 10), 'red': ('B04', 10), 'nir': ('B08', 10), 'scl': ('SCL', 20)}
LIMITS = {'max_window_cells_per_band': 1_000_000, 'max_dimension': 2048,
          'max_response_bytes': 8_000_000, 'max_total_bytes': 64_000_000,
          'max_range_requests': 256, 'network_deadline_seconds': 240,
          'request_timeout_seconds': 40, 'max_discovery_items': 100}
SCL_CLASSES = ['no_data', 'saturated_or_defective', 'topographic_cast_shadows', 'cloud_shadows',
               'vegetation', 'not_vegetated', 'water', 'unclassified', 'cloud_medium_probability',
               'cloud_high_probability', 'thin_cirrus', 'snow_or_ice']


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z', value):
        raise ValueError('utc_timestamp_required')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def interval(temporal):
    if temporal.mode != 'interval':
        raise ValueError('satellite_requires_interval')
    start, end = timestamp(temporal.start), timestamp(temporal.end)
    if start >= end or (end-start).total_seconds() > 366*86400:
        raise ValueError('invalid_satellite_interval')
    return start, end


class SatelliteRequest(Contract):
    contract_version: Literal['geographic_satellite_request_v1']
    source_id: Literal['copernicus.sentinel2_c1_l2a_earthsearch']
    adapter_version: Literal['sentinel2_c1_native_window_v1']
    area: dict
    temporal: TemporalSelection
    scene_id: str = Field(pattern=r'^S2[ABC]_T\d{2}[A-Z]{3}_\d{8}T\d{6}_L2A$')
    scene_metadata_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.:-]+$')

    @model_validator(mode='after')
    def validate_request(self):
        interval(self.temporal)
        if len(encode(self.model_dump())) > MAX_REQUEST_BYTES:
            raise ValueError('request_payload_limit')
        object.__setattr__(self, 'area', validate_area(self.area))
        return self

    @property
    def geometry_fingerprint(self):
        return digest(encode(self.area))


def descriptor():
    return {'source_id': SOURCE, 'adapter_version': ADAPTER, 'data_family': 'satellite',
            'normalization_version': PROCESSING, 'publisher': 'Copernicus / ESA',
            'distributor': 'Element 84 Earth Search COG mirror', 'collection': COLLECTION,
            'endpoint': ENDPOINT, 'access': 'public; no credentials', 'temporal_modes': ['interval'],
            'coverage_method': 'Explicit scene footprint must cover the entire request; native UTM window must fit every band.',
            'jurisdiction': 'Global catalogue, including all four UK nations; availability verified per scene.',
            'bands': BANDS, 'limits': LIMITS,
            'licence': 'Copernicus Sentinel data legal notice; free, full and open access.',
            'terms_url': 'https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice',
            'documentation': 'https://github.com/Element84/earth-search',
            'limitations': ['Catalogue discovery is bounded and may be incomplete; no automatic best-scene selection.',
                'Scene-level cloud cover is not local clear-ground coverage. SCL is a provider classification, not ground truth.',
                'Raw DN and nodata are retained; reflectance requires the retained per-asset scale and offset after masking nodata.',
                'Window GeoTIFFs are lossless derived subsets; original fetched byte ranges are separately retained for replay.',
                'Whole-object publisher checksums are recorded but not verified by partial range reads.',
                'No mosaic, index, change detection, forecast, map layer or model binding is created.']}


def validate_scene(item, area, temporal, *, scene_id=None):
    """Fail closed on unknown identity, calibration, grid or remote URL schemas."""
    try:
        p = item['properties']
        observed = timestamp(p['datetime']); start, end = interval(temporal)
        footprint = shape(item['geometry'])
        epsg = p['proj:epsg']
        if (item['type'] != 'Feature' or item['collection'] != COLLECTION
                or not re.fullmatch(r'S2[ABC]_T\d{2}[A-Z]{3}_\d{8}T\d{6}_L2A', item['id'])
                or (scene_id is not None and item['id'] != scene_id)
                or p['constellation'] != 'sentinel-2' or p['platform'] not in ('sentinel-2a','sentinel-2b','sentinel-2c')
                or p['s2:product_type'] != 'S2MSI2A' or float(p['s2:processing_baseline']) < 5
                or type(epsg) is not int or not (32601 <= epsg <= 32660 or 32701 <= epsg <= 32760)
                or not isinstance(p['s2:product_uri'], str) or not p['s2:product_uri'].endswith('.SAFE')
                or not math.isfinite(p['eo:cloud_cover']) or not 0 <= p['eo:cloud_cover'] <= 100):
            raise AcquisitionError('satellite_scene_schema_changed')
        if not start <= observed <= end:
            raise AcquisitionError('scene_outside_interval')
        if footprint.is_empty or not footprint.is_valid or footprint.geom_type not in ('Polygon','MultiPolygon'):
            raise AcquisitionError('satellite_scene_schema_changed')
        if not footprint.covers(shape(area)):
            raise AcquisitionError('scene_does_not_cover_area')
        grids = []
        for key, (name, resolution) in BANDS.items():
            asset = item['assets'][key]; band, = asset['raster:bands']
            href = asset['href']
            # No redirects, query tokens, arbitrary hosts, sidecars or operator-supplied URLs.
            if not re.fullmatch(re.escape(ASSET_ROOT+COLLECTION+'/') + r'\d{1,2}/[A-Z]/[A-Z]{2}/\d{4}/\d{1,2}/' + re.escape(item['id']+'/'+name+'.tif'), href):
                raise AcquisitionError('unsafe_satellite_asset_url')
            grid = asset['proj:transform']; height, width = asset['proj:shape']
            if (asset['type'] != 'image/tiff; application=geotiff; profile=cloud-optimized'
                    or band['data_type'] != ('uint8' if key == 'scl' else 'uint16')
                    or band['nodata'] != 0 or band['spatial_resolution'] != resolution
                    or asset['gsd'] != resolution or grid != [resolution,0,grid[2],0,-resolution,grid[5]]
                    or any(type(v) not in (float,int) or not math.isfinite(v) for v in grid)
                    or type(width) is not int or type(height) is not int or width != 109800//resolution or height != width
                    or type(asset['file:size']) is not int or not 0 < asset['file:size'] <= 600_000_000
                    or not re.fullmatch(r'1220[0-9a-f]{64}', asset['file:checksum'])):
                raise AcquisitionError('satellite_asset_schema_changed')
            if key != 'scl':
                if (asset['eo:bands'][0]['name'] != name or asset['eo:bands'][0]['common_name'] != key
                        or band['scale'] != 0.0001 or band['offset'] not in (-0.1, 0)):
                    raise AcquisitionError('satellite_calibration_changed')
            grids.append((grid[2],grid[5]))
        if len(set(grids)) != 1:
            raise AcquisitionError('satellite_asset_grid_mismatch')
    except AcquisitionError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise AcquisitionError('satellite_scene_schema_changed') from exc
    return item


def discover(area, temporal, *, client=None):
    """One bounded page; return explicit pinning information, never acquire silently."""
    from backend.acquisition_sources import BoundedClient
    area = validate_area(area)
    temporal = TemporalSelection.model_validate(temporal)
    interval(temporal)
    reader = BoundedClient(client, max_response=8_000_000, max_total=8_000_000)
    try:
        page = reader.get(ENDPOINT+'/search', {'collections':COLLECTION,
            'bbox':','.join(map(str,shape(area).bounds)), 'datetime':temporal.start+'/'+temporal.end,
            'limit':LIMITS['max_discovery_items']})
        if page.get('type') != 'FeatureCollection' or not isinstance(page.get('features'),list) or len(page['features']) > LIMITS['max_discovery_items']:
            raise AcquisitionError('satellite_search_schema_changed')
        candidates, rejected, seen = [], [], set()
        for item in page['features']:
            if not isinstance(item,dict) or not isinstance(item.get('id'),str) or item['id'] in seen:
                raise AcquisitionError('satellite_search_schema_changed')
            seen.add(item['id'])
            try:
                validate_scene(item,area,temporal)
            except AcquisitionError as exc:
                rejected.append({'scene_id':item['id'],'reason':exc.code})
                continue
            candidates.append({'scene_id':item['id'], 'scene_metadata_sha256':digest(encode(item)),
                'observation_time':item['properties']['datetime'],
                'scene_cloud_cover_percent':item['properties']['eo:cloud_cover']})
        return {'contract_version':'satellite_scene_discovery_v1', 'source_id':SOURCE,
                'collection':COLLECTION, 'area':area, 'temporal':temporal.model_dump(),
                'queried_at':datetime.now(timezone.utc).isoformat(),
                'selection_complete':not any(link.get('rel') == 'next' for link in page.get('links',[])),
                'selection_semantics':'One catalogue page. No candidates does not establish no observations.',
                'candidates':sorted(candidates,key=lambda c:(c['observation_time'],c['scene_id'])),
                'rejected_candidates':rejected, 'response_checksums':reader.responses}
    finally:
        reader.close()


def read_window(dataset, area, asset, key, epsg):
    resolution = BANDS[key][1]
    expected = asset['proj:transform']
    if (dataset.driver != 'GTiff' or dataset.count != 1 or dataset.crs != rasterio.crs.CRS.from_epsg(epsg)
            or list(dataset.transform)[:6] != expected or [dataset.height,dataset.width] != asset['proj:shape']
            or dataset.dtypes != (asset['raster:bands'][0]['data_type'],) or dataset.nodata != 0
            or max(max(block) for block in dataset.block_shapes) > 2048):
        raise AcquisitionError('satellite_raster_grid_mismatch')
    # Densify WGS84 edges before projection to constrain long-edge curvature error.
    geometry = shape(area)
    if geometry.length / 0.001 > 500_000:
        raise AcquisitionError('satellite_projection_limit')
    polygon = transform(Transformer.from_crs(4326,epsg,always_xy=True).transform,
                        geometry.segmentize(0.001))
    if not box(*dataset.bounds).covers(polygon):
        raise AcquisitionError('scene_does_not_cover_area')
    left,bottom,right,top = polygon.bounds
    col = math.floor((left-expected[2])/resolution); row = math.floor((expected[5]-top)/resolution)
    width = math.ceil((right-expected[2])/resolution)-col
    height = math.ceil((expected[5]-bottom)/resolution)-row
    if not 0 < width*height <= LIMITS['max_window_cells_per_band'] or max(width,height) > LIMITS['max_dimension']:
        raise AcquisitionError('satellite_window_limit')
    window = Window(col,row,width,height)
    data = dataset.read(1,window=window)
    affine = dataset.window_transform(window)
    inside = geometry_mask([mapping(polygon)],out_shape=data.shape,transform=affine,invert=True,all_touched=False)
    count = int(inside.sum())
    if not count:
        raise AcquisitionError('no_sample_cell_centres')
    valid = int((inside & (data != 0)).sum())
    summary = {'asset_key':key,'resolution_m':resolution,'crs':f'EPSG:{epsg}',
        'source_window':[col,row,width,height], 'transform':list(affine), 'dtype':str(data.dtype),
        'nodata':0, 'area_cell_count':count,'valid_cell_count':valid, 'missing_cell_count':count-valid,
        'coverage_state':'complete' if valid == count else ('partial' if valid else 'no_valid_cells'),
        'calibration':asset['raster:bands'][0], 'source_href':asset['href'],
        'source_file_checksum':asset['file:checksum'], 'source_file_checksum_verified':False,
        'sampling':'Native cell centres within request polygon, holes excluded; no resampling or nodata filling.'}
    if key == 'scl':
        if np.any(data > 11):
            raise AcquisitionError('satellite_scl_schema_changed')
        summary['class_counts'] = {name:int((inside & (data == code)).sum()) for code,name in enumerate(SCL_CLASSES)}
        summary['classification_semantics'] = 'Provider SCL at 20 m; classes are not field observations or a model suitability score.'
    with MemoryFile() as memory:
        with memory.open(driver='GTiff',width=width,height=height,count=1,dtype=data.dtype,
                         crs=dataset.crs,transform=affine,nodata=0,compress='deflate') as output:
            output.write(data,1)
        content = memory.read()
    return content, summary


def fetch_satellite(request, *, client=None, artifacts=None, diagnostics=None):
    from backend.acquisition_sources import BoundedClient
    from backend.satellite_ranges import RangeSource
    artifacts = artifacts if artifacts is not None else {}
    diagnostics = diagnostics if diagnostics is not None else {}
    reader = BoundedClient(client, max_response=LIMITS['max_response_bytes'],max_total=LIMITS['max_total_bytes'],
                           seconds=LIMITS['network_deadline_seconds'],request_timeout=LIMITS['request_timeout_seconds'])
    endpoint = ENDPOINT+'/collections/'+COLLECTION+'/items/'+request.scene_id
    try:
        item = reader.get(endpoint,{})
        artifacts['provider_item_before'] = item
        if digest(encode(item)) != request.scene_metadata_sha256:
            raise AcquisitionError('scene_metadata_changed')
        validate_scene(item,request.area,request.temporal,scene_id=request.scene_id)
        summaries, ranges = {}, {}
        artifacts['source_ranges'] = ranges
        for key in BANDS:
            asset = item['assets'][key]
            source = RangeSource(reader,asset,key,artifacts,LIMITS)
            ranges[key] = source.record
            try:
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
                    with rasterio.open(key+'.tif',opener=source.open,driver='GTiff') as dataset:
                        content, summary = read_window(dataset,request.area,asset,key,item['properties']['proj:epsg'])
                if source.error:
                    raise source.error
            except Exception as exc:
                if source.error:
                    raise source.error from exc
                if isinstance(exc,AcquisitionError):
                    raise
                raise AcquisitionError('invalid_satellite_raster') from exc
            artifacts[key+'_window'] = BinaryArtifact(content,'image/tiff')
            summaries[key] = summary
        after = reader.get(endpoint,{})
        artifacts['provider_item_after'] = after
        if encode(item) != encode(after):
            raise AcquisitionError('source_changed_during_capture')
        result = {'data_family':'satellite','processing_version':PROCESSING,'collection':COLLECTION,
                  'scene_id':item['id'],'observation_time':item['properties']['datetime'],
                  'product_uri':item['properties']['s2:product_uri'],
                  'processing_baseline':item['properties']['s2:processing_baseline'],
                  'scene_cloud_cover_percent':item['properties']['eo:cloud_cover'],
                  'completeness':'selected_scene_bounded_windows', 'bands':summaries,
                  'time_semantics':'Observation time from STAC datetime; capture, product generation and catalogue update are separate.',
                  'quality_semantics':'Successful acquisition does not imply clear ground, accurate classification or model suitability.'}
        artifacts['satellite_coverage'] = result
        return result
    finally:
        diagnostics['responses'] = reader.responses
        diagnostics['decoded_bytes_received'] = reader.bytes_received
        reader.close()


def validate_retained(request, manifest, references, load):
    """Validate satellite-specific retained roles in addition to shared hash checks."""
    try:
        artifacts = manifest['artifacts']
        item = load(artifacts['provider_item_before'])
        if digest(encode(item)) != request.scene_metadata_sha256 or item != load(artifacts['provider_item_after']):
            raise AcquisitionError('integrity_failure')
        validate_scene(item,request.area,request.temporal,scene_id=request.scene_id)
        if load(artifacts['satellite_coverage']) != manifest['result']:
            raise AcquisitionError('integrity_failure')
        ranges = load(artifacts['source_ranges'])
        if set(ranges) != set(BANDS) or set(manifest['result']['bands']) != set(BANDS):
            raise AcquisitionError('integrity_failure')
        required = {'provider_item_before','provider_item_after','satellite_coverage','source_ranges'}
        for key in BANDS:
            name = key+'_window'
            required.add(name)
            record = ranges[key]
            if (references[name].get('media_type') != 'image/tiff'
                    or record['href'] != item['assets'][key]['href']
                    or record['size'] != item['assets'][key]['file:size']
                    or not record['etag'] or not record['ranges']):
                raise AcquisitionError('integrity_failure')
            for index, entry in enumerate(record['ranges']):
                name = f'source_{key}_range_{index:04d}'
                if (entry['artifact'] != name or not 0 <= entry['start'] < entry['end_exclusive'] <= record['size']
                        or references[name]['bytes'] != entry['end_exclusive']-entry['start']
                        or references[name]['sha256'] != entry['sha256']
                        or references[name].get('media_type') != 'application/octet-stream'):
                    raise AcquisitionError('integrity_failure')
                required.add(name)
        return required
    except AcquisitionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise AcquisitionError('integrity_failure') from exc
