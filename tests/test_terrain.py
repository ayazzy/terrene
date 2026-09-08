"""Numerical raster checks plus a small unchanged crop of the real EA Port Meadow DTM."""
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer
from shapely.geometry import Polygon, box, mapping
from shapely.ops import transform

from backend import terrain
from backend.adapters import select_observations
from backend.earth import EarthState

FIXTURE = Path(__file__).parent / 'fixtures' / 'terrain' / 'port_meadow_64m.tif'
META = json.loads(FIXTURE.with_suffix('.json').read_text())
TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True).transform
DATE = '2026-09-08T14:23:24.261082+00:00'


def geographic(projected):
    return mapping(transform(TO_WGS84, projected))


def raster(tmp_path, values, **overrides):
    path = tmp_path / 'fixture.tif'
    values = np.asarray(values, dtype='float32')
    profile = dict(driver='GTiff', count=1, width=values.shape[1], height=values.shape[0],
                   dtype='float32', crs='EPSG:27700', nodata=-9999,
                   transform=from_origin(449200, 208600, 1, 1))
    profile.update(overrides)
    with rasterio.open(path, 'w', **profile) as target:
        target.write(values, 1)
    return path


def state():
    return EarthState(location_id='real-port-meadow-crop', boundary_version=1,
                      geography='England', as_of=DATE, geometry=META['geometry'])


def test_horn_slopes_are_degrees_with_correct_horizontal_units():
    # A plane with +1m per 2m east, +1m per 5m south. Independent analytic answer.
    rows, columns = np.indices((8, 8))
    result = terrain.horn_slope(50 + rows + columns, 2, 5)
    expected = math.degrees(math.atan(math.hypot(.5, .2)))
    assert np.allclose(result[1:-1, 1:-1], expected)
    assert np.isnan(result[[0, -1], :]).all()
    assert np.isnan(result[:, [0, -1]]).all()
    assert terrain.horn_slope(np.zeros((5, 5)), 1, 1)[2, 2] == 0
    with pytest.raises(ValueError, match='positive metres'):
        terrain.horn_slope(np.zeros((5, 5)), 0, 1)


def test_horn_requires_every_neighbour_and_never_fills_nodata():
    heights = np.ones((7, 7)) * 58
    heights[3, 3] = np.nan
    result = terrain.horn_slope(heights, 1, 1)
    assert np.isnan(result[2:5, 2:5]).all()
    assert np.isfinite(result[1:-1, 1:-1]).sum() == 16
    assert (result[np.isfinite(result)] == 0).all()
    assert np.isnan(terrain.horn_slope(np.ones((2, 3)), 1, 1)).all()


def test_dem_mask_respects_holes_and_native_cell_centres(tmp_path):
    heights = np.ones((10, 10)) * 50
    heights[4:6, 4:6] = 100  # A hole excludes this raised patch from elevation statistics.
    path = raster(tmp_path, heights)
    polygon = Polygon(box(449202, 208592, 449208, 208598).exterior.coords,
                      [box(449204, 208594, 449206, 208596).exterior.coords])
    result = terrain.process_dem(path, geographic(polygon))
    assert result['parcel_cells'] == 32
    assert result['statistics']['terrain.elevation_m'] == 50
    assert result['statistics']['terrain.elevation_max_m'] == 50
    assert result['elevation_coverage'] == 1
    assert result['slope_coverage'] == 1


def test_nodata_reduces_coverage_without_becoming_favourable_zero(tmp_path):
    heights = np.ones((10, 10)) * 50
    heights[5, 5] = -9999
    result = terrain.process_dem(raster(tmp_path, heights),
        geographic(box(449202, 208592, 449208, 208598)))
    assert result['statistics']['terrain.elevation_m'] == 50
    assert result['statistics']['terrain.slope_deg'] == 0
    assert result['parcel_cells'] == 36
    assert result['elevation_coverage'] == pytest.approx(35 / 36)
    assert result['slope_coverage'] == pytest.approx(27 / 36)
    heights[:] = -9999
    missing = terrain.process_dem(raster(tmp_path, heights),
        geographic(box(449202, 208592, 449208, 208598)))
    assert set(missing['statistics'].values()) == {None}
    assert missing['elevation_coverage'] == missing['slope_coverage'] == 0


@pytest.mark.parametrize('overrides, message', [
    ({'crs': 'EPSG:4326'}, 'EPSG:27700'),
    ({'transform': from_origin(449200, 208600, 2, 2)}, 'native 1m'),
    ({'transform': rasterio.Affine(1, .1, 449200, 0, -1, 208600)}, 'north-up'),
])
def test_rejects_incompatible_grid_units_and_resampling(tmp_path, overrides, message):
    path = raster(tmp_path, np.ones((10, 10)), **overrides)
    with pytest.raises(ValueError, match=message):
        terrain.process_dem(path, geographic(box(449202, 208592, 449208, 208598)))


def test_rejects_elevation_sentinel_without_nodata_definition(tmp_path):
    heights = np.ones((10, 10)) * 57
    heights[4, 4] = -32768
    path = raster(tmp_path, heights, nodata=None)
    with pytest.raises(ValueError, match='elevation bounds'):
        terrain.process_dem(path, geographic(box(449202, 208592, 449208, 208598)))


