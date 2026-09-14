"""Deterministic synthetic coverage for paired EA DSM/DTM building heights."""
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box, mapping

from backend import building_heights as heights
from backend import core


def write_raster(path: Path, values, **overrides) -> Path:
    values = np.asarray(values, dtype='float32')
    profile = {
        'driver': 'GTiff', 'count': 1, 'width': values.shape[1],
        'height': values.shape[0], 'dtype': 'float32', 'crs': 'EPSG:27700',
        'nodata': -9999, 'transform': from_origin(0, 20, 1, 1),
    }
    profile.update(overrides)
    with rasterio.open(path, 'w', **profile) as target:
        target.write(values, 1)
    return path


def building(key='building:1', geometry=None):
    geometry = geometry or box(2, 2, 12, 12)
    return {
        'source_object_key': key,
        'source_geometry': mapping(geometry),
        'source_geometry_fingerprint': 'fixture',
    }


def pair(tmp_path, difference, *, dtm=None, dsm_overrides=None, geometry=None):
    rows, columns = np.indices((20, 20))
    terrain = (50 + rows * .2 + columns * .1) if dtm is None else np.asarray(dtm)
    surface = terrain + difference
    dtm_path = write_raster(tmp_path / 'dtm.tif', terrain)
    dsm_path = write_raster(
        tmp_path / 'dsm.tif', surface, **(dsm_overrides or {}),
    )
    return heights.process_raster_pair(
        dtm_path, dsm_path, [building(geometry=geometry)],
    )[0]


def test_known_height_on_sloping_terrain_retains_full_precision_percentiles(tmp_path):
    result = pair(tmp_path, 12.345678)
    assert result['state'] == 'available'
    assert result['candidate_cell_count'] == 64
    assert result['valid_cell_count'] == result['sample_count'] == 64
    assert result['coverage_fraction'] == 1
    assert result['p50_height_m'] == pytest.approx(12.345678, abs=5e-6)
    assert result['p90_height_m'] == result['extrusion_height_m']


def test_holes_are_excluded_and_zero_mad_filter_removes_isolated_outlier(tmp_path):
    difference = np.full((20, 20), 10.0)
    difference[10, 6] = 100.0
    footprint = Polygon(
        box(2, 2, 14, 14).exterior.coords,
        [box(9, 9, 12, 12).exterior.coords],
    )
    result = pair(tmp_path, difference, geometry=footprint)
    assert result['state'] == 'available'
    assert result['p50_height_m'] == result['p90_height_m'] == 10
    assert result['sample_count'] < result['valid_cell_count']


def test_nodata_and_negative_differences_never_become_default_height(tmp_path):
    difference = np.full((20, 20), 8.0)
    difference[9:13, 3:7] = np.nan
    partial = pair(tmp_path, difference)
    assert partial['state'] == 'gap'
    assert partial['reason_code'] == 'insufficient_valid_coverage'
    negative = pair(tmp_path, -2.0)
    assert negative['state'] == 'gap'
    assert negative['reason_code'] == 'invalid_surface_values'
    assert 'p90_height_m' not in negative


def test_coverage_above_eighty_percent_is_admitted(tmp_path):
    difference = np.full((20, 20), 7.0)
    # The buffered 8 x 8 footprint has 64 cells; invalidate 12 for 81.25%.
    difference[9, 3:11] = np.nan
    difference[10, 3:7] = np.nan
    result = pair(tmp_path, difference)
    assert result['state'] == 'available'
    assert result['coverage_fraction'] == pytest.approx(52 / 64)
    assert result['sample_count'] == 52


def test_exact_eighty_percent_is_admitted_and_below_threshold_is_a_gap(tmp_path):
    footprint = box(2, 2, 14, 14)  # 10 x 10 cell centres after inward buffer.
    difference = np.full((20, 20), 7.0)
    difference[7:9, 3:13] = np.nan
    exact = pair(tmp_path, difference, geometry=footprint)
    assert exact['state'] == 'available'
    assert exact['coverage_fraction'] == .8
    difference[9, 3] = np.nan
    below = pair(tmp_path, difference, geometry=footprint)
    assert below['state'] == 'gap'
    assert below['reason_code'] == 'insufficient_valid_coverage'


def test_small_inward_footprint_is_an_explicit_gap(tmp_path):
    result = pair(tmp_path, 5.0, geometry=box(2, 2, 5, 5))
    assert result['state'] == 'gap'
    assert result['reason_code'] == 'footprint_too_small'
    assert 'p90_height_m' not in result


@pytest.mark.parametrize('overrides', [
    {'crs': 'EPSG:4326'},
    {'transform': from_origin(0, 20, 2, 2)},
    {'transform': rasterio.Affine(1, .1, 0, 0, -1, 20)},
    {'transform': from_origin(1, 20, 1, 1)},
])
def test_grid_crs_resolution_rotation_and_alignment_are_strict(tmp_path, overrides):
    terrain = np.ones((20, 20), dtype='float32') * 50
    dtm_path = write_raster(tmp_path / 'dtm.tif', terrain)
    dsm_path = write_raster(tmp_path / 'dsm.tif', terrain + 10, **overrides)
    with pytest.raises(heights.GridMismatch):
        heights.process_raster_pair(dtm_path, dsm_path, [building()])


