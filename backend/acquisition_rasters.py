"""Independent EA terrain/surface capture: native bytes and cell availability.

No slope, height, flood, suitability or other model is executed by acquisition.
"""
import math
from xml.etree import ElementTree as ET

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from shapely.geometry import shape, mapping
from shapely.ops import transform

from backend.acquisition_contracts import (
    AcquisitionError, BinaryArtifact, DTM_SOURCE_ID, DTM_ADAPTER_VERSION,
    DSM_SOURCE_ID, DSM_ADAPTER_VERSION,
)

SERVICE = 'https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs'
COVERAGE = '13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m'
CATALOGUE = 'https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m'
COVERAGE_PROFILE_VERSION = 'ons_england_dec2024_bfe_v1'
PROCESSING_VERSION = 'ea_dtm_native_cell_coverage_v1'
DSM_SERVICE = 'https://environment.data.gov.uk/spatialdata/lidar-composite-digital-surface-model-last-return-dsm-1m/wcs'
DSM_COVERAGE = '9ba4d5ac-d596-445a-9056-dae3ddec0178__Lidar_Composite_Elevation_LZ_DSM_1m'
DSM_CATALOGUE = 'https://www.data.gov.uk/dataset/cf3f1137-c12b-44a1-a835-e80fe4a60b92/lidar-composite-digital-surface-model-dsm-1m'
DSM_PROCESSING_VERSION = 'ea_dsm_native_cell_coverage_v1'
MAX_CELLS = 4_000_000
MAX_DIMENSION = 4096
LIMITS = {'max_window_cells': MAX_CELLS, 'max_dimension_pixels': MAX_DIMENSION,
          'max_response_bytes': 32_000_000, 'max_total_bytes': 36_000_000,
          'max_metadata_bytes': 2_000_000, 'network_deadline_seconds': 180,
          'request_timeout_seconds': 45}
PROJECT = Transformer.from_crs(4326, 27700, always_xy=True).transform
NS = {'wcs': 'http://www.opengis.net/wcs/2.0', 'gml': 'http://www.opengis.net/gml/3.2',
      'swe': 'http://www.opengis.net/swe/2.0'}


def definition(adapter_version=DTM_ADAPTER_VERSION):
    if adapter_version == DTM_ADAPTER_VERSION:
        return SERVICE, COVERAGE, PROCESSING_VERSION
    if adapter_version == DSM_ADAPTER_VERSION:
        return DSM_SERVICE, DSM_COVERAGE, DSM_PROCESSING_VERSION
    raise AcquisitionError('unsupported_adapter')


def descriptor(adapter_version=DTM_ADAPTER_VERSION):
    definition(adapter_version)
    if adapter_version == DSM_ADAPTER_VERSION:
        value = descriptor()
        value.update(source_id=DSM_SOURCE_ID, adapter_version=DSM_ADAPTER_VERSION,
                     capability_version='england_current_surface_raster_v1',
                     normalization_version=DSM_PROCESSING_VERSION,
                     endpoint=DSM_SERVICE, coverage_id=DSM_COVERAGE, catalogue_url=DSM_CATALOGUE,
                     vertical_semantics_source=DSM_CATALOGUE,
                     surface_semantics='Last-return composite surface elevation including terrain, buildings, vegetation and vehicles; not height above ground.')
        value['limitations'][0] = 'Historical last-return surface composite, not bare-earth terrain, raw point clouds or a current survey.'
        value['limitations'].append('Matching DTM/DSM grids do not establish common local survey dates or valid building-height interpretation.')
        return value
    return {
        'source_id': DTM_SOURCE_ID, 'adapter_version': DTM_ADAPTER_VERSION,
        'capability_version': 'england_current_terrain_raster_v1',
        'normalization_version': PROCESSING_VERSION, 'data_family': 'raster',
        'publisher': 'Environment Agency', 'jurisdiction': 'England',
        'endpoint': SERVICE, 'coverage_id': COVERAGE, 'catalogue_url': CATALOGUE,
        'coverage_profile_version': COVERAGE_PROFILE_VERSION,
        'access': 'public; no credentials', 'licence': 'Open Government Licence',
        'attribution': '© Environment Agency copyright and/or database right 2022. All rights reserved.',
        'native_crs': 'EPSG:27700', 'retrieved_crs': 'EPSG:27700',
        'resolution_m': 1, 'vertical_unit': 'metre', 'vertical_datum': 'Ordnance Datum Newlyn',
        'vertical_semantics_source': CATALOGUE,
        'temporal_modes': ['current_publication'],
        'catalogue_composite_label': '2022 (catalogue checked 2026-09-14; not an immutable WCS release identifier)',
        'limits': LIMITS,
        'coverage_method': 'Whole requested polygon inside pinned ONS England BFE; native valid-cell coverage checked separately.',
        'limitations': [
            'Raster terrain composite, not raw LIDAR point clouds or a current field survey.',
            'Publisher composite merges historical surveys and may contain publisher-resampled cells; Terrene requests the published 1 m grid without further resampling.',
            'Local survey date and immutable publisher release are unknown; retrieval time is separate.',
            'The WCS radiance unit tag is erroneous for this dataset; metre/ODN semantics are bound to the official catalogue, not inferred from that tag.',
            'Administrative support does not prove raster availability. Nodata is missing terrain, not zero elevation.',
            'Centre-in-polygon coverage excludes holes and is not predictive confidence or continuous subpixel coverage.',
            'Before/after coverage definitions detect schema changes, not every in-place pixel change; WCS offers no atomic snapshot here.',
            'No slope, hydrology, building height, flood probability or future climate interpretation is produced.',
        ],
    }


