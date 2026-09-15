"""Read-only, bounded presentation of one exact retained EA terrain capture.

The preview is disposable display output, never a replacement raster or Earth fact.
No provider access, persistence, model execution or cross-request cache occurs.
"""
import base64
import math
import struct
from typing import Literal
from uuid import UUID
import zlib

import numpy as np
from pydantic import Field
import pyproj
import rasterio
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling
import shapely
from shapely.geometry import mapping
from shapely.ops import transform

from backend import acquisition as store, acquisition_rasters as raster
from backend.acquisition_contracts import (
    AcquisitionError, Contract, DTM_SOURCE_ID, DTM_ADAPTER_VERSION, digest, encode,
)

RENDERER = 'ea_dtm_grayscale_web_mercator_v1'
MAX_EDGE = 512


class TerrainCapture(Contract):
    acquisition_id: UUID
    attempt_id: UUID
    manifest_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    native_raster_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_id: Literal['environment_agency.lidar_dtm_1m']
    adapter_version: Literal['ea_lidar_dtm_wcs_v1']
    capture_started: str
    capture_completed: str
    observation_time: None = None
    attribution: str
    licence: str


class NativeTerrain(Contract):
    crs: Literal['EPSG:27700'] = 'EPSG:27700'
    resolution_m: Literal[1] = 1
    vertical_unit: Literal['metre'] = 'metre'
    vertical_datum: Literal['Ordnance Datum Newlyn'] = 'Ordnance Datum Newlyn'
    bounds: tuple[float, float, float, float]
    transform: list[float] = Field(min_length=9, max_length=9)
    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    nodata_value: float
    area_cell_count: int = Field(ge=1, le=4_000_000)
    valid_cell_count: int = Field(ge=0, le=4_000_000)
    missing_cell_count: int = Field(ge=0, le=4_000_000)
    coverage_state: Literal['complete', 'partial', 'no_valid_cells']


class TerrainGrid(Contract):
    crs: Literal['EPSG:3857'] = 'EPSG:3857'
    width: int = Field(ge=1, le=MAX_EDGE)
    height: int = Field(ge=1, le=MAX_EDGE)
    bounds: tuple[float, float, float, float]
    transform: list[float] = Field(min_length=9, max_length=9)
    pixel_size_projected_metres: tuple[float, float]
    coordinates_wgs84: list[tuple[float, float]] = Field(min_length=4, max_length=4)
    coordinate_order: Literal['top_left_top_right_bottom_right_bottom_left'] = 'top_left_top_right_bottom_right_bottom_left'
    visible_pixel_count: int = Field(ge=0, le=MAX_EDGE * MAX_EDGE)
    transparent_pixel_count: int = Field(ge=0, le=MAX_EDGE * MAX_EDGE)
    state: Literal['visible_samples', 'no_visible_samples']


class TerrainLegend(Contract):
    kind: Literal['linear_grayscale'] = 'linear_grayscale'
    minimum_elevation_m: float | None
    maximum_elevation_m: float | None
    low_rgb: tuple[int, int, int] = (32, 32, 32)
    high_rgb: tuple[int, int, int] = (240, 240, 240)
    constant_rgb: tuple[int, int, int] = (128, 128, 128)
    range_basis: Literal['all_valid_native_cells_inside_request'] = 'all_valid_native_cells_inside_request'
    missing_alpha: Literal[0] = 0
    valid_alpha: Literal[255] = 255


class TerrainImage(Contract):
    media_type: Literal['image/png'] = 'image/png'
    encoding: Literal['base64'] = 'base64'
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    bytes: int = Field(ge=1, le=1_100_000)
    data: str = Field(max_length=1_500_000)


class TerrainRendering(Contract):
    version: Literal['ea_dtm_grayscale_web_mercator_v1'] = RENDERER
    resampling: Literal['nearest'] = 'nearest'
    max_edge_pixels: Literal[512] = MAX_EDGE
    runtime_versions: dict[str, str]
    polygon_mask: Literal['native_and_display_pixel_centres_holes_excluded'] = 'native_and_display_pixel_centres_holes_excluded'
    geometry_projection: Literal['acquisition_native_polygon_densified_25m_to_display'] = 'acquisition_native_polygon_densified_25m_to_display'
    display_only: Literal[True] = True


