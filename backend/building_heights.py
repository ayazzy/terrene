"""Paired EA 1 m DSM/DTM acquisition and object-level height evidence.

The output is deliberately a retained acquisition/measurement bundle rather
than a legacy EarthState observation.  It is joined to immutable OpenMap Local
building objects by ``source_object_key`` when Land Evidence v4 is projected.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from backend.earth import fingerprint
from backend.source_io import artifact, fetch_bytes, utcnow


PROCESSING_VERSION = 'crc_ea_lidar_building_height_v1'
DTM_SERVICE = (
    'https://environment.data.gov.uk/spatialdata/'
    'lidar-composite-digital-terrain-model-dtm-1m/wcs'
)
DTM_COVERAGE = (
    '13787b9a-26a4-4775-8523-806d13af58fc__'
    'Lidar_Composite_Elevation_DTM_1m'
)
DTM_CATALOG = (
    'https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/'
    'lidar-composite-digital-terrain-model-dtm-1m'
)
DSM_SERVICE = (
    'https://environment.data.gov.uk/spatialdata/'
    'lidar-composite-digital-surface-model-last-return-dsm-1m/wcs'
)
DSM_COVERAGE = (
    '9ba4d5ac-d596-445a-9056-dae3ddec0178__'
    'Lidar_Composite_Elevation_LZ_DSM_1m'
)
DSM_CATALOG = (
    'https://www.data.gov.uk/dataset/cf3f1137-c12b-44a1-a835-e80fe4a60b92/'
    'lidar-composite-digital-surface-model-dsm-1m'
)
SURVEY_METADATA = {
    'composite_product_year': 2022,
    'constituent_survey_period_start': 2000,
    'constituent_survey_period_end': 2022,
    'local_survey_date': None,
    'vertical_datum': 'Ordnance Datum Newlyn',
    'source_resolution_m': 1,
    'surface_semantics': (
        'Last-return composite digital surface model including buildings, '
        'vegetation, vehicles and terrain.'
    ),
}
INWARD_BUFFER_M = 1.0
MIN_VALID_CELLS = 9
MIN_VALID_COVERAGE = 0.8
MAX_CELLS = 25_000_000
ROBUST_Z_LIMIT = 3.5
MAD_NORMALIZATION = 1.4826
FILTER_PRECISION_FLOOR_M = 0.0001
MAX_PLAUSIBLE_SURFACE_DIFFERENCE_M = 500.0
LIMITATIONS = (
    'Historical EA composite surface-height estimate derived from 1 m DSM minus '
    'co-registered 1 m DTM. Constituent surveys span 2000–2022 and the local '
    'survey date is not identified here. Vegetation, vehicles, roof form, source '
    'age, footprint generalisation, interpolation and residual alignment can '
    'affect the result. This is not a current, legal or engineering building survey.'
)


class GridMismatch(ValueError):
    """Raised when DSM and DTM cannot support cell-wise subtraction."""


class InvalidRasterValues(ValueError):
    """Raised when a retained elevation grid contains unsafe numeric values."""


def _validate_grid(dataset: rasterio.DatasetReader, label: str) -> None:
    if dataset.crs != rasterio.crs.CRS.from_epsg(27700) or dataset.count != 1:
        raise GridMismatch(f'{label} must be a single-band EPSG:27700 grid')
    affine = dataset.transform
    if affine.b != 0 or affine.d != 0 or affine.a <= 0 or affine.e >= 0:
        raise GridMismatch(f'{label} must be a north-up rectilinear grid')
    if not (
        math.isclose(dataset.res[0], 1, rel_tol=0, abs_tol=1e-8)
        and math.isclose(dataset.res[1], 1, rel_tol=0, abs_tol=1e-8)
    ):
        raise GridMismatch(f'{label} must retain the native 1 m grid')
    if dataset.width * dataset.height > MAX_CELLS:
        raise GridMismatch(f'{label} exceeds the bounded raster processing budget')


def _read_grid(dataset: rasterio.DatasetReader, label: str) -> np.ndarray:
    values = dataset.read(1, masked=True).astype('float64').filled(np.nan)
    values[~np.isfinite(values)] = np.nan
    if np.any(np.isfinite(values) & ((values < -500) | (values > 9000))):
        raise InvalidRasterValues(f'{label} contains values outside elevation bounds')
    return values


def _gap(source_object_key: str, reason_code: str, reason: str, **details: Any) -> dict[str, Any]:
    return {
        'source_object_key': source_object_key,
        'state': 'gap',
        'reason_code': reason_code,
        'reason': reason,
        **details,
    }


def _measure_building(
    source_object_key: str,
    footprint: Any,
    dtm: np.ndarray,
    dsm: np.ndarray,
    affine: rasterio.Affine,
    raster_bounds: Any,
) -> dict[str, Any]:
    if footprint.is_empty or footprint.geom_type not in ('Polygon', 'MultiPolygon'):
        return _gap(
            source_object_key, 'invalid_building_footprint',
            'The mapped building footprint is empty or not polygonal.',
        )
    interior = footprint.buffer(-INWARD_BUFFER_M)
    if interior.is_empty:
        return _gap(
            source_object_key, 'footprint_too_small',
            'A 1 m inward buffer leaves no building interior for boundary-safe sampling.',
            candidate_cell_count=0,
        )
    west, south, east, north = interior.bounds
    tolerance = 1e-7
    if (
        raster_bounds.left > west + tolerance
        or raster_bounds.bottom > south + tolerance
        or raster_bounds.right < east - tolerance
        or raster_bounds.top < north - tolerance
    ):
        return _gap(
            source_object_key, 'insufficient_raster_extent',
            'The paired rasters do not cover the complete inward-buffered footprint.',
        )
    inside = geometry_mask(
        [mapping(interior)], out_shape=dtm.shape, transform=affine,
        invert=True, all_touched=False,
    )
    candidate_count = int(inside.sum())
    if candidate_count < MIN_VALID_CELLS:
        return _gap(
            source_object_key, 'footprint_too_small',
            f'Only {candidate_count} native cell centres remain after the 1 m inward buffer; '
            f'at least {MIN_VALID_CELLS} are required.',
            candidate_cell_count=candidate_count,
        )
    paired = inside & np.isfinite(dtm) & np.isfinite(dsm)
    differences = dsm - dtm
    physically_valid = paired & (differences >= 0) & (
        differences <= MAX_PLAUSIBLE_SURFACE_DIFFERENCE_M
    )
    valid_values = differences[physically_valid]
    valid_count = int(valid_values.size)
    coverage = valid_count / candidate_count
    if valid_count == 0:
        return _gap(
            source_object_key, 'invalid_surface_values',
            'No finite non-negative DSM minus DTM values remain inside the building interior.',
            candidate_cell_count=candidate_count, valid_cell_count=0,
            coverage_fraction=0.0,
        )
    if valid_count < MIN_VALID_CELLS or coverage < MIN_VALID_COVERAGE:
        return _gap(
            source_object_key, 'insufficient_valid_coverage',
            f'Valid paired surface cells cover {coverage:.6%} of the building interior; '
            f'at least {MIN_VALID_CELLS} cells and {MIN_VALID_COVERAGE:.0%} coverage are required.',
            candidate_cell_count=candidate_count, valid_cell_count=valid_count,
            coverage_fraction=coverage,
        )

    median = float(np.median(valid_values))
    deviations = np.abs(valid_values - median)
    mad = float(np.median(deviations))
    # Float32 DSM/DTM subtraction can introduce micrometre-scale quantisation
    # around an otherwise constant roof. The fixed 0.1 mm floor prevents that
    # encoding noise becoming a false outlier while leaving metre-scale values
    # and the MAD rule untouched.
    threshold = max(
        FILTER_PRECISION_FLOOR_M,
        ROBUST_Z_LIMIT * MAD_NORMALIZATION * mad,
    )
    retained = valid_values[deviations <= threshold]
    if retained.size < MIN_VALID_CELLS:
        return _gap(
            source_object_key, 'insufficient_filtered_samples',
            'Median/MAD filtering leaves fewer than nine deterministic interior samples.',
            candidate_cell_count=candidate_count, valid_cell_count=valid_count,
            filtered_sample_count=int(retained.size), coverage_fraction=coverage,
            median_absolute_deviation_m=mad,
        )
    p50 = float(np.percentile(retained, 50, method='linear'))
    p90 = float(np.percentile(retained, 90, method='linear'))
    if not (math.isfinite(p50) and math.isfinite(p90) and p50 >= 0 and p90 >= 0):
        return _gap(
            source_object_key, 'invalid_surface_values',
            'Filtered DSM minus DTM percentiles are invalid.',
        )
    return {
        'source_object_key': source_object_key,
        'state': 'available',
        'p50_height_m': p50,
        'p90_height_m': p90,
        'extrusion_height_m': p90,
        'candidate_cell_count': candidate_count,
        'valid_cell_count': valid_count,
        'sample_count': int(retained.size),
        'coverage_fraction': coverage,
        'median_absolute_deviation_m': mad,
    }


def process_raster_pair(
    dtm_path: str | Path,
    dsm_path: str | Path,
    buildings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return deterministic measurements or explicit gaps for every building."""
    with rasterio.open(dtm_path) as dtm_dataset, rasterio.open(dsm_path) as dsm_dataset:
        _validate_grid(dtm_dataset, 'DTM')
        _validate_grid(dsm_dataset, 'DSM')
        if (
            dtm_dataset.shape != dsm_dataset.shape
            or not dtm_dataset.transform.almost_equals(dsm_dataset.transform, precision=1e-10)
        ):
            raise GridMismatch('DSM and DTM grids are not exactly co-registered')
        dtm = _read_grid(dtm_dataset, 'DTM')
        dsm = _read_grid(dsm_dataset, 'DSM')
        return [
            _measure_building(
                item['source_object_key'], shape(item['source_geometry']), dtm, dsm,
                dtm_dataset.transform, dtm_dataset.bounds,
            )
            for item in sorted(buildings, key=lambda value: value['source_object_key'])
        ]