def request_window(area):
    polygon = transform(PROJECT, shape(area))
    if polygon.is_empty or not polygon.is_valid or not all(math.isfinite(v) for v in polygon.bounds):
        raise AcquisitionError('invalid_projected_geometry')
    left, bottom, right, top = polygon.bounds
    bounds = [math.floor(left)-3, math.floor(bottom)-3, math.ceil(right)+3, math.ceil(top)+3]
    width, height = bounds[2]-bounds[0], bounds[3]-bounds[1]
    if width*height > MAX_CELLS or max(width, height) > MAX_DIMENSION:
        raise AcquisitionError('raster_window_limit')
    return polygon, bounds


def describe_parameters(adapter_version=DTM_ADAPTER_VERSION):
    return {'service': 'WCS', 'version': '2.0.1', 'request': 'DescribeCoverage', 'coverageId': definition(adapter_version)[1]}


def raster_parameters(bounds, adapter_version=DTM_ADAPTER_VERSION):
    west, south, east, north = bounds
    return [('service', 'WCS'), ('version', '2.0.1'), ('request', 'GetCoverage'),
            ('coverageId', definition(adapter_version)[1]), ('format', 'image/tiff'),
            ('subset', f'E({west},{east})'), ('subset', f'N({south},{north})')]


def validate_description(content, bounds, adapter_version=DTM_ADAPTER_VERSION):
    coverage_id = definition(adapter_version)[1]
    try:
        if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
            raise ValueError('xml_declaration')
        root = ET.fromstring(content)
        descriptions = root.findall('wcs:CoverageDescription', NS)
        if len(descriptions) != 1:
            raise ValueError('coverage_count')
        item = descriptions[0]
        envelope = item.find('gml:boundedBy/gml:Envelope', NS)
        vectors = [tuple(map(float, n.text.split())) for n in item.findall('.//gml:offsetVector', NS)]
        if (item.findtext('wcs:CoverageId', namespaces=NS) != coverage_id
                or envelope.attrib.get('srsName') != 'http://www.opengis.net/def/crs/EPSG/0/27700'
                or envelope.attrib.get('axisLabels') != 'E N'
                or vectors != [(1.0, 0.0), (0.0, -1.0)]
                or item.find('.//swe:field', NS).attrib.get('name') != 'Elevation'
                # Pin the observed erroneous tag; changed units require review of
                # the catalogue binding rather than a silent reinterpretation.
                or item.find('.//swe:field/swe:Quantity/swe:uom', NS).attrib.get('code') != 'W.m-2.Sr-1'):
            raise ValueError('identity_or_grid')
        lower = list(map(float, envelope.findtext('gml:lowerCorner', namespaces=NS).split()))
        upper = list(map(float, envelope.findtext('gml:upperCorner', namespaces=NS).split()))
        if len(lower) != 2 or len(upper) != 2 or not all(math.isfinite(v) for v in lower+upper):
            raise ValueError('extent')
        if not (lower[0] <= bounds[0] < bounds[2] <= upper[0] and lower[1] <= bounds[1] < bounds[3] <= upper[1]):
            raise AcquisitionError('outside_raster_extent')
    except AcquisitionError:
        raise
    except (ET.ParseError, ValueError, AttributeError, TypeError) as exc:
        raise AcquisitionError('raster_source_schema_changed') from exc


