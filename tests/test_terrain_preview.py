"""Terrain presentation integrity, georeferencing, missingness and authorization."""
import base64
from datetime import datetime, timezone
import json
import warnings
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import httpx
import jwt
import numpy as np
from pyproj import Transformer
import pytest
from rasterio.io import MemoryFile
from rasterio.errors import NotGeoreferencedWarning
from rasterio.transform import Affine
from shapely.geometry import box, Polygon, MultiPolygon, Point
from sqlalchemy import event, update

from backend import api, core, acquisition as store, terrain_preview as preview
from backend.acquisition_contracts import AcquisitionError, digest, encode
from test_geographic_acquisition import database, profile, request, Provider
from test_lidar_acquisition import raster_profile, lidar_request, RasterProvider, geographic
from test_dsm_acquisition import dsm_request, SurfaceProvider
from test_weather_acquisition import request as weather_request, Provider as WeatherProvider


def capture(sha, *, values=None, area=None, key='terrain'):
    req = lidar_request(sha, key=key, area=area)
    provider = RasterProvider(req['area'], values=values)
    summary = store.acquire('org', req, client=provider.client())
    assert summary['state'] == 'succeeded'
    return summary, provider


def read(summary, org='org'):
    return preview.read_terrain_preview(org, summary['acquisition_id'], attempt_id=summary['attempt_id']).model_dump(mode='json')


def pixels(result):
    raw = base64.b64decode(result['image']['data'], validate=True)
    assert digest(raw) == result['image']['sha256'] and len(raw) == result['image']['bytes']
    # PNG georeferencing intentionally lives in the companion JSON contract.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', NotGeoreferencedWarning)
        with MemoryFile(raw) as f, f.open() as ds:
            assert ds.driver == 'PNG' and ds.count == 4
            assert ds.width == result['grid']['width'] and ds.height == result['grid']['height']
            return ds.read().transpose(1, 2, 0)


def path(s):
    return f'/api/acquisitions/{s["acquisition_id"]}/terrain-preview'


@pytest.fixture
def client(database):
    api.app.dependency_overrides[api.organization] = lambda: 'org'
    with TestClient(api.app, raise_server_exceptions=False) as c:
        yield c
    api.app.dependency_overrides.clear()


def test_exact_deterministic_contract_preserves_native_source(raster_profile):
    s, provider = capture(raster_profile)
    result = read(s)
    assert result == read(s)
    assert result['contract_version'] == 'terrain_preview_v1'
    assert result['capture']['acquisition_id'] == s['acquisition_id']
    assert result['capture']['attempt_id'] == s['attempt_id']
    assert result['capture']['manifest_sha256'] == s['manifest_sha256']
    assert result['capture']['native_raster_sha256'] == digest(provider.content)
    assert result['capture']['observation_time'] is None
    assert result['native']['valid_cell_count'] == 400
    assert result['native']['vertical_datum'] == 'Ordnance Datum Newlyn'
    assert result['legend']['minimum_elevation_m'] == result['legend']['maximum_elevation_m'] == 50
    assert result['requested_geometry'] == s['request']['area']
    rgba = pixels(result)
    assert np.all(rgba[rgba[:, :, 3] == 255, :3] == 128)
    payload = {k: v for k, v in result.items() if k != 'preview_fingerprint'}
    payload['image'] = {k: v for k, v in payload['image'].items() if k != 'data'}
    assert digest(encode(payload)) == result['preview_fingerprint']
    assert store.read_acquisition('org', s['acquisition_id']) == s
    assert store.read_acquisition_artifact('org', s['acquisition_id'], 'native_raster') == provider.content
    for private in ('objects/', 'idempotency_key', 'manifest_key', 'https://', '"org"'):
        assert private not in json.dumps(result)


def test_georeferencing_orientation_and_pixels_against_inverse_native_lookup(raster_profile):
    def gradient(data):
        rows, cols = np.indices(data.shape)
        data[:] = rows * 2 + cols - 30
    s, provider = capture(raster_profile, values=gradient)
    result = read(s); rgba = pixels(result)
    grid = result['grid']; aff = Affine(*grid['transform'][:6])
    inverse = Transformer.from_crs(3857, 27700, always_xy=True)
    to_wgs = Transformer.from_crs(3857, 4326, always_xy=True)
    west, south, east, north = grid['bounds']
    assert grid['coordinates_wgs84'] == [list(to_wgs.transform(x, y)) for x, y in
        [(west, north), (east, north), (east, south), (west, south)]]
    assert aff.a > 0 and aff.e < 0 and aff.b == aff.d == 0
    with MemoryFile(provider.content) as f, f.open() as ds:
        native = ds.read(1)
        checked = 0
        for row, col in np.argwhere(rgba[:, :, 3] == 255):
            x, y = inverse.transform(*(aff @ (int(col) + .5, int(row) + .5)))
            sr, sc = ds.index(x, y)
            expected = native[sr, sc]
            low, high = (result['legend'][k] for k in ('minimum_elevation_m', 'maximum_elevation_m'))
            shade = round(32 + 208 * (float(expected) - low) / (high - low))
            assert list(rgba[row, col]) == [shade, shade, shade, 255]
            checked += 1
        assert checked > 300