@pytest.mark.parametrize('parcel', [
    box(449195, 208592, 449208, 208598),  # Parcel extends beyond the received raster.
    box(449200.25, 208592, 449208, 208598),  # No complete west Horn-neighbour halo.
])
def test_undersized_raster_cannot_report_false_complete_coverage(tmp_path, parcel):
    path = raster(tmp_path, np.ones((10, 10)) * 57)
    with pytest.raises(ValueError, match='full parcel and one-cell slope halo'):
        terrain.process_dem(path, geographic(parcel))


def test_real_port_meadow_fixture_is_immutable_and_reproduces_statistics():
    assert sha256(FIXTURE.read_bytes()).hexdigest() == META['fixture_sha256']
    assert META['source_sha256'] == 'b386dd3e503a90bfe14c8a101c306485b8516597871e434e9669e7c5de60b43e'
    result = terrain.process_dem(FIXTURE, META['geometry'])
    assert result['statistics'] == pytest.approx(META['expected']['statistics'], abs=1e-10)
    assert result['parcel_cells'] == 3600
    assert result['elevation_coverage'] == result['slope_coverage'] == 1
    assert result['resolution_m'] == 1
    # Independent aggregation of the unchanged real crop's central 60 x 60 cells.
    with rasterio.open(FIXTURE) as dataset:
        heights = dataset.read(1).astype('float64')[2:-2, 2:-2]
    assert result['statistics']['terrain.elevation_m'] == pytest.approx(heights.mean())
    assert result['statistics']['terrain.elevation_std_m'] == pytest.approx(heights.std())
    assert META['observation_date'] is None


def test_acquisition_failure_is_explicit_unknown_without_generated_values(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError('source unavailable in this test')
    monkeypatch.setattr(terrain, 'fetch_bytes', unavailable)
    snapshot = terrain.fetch_terrain(META['geometry'], tmp_path)
    assert snapshot['status'] == 'unavailable'
    assert snapshot['artifacts'] == []
    assert set(snapshot['statistics'].values()) == {None}
    raw, candidates = terrain.terrain_observations(snapshot, state())
    assert raw and 'acquisition attempt' in raw[0].source_dataset
    assert all(o.value is None and o.confidence == 0 and o.input_coverage == 0 and
               o.epistemic_status == 'unknown' and o.missing_reason and not o.synthetic
               for _, o in candidates)
    assert not list(tmp_path.rglob('*.tif'))


def test_real_bytes_acquisition_cache_and_provenance_roundtrip(tmp_path, monkeypatch):
    calls = []
    metadata = b'<coverage><name>Elevation</name><gml:offsetVector>1 0</gml:offsetVector></coverage>'
    def responses(url, params, **kwargs):
        calls.append(params)
        content = metadata if isinstance(params, dict) else FIXTURE.read_bytes()
        return content, {'url': META['source_url'], 'retrieved_at': DATE}
    monkeypatch.setattr(terrain, 'fetch_bytes', responses)
    snapshot = terrain.fetch_terrain(META['geometry'], tmp_path)
    assert snapshot['status'] == 'available' and len(calls) == 2
    assert terrain.fetch_terrain(META['geometry'], tmp_path) == snapshot
    assert len(calls) == 2
    raw, candidates = terrain.terrain_observations(snapshot, state())
    assert all(r.checksum == sha256(Path(r.storage_reference).read_bytes()).hexdigest() for r in raw)
    parcel = state()
    parcel.raw = raw
    select_observations(parcel, candidates)
    reread = EarthState.model_validate_json(parcel.model_dump_json())
    for observation in reread.observations():
        assert set(observation.raw_source_ids) == {r.id for r in reread.raw}
        assert observation.timestamp is None
        assert observation.source_version == snapshot['dem']['sha256']
        assert observation.observed_or_derived == 'derived'
        assert terrain.TERRAIN_VERSION in observation.method
        assert terrain.STATISTIC_NAMES[observation.variable] in observation.method
        assert 'not validated predictive accuracy' in observation.uncertainty
        assert observation.spatial.spatial_resolution_m == 1
        assert not observation.synthetic
    assert reread.get('terrain.slope_deg').value == pytest.approx(.5352894663)
    assert reread.get('terrain.slope_deg').unit == 'degree'
    assert reread.get('terrain.elevation_m').unit == 'm'
    # A cache must not mask corruption or manufacture a replacement measurement.
    Path(snapshot['dem']['path']).write_bytes(b'corrupt source')
    with pytest.raises(ValueError, match='missing or changed'):
        terrain.fetch_terrain(META['geometry'], tmp_path)
    assert len(calls) == 2


def test_partial_observations_keep_fractional_coverage_and_explicit_method():
    snapshot = dict(version=terrain.TERRAIN_VERSION, retrieved_at=DATE, artifacts=[],
                    statistics=deepcopy(META['expected']['statistics']),
                    elevation_coverage=.9, slope_coverage=.7)
    # Give the real raster source, while simulating a partial parcel availability report.
    snapshot['artifacts'] = [{'path': str(FIXTURE), 'sha256': META['fixture_sha256']}]
    snapshot['dem'] = snapshot['artifacts'][0]
    _, candidates = terrain.terrain_observations(snapshot, state())
    for _, observation in candidates:
        assert observation.input_coverage == (.7 if 'slope' in observation.variable else .9)
        assert 'no gap filling' in observation.method
        assert observation.value is not None
