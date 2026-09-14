"""Offline native-coverage replay plus independent bounded live WCS cell samples."""
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.features import geometry_mask
from shapely.geometry import mapping

from backend import core, acquisition_rasters as raster
from backend.acquisition import read_acquisition_artifact
from backend.acquisition_contracts import AcquisitionError
from backend.acquisition_sources import BoundedClient


def verify_raster(org, summary):
    acquisition_id = summary['acquisition_id']
    area = summary['request']['area']
    adapter_version = summary['request']['adapter_version']
    endpoint, coverage_id, _ = raster.definition(adapter_version)
    content = read_acquisition_artifact(org, acquisition_id, 'native_raster')
    description = read_acquisition_artifact(org, acquisition_id, 'provider_description_before')
    saved = summary['result']['raster']
    replay = raster.inspect_raster(content, area, saved['bounds_27700'], adapter_version)
    if replay != saved:
        raise AcquisitionError('raster_replay_mismatch')
    samples = []
    polygon, _ = raster.request_window(area)
    with MemoryFile(content) as memory, memory.open() as ds:
        values = ds.read(1, masked=True)
        inside = geometry_mask([mapping(polygon)], out_shape=values.shape,
                               transform=ds.transform, invert=True, all_touched=False)
        indices = np.flatnonzero(inside)
        chosen = {int(indices[0]), int(indices[len(indices)//2]), int(indices[-1])}
        missing = np.flatnonzero(inside & (np.ma.getmaskarray(values) | ~np.isfinite(values.data)))
        if len(missing): chosen.add(int(missing[0]))
        for index in sorted(chosen):
            row, col = divmod(index, ds.width)
            left, top = ds.bounds.left + col, ds.bounds.top - row
            valid = not np.ma.getmaskarray(values)[row,col] and np.isfinite(values.data[row,col])
            samples.append({'row':row, 'column':col, 'bounds_27700':[left,top-1,left+1,top],
                            'valid':bool(valid), 'elevation_m':float(values.data[row,col]) if valid else None})
    reader = BoundedClient(max_response=2_000_000, max_total=12_000_000, seconds=180, request_timeout=45)
    try:
        before = reader.get_bytes(endpoint, raster.describe_parameters(adapter_version))
        if before != description:
            raise AcquisitionError('provider_changed_since_capture')
        for sample in samples:
            left,bottom,right,top = sample['bounds_27700']
            # Separate one-cell requests; never substitute the retained full raster.
            params = [('service','WCS'),('version','2.0.1'),('request','GetCoverage'),
                      ('coverageId',coverage_id),('format','image/tiff'),
                      ('subset',f'E({left},{right})'),('subset',f'N({bottom},{top})')]
            data = reader.get_bytes(endpoint, params)
            try:
                with MemoryFile(data) as memory, memory.open() as ds:
                    if (ds.driver != 'GTiff' or ds.count != 1 or ds.shape != (1,1)
                            or ds.crs != rasterio.crs.CRS.from_epsg(27700)
                            or list(ds.bounds) != sample['bounds_27700'] or ds.nodata is None
                            or ds.transform.a != 1 or ds.transform.e != -1 or ds.transform.b or ds.transform.d
                            or ds.dtypes != ('float32',)):
                        raise AcquisitionError('independent_raster_sample_mismatch')
                    cell = ds.read(1, masked=True)
                    valid = bool(not np.ma.getmaskarray(cell)[0,0] and np.isfinite(cell.data[0,0]))
                    value = float(cell.data[0,0]) if valid else None
                    if valid != sample['valid'] or value != sample['elevation_m']:
                        raise AcquisitionError('independent_raster_sample_mismatch')
            except rasterio.errors.RasterioError as exc:
                raise AcquisitionError('independent_raster_sample_mismatch') from exc
            sample['independent_match'] = True
        after = reader.get_bytes(endpoint, raster.describe_parameters(adapter_version))
        if before != after:
            raise AcquisitionError('provider_changed_since_capture')
        return {'verification_version':'geographic_raster_live_verification_v1',
                'verified_at':core.now(), 'acquisition_id':acquisition_id,
                'request':summary['request'], 'manifest_sha256':summary['manifest_sha256'],
                'artifact_checksums':summary['artifact_checksums'], 'raster_coverage':saved,
                'offline_replay_match':True, 'independent_sample_match':True, 'samples':samples,
                'independent_responses':reader.responses,
                'limits':'Offline full-coverage replay and 3–4 live one-cell comparisons, not a second complete raster download, survey validation or atomic provider snapshot.'}
    finally:
        reader.close()