def _request_coverage(
    service: str,
    coverage: str,
    role_prefix: str,
    bounds: tuple[int, int, int, int],
    cache_dir: Path,
    artifacts: list[dict[str, Any]],
) -> Path:
    describe_params = {
        'service': 'WCS', 'version': '2.0.1', 'request': 'DescribeCoverage',
        'coverageId': coverage,
    }
    metadata_bytes, metadata_request = fetch_bytes(
        service, describe_params, max_bytes=2_000_000,
    )
    if coverage.encode() not in metadata_bytes or b'<gml:offsetVector' not in metadata_bytes:
        raise ValueError(f'Unexpected {role_prefix.upper()} DescribeCoverage response')
    metadata = artifact(cache_dir, metadata_bytes, '.xml')
    artifacts.append({
        **metadata, 'role': role_prefix + '_describe_coverage',
        'request': metadata_request,
    })
    west, south, east, north = bounds
    coverage_params = [
        ('service', 'WCS'), ('version', '2.0.1'), ('request', 'GetCoverage'),
        ('coverageId', coverage), ('format', 'image/tiff'),
        ('subset', f'E({west},{east})'), ('subset', f'N({south},{north})'),
    ]
    raster_bytes, raster_request = fetch_bytes(
        service, coverage_params, max_bytes=128 * 1024 * 1024,
    )
    if raster_bytes[:4] not in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+'):
        raise ValueError(f'EA did not return a GeoTIFF {role_prefix.upper()} coverage')
    raster = artifact(cache_dir, raster_bytes, '.tif')
    artifacts.append({
        **raster, 'role': role_prefix + '_raster', 'request': raster_request,
    })
    return Path(raster['path'])


