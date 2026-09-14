"""Read-only compatibility of two explicitly selected immutable LIDAR captures.

Grid compatibility and joint valid-cell availability are not a height model or
evidence that the source pixels were surveyed together.
"""
import numpy as np
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from shapely.geometry import mapping

from backend.acquisition import read_acquisition, read_acquisition_artifact
from backend.acquisition_contracts import (
    AcquisitionError, DTM_ADAPTER_VERSION, DSM_ADAPTER_VERSION, digest, encode,
)
from backend import acquisition_rasters as raster


def read_lidar_pair(org, *, dtm_acquisition_id, dsm_acquisition_id):
    sources = {'dtm': read_acquisition(org, dtm_acquisition_id),
               'dsm': read_acquisition(org, dsm_acquisition_id)}
    for role, adapter in [('dtm', DTM_ADAPTER_VERSION), ('dsm', DSM_ADAPTER_VERSION)]:
        source = sources[role]
        if source['state'] != 'succeeded':
            raise AcquisitionError('successful_capture_required')
        if source['request']['adapter_version'] != adapter:
            raise AcquisitionError('lidar_pair_source_mismatch')
    dtm, dsm = sources['dtm'], sources['dsm']
    if dtm['request']['area'] != dsm['request']['area']:
        raise AcquisitionError('lidar_pair_area_mismatch')
    if dtm['request']['coverage_profile_sha256'] != dsm['request']['coverage_profile_sha256']:
        raise AcquisitionError('lidar_pair_coverage_profile_mismatch')
    inputs, masks, grid = {}, {}, None
    polygon, bounds = raster.request_window(dtm['request']['area'])
    inside = None
    for role, source in sources.items():
        def artifact(name):
            return read_acquisition_artifact(org, source['acquisition_id'], name, attempt_id=source['attempt_id'])
        adapter = source['request']['adapter_version']
        raster.validate_description(artifact('provider_description_before'), bounds, adapter)
        content = artifact('native_raster')
        replay = raster.inspect_raster(content, source['request']['area'], bounds, adapter)
        if replay != source['result']['raster']:
            raise AcquisitionError('raster_replay_mismatch')
        current_grid = {key: replay[key] for key in ('crs', 'resolution_m', 'vertical_unit', 'vertical_datum',
                                                    'width', 'height', 'transform', 'bounds_27700', 'dtype', 'band_count')}
        if grid is not None and grid != current_grid:
            raise AcquisitionError('lidar_pair_grid_mismatch')
        grid = current_grid
        with MemoryFile(content) as memory, memory.open() as dataset:
            values = dataset.read(1, masked=True)
            masks[role] = ~np.ma.getmaskarray(values) & np.isfinite(values.data)
            if inside is None:
                inside = geometry_mask([mapping(polygon)], out_shape=values.shape,
                                       transform=dataset.transform, invert=True, all_touched=False)
        inputs[role] = {
            'acquisition_id': source['acquisition_id'], 'attempt_id': source['attempt_id'],
            'source_id': source['request']['source_id'], 'adapter_version': adapter,
            'manifest_sha256': source['manifest_sha256'],
            'native_raster_sha256': source['artifact_checksums']['native_raster']['sha256'],
            'capture_started': source['started'], 'capture_completed': source['completed'],
            'local_survey_date': None,
        }
    total = int(inside.sum())
    paired = int((inside & masks['dtm'] & masks['dsm']).sum())
    result = {
        'contract_version': 'lidar_pair_compatibility_v1', 'inputs': inputs,
        'geometry_fingerprint': digest(encode(dtm['request']['area'])),
        'coverage_profile_sha256': dtm['request']['coverage_profile_sha256'],
        'grid_compatible': True, 'grid': grid,
        'paired_coverage': {
            'area_cell_count': total, 'paired_valid_cell_count': paired,
            'missing_pair_cell_count': total-paired, 'paired_valid_cell_fraction': paired/total,
            'coverage_state': 'complete' if paired == total else ('partial' if paired else 'no_valid_pairs'),
            'dtm_only_valid_cell_count': int((inside & masks['dtm'] & ~masks['dsm']).sum()),
            'dsm_only_valid_cell_count': int((inside & masks['dsm'] & ~masks['dtm']).sum()),
        },
        'temporal_compatibility': 'unverified_local_survey_dates',
        'same_survey_confirmed': None,
        'limitations': [
            'Read-only compatibility check; no persisted pair, Evidence Snapshot, model binding or calculation of heights.',
            'Shared resolution, grid and datum do not establish matching survey dates, contemporary conditions or scientific suitability.',
            'Joint coverage is the intersection of valid cell masks inside the requested polygon; it is not confidence.',
            'Surface-minus-terrain interpretation requires a separate versioned model and explicit assumptions.',
        ],
    }
    return {**result, 'compatibility_fingerprint': digest(encode(result))}