@pytest.mark.parametrize('mode', ['zero', 'negative', 'empty', 'partial'])
def test_missing_zero_and_negative_are_distinct(raster_profile, mode):
    def values(data):
        data[:] = {'zero': 0, 'negative': -5, 'empty': -9999, 'partial': 0}[mode]
        if mode == 'partial': data[8:18, 8:18] = -9999
    s, _ = capture(raster_profile, values=values)
    result = read(s); rgba = pixels(result)
    alpha = rgba[:, :, 3]
    assert int((alpha == 255).sum()) == result['grid']['visible_pixel_count']
    assert int((alpha == 0).sum()) == result['grid']['transparent_pixel_count']
    if mode == 'empty':
        assert result['native']['coverage_state'] == 'no_valid_cells'
        assert result['grid']['state'] == 'no_visible_samples'
        assert result['legend']['minimum_elevation_m'] is None
        assert result['legend']['maximum_elevation_m'] is None
        assert not rgba.any()
    else:
        assert (alpha == 255).any() and (alpha == 0).any()
        assert result['legend']['minimum_elevation_m'] == (-5 if mode == 'negative' else 0)
        assert np.all(rgba[alpha == 255, :3] == 128)
        if mode == 'partial': assert result['native']['missing_cell_count'] == 100


@pytest.mark.parametrize('kind', ['hole', 'multipart'])
def test_polygon_holes_and_gaps_stay_transparent(raster_profile, kind):
    outer = box(449202, 208542, 449262, 208602)
    polygon = (Polygon(outer.exterior.coords, [box(449222, 208562, 449242, 208582).exterior.coords])
        if kind == 'hole' else MultiPolygon([box(449202, 208542, 449222, 208602), box(449242, 208542, 449262, 208602)]))
    s, _ = capture(raster_profile, area=geographic(polygon))
    result = read(s); rgba = pixels(result)
    aff = Affine(*result['grid']['transform'][:6]); inverse = Transformer.from_crs(3857, 27700, always_xy=True)
    gap_count = 0
    for row, col in np.ndindex(rgba.shape[:2]):
        point = Point(inverse.transform(*(aff @ (col + .5, row + .5))))
        if not polygon.covers(point): assert rgba[row, col, 3] == 0
        if box(449224, 208564, 449240, 208580).covers(point):
            assert rgba[row, col, 3] == 0
            gap_count += 1
    assert gap_count > 100


def test_bounding_margin_does_not_set_legend_range(raster_profile):
    # Use the authoritative centre mask to put extremes only outside the request.
    req = lidar_request(raster_profile)
    from backend import acquisition_rasters as raster
    from rasterio.features import geometry_mask
    from rasterio.transform import from_origin
    from shapely.geometry import mapping
    polygon, bounds = raster.request_window(req['area'])
    def masked_values(data):
        inside = geometry_mask([mapping(polygon)], out_shape=data.shape,
            transform=from_origin(bounds[0], bounds[3], 1, 1), invert=True)
        data[:] = np.where(inside, 50, 9000)
    s, _ = capture(raster_profile, values=masked_values)
    result = read(s)
    assert result['legend']['minimum_elevation_m'] == result['legend']['maximum_elevation_m'] == 50


def test_large_window_is_bounded_and_native_counts_remain_separate(raster_profile):
    s, _ = capture(raster_profile, area=geographic(box(449000, 208000, 450500, 209000)))
    result = read(s); rgba = pixels(result)
    assert max(rgba.shape[:2]) <= 512
    assert rgba.size <= 512 * 512 * 4
    assert result['native']['valid_cell_count'] == 1_500_000
    assert result['grid']['visible_pixel_count'] < result['native']['valid_cell_count']


def test_distinct_captures_do_not_share_identity(raster_profile):
    first, _ = capture(raster_profile, key='first')
    second, _ = capture(raster_profile, key='second')
    a, b = read(first), read(second)
    assert a['image'] == b['image']
    assert a['preview_fingerprint'] != b['preview_fingerprint']


def test_reads_never_write_or_fetch_providers(client, raster_profile, monkeypatch):
    s, _ = capture(raster_profile)
    before = {str(p): digest(p.read_bytes()) for p in (core.ROOT / 'objects').rglob('*') if p.is_file()}
    def refuse(*args, **kwargs): raise AssertionError('Write or provider access')
    monkeypatch.setattr(core, 'store_object', refuse)
    monkeypatch.setattr(core, 'store_object_immutable', refuse)
    monkeypatch.setattr(httpx.Client, 'stream', refuse)
    def read_only(conn, cursor, statement, *args):
        assert statement.lstrip().upper().startswith('SELECT'), statement
    event.listen(core.engine, 'before_cursor_execute', read_only)
    try:
        r = client.get(path(s), params={'attempt_id': s['attempt_id']})
        assert r.status_code == 200, r.text
        assert r.headers['cache-control'] == 'no-store'
        assert r.json() == read(s)
    finally:
        event.remove(core.engine, 'before_cursor_execute', read_only)
    assert before == {str(p): digest(p.read_bytes()) for p in (core.ROOT / 'objects').rglob('*') if p.is_file()}