def inspect_raster(content, area, bounds, adapter_version=DTM_ADAPTER_VERSION):
    """Validate native grid before allocation; count only the requested area cells."""
    processing_version = definition(adapter_version)[2]
    if content[:4] not in (b'II*\x00', b'MM\x00*', b'II+\x00', b'MM\x00+'):
        raise AcquisitionError('invalid_raster_response')
    polygon, expected_bounds = request_window(area)
    if list(bounds) != expected_bounds:
        raise AcquisitionError('raster_window_mismatch')
    try:
        with MemoryFile(content) as memory, memory.open() as dataset:
            affine = dataset.transform
            if (dataset.driver != 'GTiff' or dataset.count != 1
                    or dataset.crs != rasterio.crs.CRS.from_epsg(27700)
                    or dataset.dtypes != ('float32',)
                    or affine.a != 1 or affine.e != -1 or affine.b != 0 or affine.d != 0):
                raise AcquisitionError('raster_grid_mismatch')
            if dataset.width*dataset.height > MAX_CELLS or max(dataset.width, dataset.height) > MAX_DIMENSION:
                raise AcquisitionError('raster_window_limit')
            if list(dataset.bounds) != list(bounds):
                raise AcquisitionError('raster_extent_mismatch')
            nodata = dataset.nodata
            if nodata is None or not math.isfinite(nodata):
                raise AcquisitionError('raster_nodata_undefined')
            values = dataset.read(1, masked=True)
            valid = ~np.ma.getmaskarray(values) & np.isfinite(values.data)
            if np.any(valid & ((values.data < -500) | (values.data > 9000))):
                raise AcquisitionError('invalid_elevation_values')
            inside = geometry_mask([mapping(polygon)], out_shape=values.shape,
                                   transform=affine, invert=True, all_touched=False)
            total = int(inside.sum())
            if total == 0:
                raise AcquisitionError('no_sample_cell_centres')
            available = int((inside & valid).sum())
            return {
                'contract_version': 'geographic_raster_coverage_v1', 'processing_version': processing_version,
                'crs': 'EPSG:27700', 'resolution_m': 1, 'band_count': 1, 'dtype': 'float32',
                'vertical_unit': 'metre', 'vertical_datum': 'Ordnance Datum Newlyn',
                'width': dataset.width, 'height': dataset.height, 'transform': list(affine),
                'bounds_27700': list(dataset.bounds), 'nodata_value': nodata,
                'area_cell_count': total, 'valid_cell_count': available,
                'missing_cell_count': total-available, 'valid_cell_fraction': available/total,
                'coverage_state': 'complete' if available == total else ('partial' if available else 'no_valid_cells'),
                'sampling_method': 'Native cell centres in projected request polygon; holes excluded. No filling, reprojection of raster, resampling or clipping.',
                'projection_method': 'pyproj EPSG:4326 to EPSG:27700, always_xy; polygon vertices transformed without densification.',
                'retained_extent': 'Unmodified WCS bounding window with 3 m margin; availability counts refer only to the request polygon.',
            }
    except AcquisitionError:
        raise
    except (rasterio.errors.RasterioError, ValueError, OSError) as exc:
        raise AcquisitionError('invalid_raster_response') from exc


def fetch_raster(request, *, client=None, artifacts=None, diagnostics=None):
    from backend.acquisition_sources import BoundedClient
    adapter_version = request.adapter_version
    endpoint, coverage_id, _ = definition(adapter_version)
    artifacts = artifacts if artifacts is not None else {}
    diagnostics = diagnostics if diagnostics is not None else {}
    reader = BoundedClient(client, max_response=LIMITS['max_response_bytes'], max_total=LIMITS['max_total_bytes'],
                           seconds=LIMITS['network_deadline_seconds'], request_timeout=LIMITS['request_timeout_seconds'])
    try:
        _, bounds = request_window(request.area)
        diagnostics['requested_bounds_27700'] = bounds
        before = reader.get_bytes(endpoint, describe_parameters(adapter_version), max_bytes=LIMITS['max_metadata_bytes'])
        artifacts['provider_description_before'] = BinaryArtifact(before, 'application/xml')
        validate_description(before, bounds, adapter_version)
        raster = reader.get_bytes(endpoint, raster_parameters(bounds, adapter_version))
        artifacts['native_raster'] = BinaryArtifact(raster, 'image/tiff')
        coverage = inspect_raster(raster, request.area, bounds, adapter_version)
        artifacts['raster_coverage'] = coverage
        after = reader.get_bytes(endpoint, describe_parameters(adapter_version), max_bytes=LIMITS['max_metadata_bytes'])
        artifacts['provider_description_after'] = BinaryArtifact(after, 'application/xml')
        validate_description(after, bounds, adapter_version)
        if before != after:
            raise AcquisitionError('source_changed_during_capture')
        return {'data_family': 'raster', 'raster': coverage, 'publisher_coverage_id': coverage_id,
                'publisher_release_id': None, 'observation_time': None, 'publication_time': None,
                'completeness': 'complete_bounded_response',
                'time_semantics': 'Current WCS composite capture; local constituent survey date is unknown.'}
    finally:
        diagnostics['responses'] = reader.responses
        diagnostics['decoded_bytes_received'] = reader.bytes_received
        reader.close()


def fetch_dtm(request, **kwargs):
    """Preserve the terrain-only internal entry point and reject role confusion."""
    if request.adapter_version != DTM_ADAPTER_VERSION:
        raise AcquisitionError('source_adapter_mismatch')
    return fetch_raster(request, **kwargs)