class TerrainPreview(Contract):
    contract_version: Literal['terrain_preview_v1'] = 'terrain_preview_v1'
    capture: TerrainCapture
    requested_geometry: dict
    native: NativeTerrain
    grid: TerrainGrid
    legend: TerrainLegend
    image: TerrainImage
    rendering: TerrainRendering
    preview_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    limitations: list[str]


def _png(rgba):
    """Fixed RGBA8 PNG encoding: filter 0, no metadata, zlib level 9."""
    height, width, _ = rgba.shape
    def chunk(kind, payload):
        return (struct.pack('!I', len(payload)) + kind + payload
                + struct.pack('!I', zlib.crc32(kind + payload)))
    rows = b''.join(b'\x00' + row.tobytes() for row in rgba)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def read_terrain_preview(org, acquisition_id, *, attempt_id):
    try:
        acquisition_id, attempt_id = str(UUID(acquisition_id)), str(UUID(attempt_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise AcquisitionError('not_found') from exc
    summary = store.read_acquisition(org, acquisition_id, attempt_id=attempt_id)
    if summary['state'] != 'succeeded':
        raise AcquisitionError('not_found')
    request = summary['request']
    if (request['source_id'], request['adapter_version']) != (DTM_SOURCE_ID, DTM_ADAPTER_VERSION):
        raise AcquisitionError('terrain_preview_unsupported_source')
    source = summary['source']
    descriptor = raster.descriptor()
    for key in ('source_id', 'adapter_version', 'coverage_id', 'native_crs',
                'resolution_m', 'vertical_unit', 'vertical_datum', 'attribution', 'licence'):
        if source.get(key) != descriptor[key]:
            raise AcquisitionError('integrity_failure')

    # Read the exact manifest once more to obtain original bytes, without exposing
    # private keys. All artifacts were verified above; recheck these bytes on use.
    manifest = store._load(org, {'key': store._object_key(org, summary['manifest_sha256']),
                                 'sha256': summary['manifest_sha256']})
    def artifact(name):
        return store._load(org, manifest['artifacts'][name])
    polygon, bounds = raster.request_window(request['area'])
    before, after = artifact('provider_description_before'), artifact('provider_description_after')
    raster.validate_description(before, bounds)
    if before != after:
        raise AcquisitionError('integrity_failure')
    content = artifact('native_raster')
    native = raster.inspect_raster(content, request['area'], bounds)
    if native != summary['result']['raster'] or summary['result']['publisher_coverage_id'] != raster.COVERAGE:
        raise AcquisitionError('integrity_failure')
    if any(summary['result'].get(k) is not None for k in ('observation_time', 'publication_time', 'publisher_release_id')):
        raise AcquisitionError('integrity_failure')

    with MemoryFile(content) as memory, memory.open() as dataset:
        data = dataset.read(1, masked=True)
        inside = geometry_mask([mapping(polygon)], out_shape=data.shape,
                               transform=dataset.transform, invert=True, all_touched=False)
        valid = inside & ~np.ma.getmaskarray(data) & np.isfinite(data.data)
        low = float(data.data[valid].min()) if valid.any() else None
        high = float(data.data[valid].max()) if valid.any() else None
        source_values = np.where(valid, data.data, np.nan).astype('float32')
        affine, width, height = calculate_default_transform(
            dataset.crs, 'EPSG:3857', dataset.width, dataset.height, *dataset.bounds)
        factor = max(1, max(width, height) / MAX_EDGE)
        out_width = min(MAX_EDGE, math.ceil(width / factor))
        out_height = min(MAX_EDGE, math.ceil(height / factor))
        affine = affine @ affine.scale(width / out_width, height / out_height)
        display = np.full((out_height, out_width), np.nan, dtype='float32')
        reproject(source_values, display, src_transform=dataset.transform,
                  src_crs=dataset.crs, src_nodata=np.nan, dst_transform=affine,
                  dst_crs='EPSG:3857', dst_nodata=np.nan, resampling=Resampling.nearest,
                  num_threads=1, warp_mem_limit=32)

    # Use the native acquisition polygon as authority; densification only reduces
    # curvature error when projecting its edges for display.
    display_polygon = transform(pyproj.Transformer.from_crs(27700, 3857, always_xy=True).transform,
                                polygon.segmentize(25))
    display_inside = geometry_mask([mapping(display_polygon)], out_shape=display.shape,
                                   transform=affine, invert=True, all_touched=False)
    visible = np.isfinite(display) & display_inside
    rgba = np.zeros((*display.shape, 4), dtype='uint8')
    if visible.any():
        shade = (np.rint(32 + 208 * np.clip((display[visible].astype('float64') - low) / (high - low), 0, 1))
                 if high != low else np.full(int(visible.sum()), 128))
        rgba[visible, :3] = shade.astype('uint8')[:, None]
        rgba[visible, 3] = 255
    png = _png(rgba)
    west, south, east, north = array_bounds(out_height, out_width, affine)
    to_wgs84 = pyproj.Transformer.from_crs(3857, 4326, always_xy=True)
    capture = TerrainCapture(
        acquisition_id=acquisition_id, attempt_id=attempt_id,
        manifest_sha256=summary['manifest_sha256'],
        native_raster_sha256=summary['artifact_checksums']['native_raster']['sha256'],
        source_id=DTM_SOURCE_ID, adapter_version=DTM_ADAPTER_VERSION,
        capture_started=summary['started'], capture_completed=summary['completed'],
        attribution=source['attribution'], licence=source['licence'])
    native_view = NativeTerrain(bounds=native['bounds_27700'], **{
        key: native[key] for key in NativeTerrain.model_fields if key != 'bounds'})
    grid = TerrainGrid(width=out_width, height=out_height, bounds=(west, south, east, north),
        transform=list(affine), pixel_size_projected_metres=(affine.a, -affine.e),
        coordinates_wgs84=[to_wgs84.transform(x, y) for x, y in
                           [(west, north), (east, north), (east, south), (west, south)]],
        visible_pixel_count=int(visible.sum()), transparent_pixel_count=int((~visible).sum()),
        state='visible_samples' if visible.any() else 'no_visible_samples')
    legend = TerrainLegend(minimum_elevation_m=low, maximum_elevation_m=high)
    rendering = TerrainRendering(runtime_versions={
        'rasterio': rasterio.__version__, 'gdal': rasterio.__gdal_version__,
        'pyproj': pyproj.__version__, 'proj': pyproj.proj_version_str,
        'shapely': shapely.__version__, 'numpy': np.__version__, 'zlib': zlib.ZLIB_RUNTIME_VERSION})
    image = TerrainImage(sha256=digest(png), bytes=len(png), data=base64.b64encode(png).decode('ascii'))
    payload = dict(capture=capture.model_dump(mode='json'), requested_geometry=request['area'],
        native=native_view.model_dump(mode='json'), grid=grid.model_dump(mode='json'),
        legend=legend.model_dump(mode='json'), rendering=rendering.model_dump(mode='json'),
        image=image.model_dump(exclude={'data'}), contract_version='terrain_preview_v1',
        limitations=[
            'Display-only nearest-neighbour reprojection; native raster remains unchanged and authoritative.',
            'Transparent pixels include nodata, polygon holes and outside-request areas; never zero elevation.',
            'Reduced display resolution can omit small valid or missing features; native availability counts remain separate.',
            'Grayscale range is local to all valid native request cells; independently stretched previews are not directly comparable.',
            'Historical composite with unknown local survey dates; no current-survey, height, slope, flood or climate interpretation.',
            'Projected display pixel size is not native ground resolution; grayscale pixels are not elevation measurements.',
        ])
    return TerrainPreview(**{**payload, 'image': image}, preview_fingerprint=digest(encode(payload)))