def test_bounded_acquisition_retains_exact_requests_hashes_and_metadata(tmp_path, monkeypatch):
    terrain = np.ones((20, 20), dtype='float32') * 50
    dtm_path = write_raster(tmp_path / 'fixture-dtm.tif', terrain)
    dsm_path = write_raster(tmp_path / 'fixture-dsm.tif', terrain + 11)
    rasters = {
        heights.DTM_COVERAGE: dtm_path.read_bytes(),
        heights.DSM_COVERAGE: dsm_path.read_bytes(),
    }
    calls = []

    def response(url, params, **kwargs):
        parameters = dict(params)
        coverage = parameters['coverageId']
        calls.append((url, list(params.items()) if isinstance(params, dict) else list(params)))
        content = (
            (f'<CoverageDescription><wcs:CoverageId>{coverage}</wcs:CoverageId>'
             '<gml:offsetVector>1 0</gml:offsetVector></CoverageDescription>').encode()
            if parameters['request'] == 'DescribeCoverage' else rasters[coverage]
        )
        return content, {
            'url': url + '?exact=' + parameters['request'] + '&coverageId=' + coverage,
            'retrieved_at': '2026-09-14T10:00:00Z', 'etag': 'fixture',
            'last_modified': None,
        }

    monkeypatch.setattr(heights, 'fetch_bytes', response)
    result = heights.fetch_building_height_evidence([building()], tmp_path)
    assert result['status'] == 'available'
    assert len(calls) == len(result['artifacts']) == 4
    assert {item['role'] for item in result['artifacts']} == {
        'dtm_describe_coverage', 'dtm_raster',
        'dsm_describe_coverage', 'dsm_raster',
    }
    assert all(len(item['sha256']) == 64 and item['request']['url']
               for item in result['artifacts'])
    assert result['survey_metadata'] == heights.SURVEY_METADATA
    assert result['results'][0]['p90_height_m'] == 11


def test_acquisition_failure_emits_one_gap_per_building(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise __import__('httpx').ConnectError('deliberate failure')

    monkeypatch.setattr(heights, 'fetch_bytes', unavailable)
    result = heights.fetch_building_height_evidence(
        [building('building:1'), building('building:2')], tmp_path,
    )
    assert result['status'] == 'unavailable'
    assert result['artifacts'] == []
    assert len(result['results']) == 2
    assert all(item['state'] == 'gap' and item['reason_code'] == 'acquisition_failed'
               for item in result['results'])


def test_assessment_acquisition_retains_raw_artifacts_and_reuses_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'ROOT', tmp_path)
    monkeypatch.setenv('CRC_ENV', 'development')
    monkeypatch.delenv('R2_BUCKET', raising=False)
    raw = tmp_path / 'source.xml'
    raw.write_bytes(b'<exact-source/>')
    checksum = __import__('hashlib').sha256(raw.read_bytes()).hexdigest()
    acquired = {
        'processing_version': heights.PROCESSING_VERSION,
        'status': 'unavailable', 'retrieved_at': '2026-09-14T10:00:00Z',
        'building_source_fingerprint': 'fixture',
        'requested_bounds_27700': [0, 0, 20, 20],
        'survey_metadata': heights.SURVEY_METADATA,
        'artifacts': [{
            'path': str(raw), 'sha256': checksum,
            'role': 'dtm_describe_coverage',
            'request': {
                'url': 'https://environment.data.gov.uk/wcs?exact=1',
                'retrieved_at': '2026-09-14T10:00:00Z',
            },
        }],
        'results': [{
            'source_object_key': 'building:1', 'state': 'gap',
            'reason_code': 'acquisition_failed', 'reason': 'fixture failure',
        }],
        'limitations': heights.LIMITATIONS,
    }
    monkeypatch.setattr(
        heights, 'fetch_building_height_evidence',
        lambda buildings, cache_dir: acquired,
    )
    finding = {'built_world': {
        'source_release': '2026-04',
        'objects': [building()],
    }}
    job = {
        'id': 'assessment-1', 'site_id': 'site-1', 'version': 1,
        'geometry': mapping(box(0, 0, 20, 20)),
    }
    first = heights.acquire_for_assessment(job, finding)
    artifact = first['artifacts'][0]
    assert artifact['sha256'] == checksum
    assert core.load_object(artifact['storage_reference']) == b'<exact-source/>'
    monkeypatch.setattr(
        heights, 'fetch_building_height_evidence',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('must reuse')),
    )
    assert heights.acquire_for_assessment(job, finding) == first