def fetch_building_height_evidence(
    buildings: list[dict[str, Any]],
    cache_dir: str | Path,
) -> dict[str, Any]:
    """Acquire a co-registered pair and compute one outcome per building."""
    cache_dir = Path(cache_dir) / 'building-heights'
    started_at = utcnow()
    source_fingerprint = fingerprint([
        {
            'source_object_key': item.get('source_object_key'),
            'source_geometry_fingerprint': item.get('source_geometry_fingerprint'),
            'source_geometry': item.get('source_geometry'),
        }
        for item in sorted(buildings, key=lambda value: value.get('source_object_key', ''))
    ])
    result: dict[str, Any] = {
        'processing_version': PROCESSING_VERSION,
        'status': 'unavailable',
        'retrieved_at': started_at,
        'building_source_fingerprint': source_fingerprint,
        'requested_bounds_27700': None,
        'survey_metadata': SURVEY_METADATA,
        'artifacts': [],
        'results': [],
        'limitations': LIMITATIONS,
    }
    try:
        if not buildings:
            raise ValueError('No mapped buildings were supplied for height processing')
        footprints = [shape(item['source_geometry']) for item in buildings]
        if any(
            footprint.is_empty
            or footprint.geom_type not in ('Polygon', 'MultiPolygon')
            for footprint in footprints
        ):
            raise ValueError('Mapped building collection contains invalid geometry')
        west, south, east, north = unary_union(footprints).bounds
        bounds = (
            math.floor(west) - 2, math.floor(south) - 2,
            math.ceil(east) + 2, math.ceil(north) + 2,
        )
        if (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) > MAX_CELLS:
            raise ValueError('Building extent exceeds 25 million paired raster cells')
        result['requested_bounds_27700'] = list(bounds)
        dtm_path = _request_coverage(
            DTM_SERVICE, DTM_COVERAGE, 'dtm', bounds, cache_dir,
            result['artifacts'],
        )
        dsm_path = _request_coverage(
            DSM_SERVICE, DSM_COVERAGE, 'dsm', bounds, cache_dir,
            result['artifacts'],
        )
        try:
            result['results'] = process_raster_pair(dtm_path, dsm_path, buildings)
        except GridMismatch as error:
            result['results'] = [
                _gap(item['source_object_key'], 'grid_misaligned', str(error))
                for item in sorted(buildings, key=lambda value: value['source_object_key'])
            ]
        except InvalidRasterValues as error:
            result['results'] = [
                _gap(item['source_object_key'], 'invalid_surface_values', str(error))
                for item in sorted(buildings, key=lambda value: value['source_object_key'])
            ]
        result['status'] = 'available'
        result['retrieved_at'] = max(
            artifact_record['request']['retrieved_at']
            for artifact_record in result['artifacts']
        )
    except (
        KeyError, TypeError, ValueError, OSError, RuntimeError,
        rasterio.errors.RasterioError, httpx.HTTPError,
    ) as error:
        reason = f'EA paired DSM/DTM acquisition unavailable: {type(error).__name__}: {str(error)[:350]}'
        result['missing_reason'] = reason
        result['results'] = [
            _gap(item.get('source_object_key', 'unknown'), 'acquisition_failed', reason)
            for item in sorted(buildings, key=lambda value: value.get('source_object_key', ''))
        ]
    return result