@pytest.mark.parametrize('family', ['dsm', 'vector', 'weather'])
def test_other_sources_are_explicitly_unsupported(client, raster_profile, profile, family):
    if family == 'dsm':
        req = dsm_request(raster_profile); provider = SurfaceProvider(req['area'])
    elif family == 'vector': req, provider = request(profile), Provider()
    else: req, provider = weather_request(), WeatherProvider()
    s = store.acquire('org', req, client=provider.client())
    assert s['state'] == 'succeeded'
    r = client.get(path(s), params={'attempt_id': s['attempt_id']})
    assert r.status_code == 422
    assert r.json() == {'detail': 'Terrain preview requires an EA DTM capture'}
    assert r.headers['cache-control'] == 'no-store'


def test_exact_attempt_required_and_failed_history_never_substituted(client, raster_profile):
    req = lidar_request(raster_profile)
    failed = store.acquire('org', req, client=RasterProvider(req['area'], fault='network').client())
    s = store.acquire('org', req, client=RasterProvider(req['area']).client())
    assert client.get(path(s)).status_code == 422
    for attempt in (failed['attempt_id'], str(uuid4()), 'invalid'):
        assert client.get(path(s), params={'attempt_id': attempt}).status_code == 404
    assert client.get(path(s), params={'attempt_id': s['attempt_id']}).status_code == 200
    assert client.get('/api/acquisitions/invalid/terrain-preview', params={'attempt_id': s['attempt_id']}).status_code == 404
    api.app.dependency_overrides[api.organization] = lambda: 'other'
    assert client.get(path(s), params={'attempt_id': s['attempt_id']}).status_code == 404


@pytest.mark.parametrize('fault', ['raster_bytes', 'description_bytes', 'source', 'coverage_count', 'observation_date'])
def test_corrupt_evidence_fails_closed_without_image(client, raster_profile, fault):
    s, _ = capture(raster_profile)
    key = store._object_key('org', s['manifest_sha256'])
    m = store._load('org', {'key': key, 'sha256': s['manifest_sha256']})
    if fault in ('raster_bytes', 'description_bytes'):
        role = 'native_raster' if fault == 'raster_bytes' else 'provider_description_before'
        core.store_object(m['artifacts'][role]['key'], b'private location/secret')
    else:
        if fault == 'source': m['source']['vertical_unit'] = 'cm'
        elif fault == 'observation_date': m['result']['observation_time'] = '2025-01-01'
        else:
            m['result']['raster']['valid_cell_count'] -= 1
            m['artifacts']['raster_coverage'] = store._store('org', m['result']['raster'])
        ref = store._store('org', m)
        with core.engine.begin() as c:
            c.execute(update(store.attempts).where(store.attempts.c.id == s['attempt_id']).values(
                manifest_key=ref['key'], manifest_sha256=ref['sha256']))
    r = client.get(path(s), params={'attempt_id': s['attempt_id']})
    assert r.status_code == 500
    assert r.json() == {'detail': 'Retained acquisition could not be verified'}
    assert r.headers['cache-control'] == 'no-store'


def test_signed_tenant_authentication_on_preview(database, raster_profile, monkeypatch):
    s, _ = capture(raster_profile)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv('CRC_ENV', 'production'); monkeypatch.setenv('SUPABASE_URL', 'https://auth.test')
    monkeypatch.setattr(jwt.PyJWKClient, 'get_signing_key_from_jwt', lambda self, token: SimpleNamespace(key=private.public_key()))
    claims = {'sub': 'user', 'exp': int(datetime.now(timezone.utc).timestamp()) + 300,
        'aud': 'authenticated', 'iss': 'https://auth.test/auth/v1', 'app_metadata': {'org_id': 'org'}}
    client = TestClient(api.app, raise_server_exceptions=False)  # No hosted-lifespan claim.
    params = {'attempt_id': s['attempt_id']}
    def headers(value, key=private):
        return {'Authorization': 'Bearer ' + jwt.encode(value, key, algorithm='RS256')}
    assert client.get(path(s), params=params).status_code == 401
    assert client.get(path(s), params=params, headers={'Authorization': 'Bearer invalid', 'X-Org-Id': 'org'}).status_code == 401
    assert client.get(path(s), params=params, headers=headers(claims)).status_code == 200
    assert client.get(path(s), params=params, headers=headers({**claims, 'app_metadata': {'org_id': 'other'}})).status_code == 404
    for change in ({'exp': 1}, {'aud': 'wrong'}, {'iss': 'https://wrong'}, {'app_metadata': {}}):
        assert client.get(path(s), params=params, headers=headers({**claims, **change})).status_code == 401
    forged = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert client.get(path(s), params=params, headers=headers(claims, forged)).status_code == 401
    client.close()


def test_openapi_exposes_only_typed_get(client):
    route = client.get('/openapi.json').json()['paths']['/api/acquisitions/{id}/terrain-preview']
    assert set(route) == {'get'}
    assert route['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/TerrainPreview')
    assert next(p for p in route['get']['parameters'] if p['name'] == 'attempt_id')['required']