def acquire_for_assessment(job: dict[str, Any], built_finding: dict[str, Any]) -> dict[str, Any]:
    """Retain one immutable height acquisition bundle for an assessment."""
    from backend import core

    summary = built_finding.get('built_world') or {}
    buildings = [
        item for item in summary.get('objects', [])
        if item.get('object_type') == 'building'
    ]
    expected_fingerprint = fingerprint([
        job['site_id'], job['version'], job['geometry'],
        summary.get('source_release'), buildings,
    ])
    key = f'environmental/assessments/{job["id"]}/building-heights.json'
    saved = core.load_object(key)
    if saved is not None:
        retained = json.loads(saved)
        if (
            retained.get('processing_version') != PROCESSING_VERSION
            or retained.get('assessment_input_fingerprint') != expected_fingerprint
        ):
            raise ValueError('Retained building-height evidence does not match the assessment inputs')
        return retained

    acquired = fetch_building_height_evidence(buildings, core.ROOT / 'environmental')
    retained_artifacts: list[dict[str, Any]] = []
    for record in acquired.pop('artifacts'):
        path = Path(record.pop('path'))
        content = path.read_bytes()
        checksum = sha256(content).hexdigest()
        if checksum != record['sha256']:
            raise ValueError('Building-height raw artifact checksum mismatch')
        destination = f'environmental/raw/{checksum}/{path.name}'
        core.store_object(destination, content, 'application/octet-stream')
        role = record['role']
        is_dsm = role.startswith('dsm_')
        is_raster = role.endswith('_raster')
        retained_artifacts.append({
            **record,
            'storage_reference': destination,
            'provider': 'Environment Agency',
            'dataset': (
                'LIDAR Composite Digital Surface Model (DSM) - 1m'
                if is_dsm else 'LIDAR Composite Digital Terrain Model (DTM) - 1m'
            ),
            'source_url': DSM_CATALOG if is_dsm else DTM_CATALOG,
            'media_type': 'image/tiff' if is_raster else 'application/xml',
            'asset_role': 'surface' if is_dsm and is_raster else (
                'terrain' if is_raster else 'metadata'
            ),
            'crs': 'EPSG:27700' if is_raster else None,
            'spatial_resolution_m': 1 if is_raster else None,
            'raw_semantics': (
                'Original bounded WCS response bytes for the declared request. '
                + (LIMITATIONS if is_raster else 'This is the exact DescribeCoverage response.')
            ),
        })
    acquired['artifacts'] = retained_artifacts
    acquired['assessment_input_fingerprint'] = expected_fingerprint
    payload = json.dumps(
        acquired, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode()
    core.store_object(key, payload, 'application/json')
    return acquired
