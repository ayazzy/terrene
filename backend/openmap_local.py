"""Narrow OS OpenMap - Local built-world object and relationship semantics.

The admitted source feature types are deliberately fixed: generalized Building
polygons, FunctionalSite polygons, RailwayTrack lines and RailwayStation
points.  This is not a general ontology layer and it does not infer operational
status, legal footprints, surface widths, development constraint or
suitability.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import md5, sha256
import json
import math
from pathlib import Path
import tempfile
from typing import Any, Iterable
from uuid import UUID
from zipfile import ZipFile

import httpx
from pyproj import CRS, Transformer
import shapefile
from shapely import set_precision
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union

from backend.earth import fingerprint


PRODUCT_ID = 'OpenMapLocal'
SOURCE_RELEASE = '2026-04'
SOURCE_TILE = 'SP'
SOURCE_CRS = 'EPSG:27700'
PRODUCT_URL = 'https://api.os.uk/downloads/v1/products/OpenMapLocal'
DOWNLOAD_URL = (
    'https://api.os.uk/downloads/v1/products/OpenMapLocal/downloads'
    '?area=SP&format=ESRI%C2%AE+Shapefile&redirect'
)
TECHNICAL_SPECIFICATION_URL = (
    'https://docs.os.uk/os-downloads/products/maps-and-imagery-portfolio/'
    'os-openmap-local/os-openmap-local-technical-specification'
)
SCHEMA_URL = 'https://www.ordnancesurvey.co.uk/xml/open/oml/1.0/OSOpenMapLocal.xsd'
SITE_CLASSIFICATION_URL = (
    'https://www.ordnancesurvey.co.uk/xml/codelists/map/SiteClassificationOML.xml'
)
SITE_THEME_URL = 'https://www.ordnancesurvey.co.uk/xml/codelists/sites/SiteTheme.xml'
RAIL_TRACK_CLASSIFICATION_URL = (
    'https://www.ordnancesurvey.co.uk/xml/codelists/map/'
    'RailwayTrackClassificationOML.xml'
)
RAIL_STATION_CLASSIFICATION_URL = (
    'https://www.ordnancesurvey.co.uk/xml/codelists/map/'
    'RailwayStationClassificationOML.xml'
)
DOWNLOAD_MD5 = 'fce94d990c044ae6316e566b418224f6'
DOWNLOAD_SHA256 = '1e1654017820ef8cf63a93d16a148849cecb651c3e5cb8f153840df931f91bd6'
DOWNLOAD_FILE_NAME = 'opmplc_essh_sp.zip'
SCHEMA_VERSION = 'os_openmap_local_1_0_shapefile_2026_04'
PROCESSING_VERSION = 'crc_openmap_local_spatial_v1'
SEARCH_RADIUS_M = 5000.0
SPATIAL_PRECISION_M = 0.01

# The existing CRC Oxford pilot support, clipped to the authoritative SP
# 100 km source tile. Features needed to prove a complete 5 km railway search
# around that support are retained during import, but are never treated as
# parcel coverage outside this declared area.
OXFORD_PILOT_WGS84 = box(-1.65, 51.5, -0.85, 52.05)
SP_TILE_BNG = box(400000, 200000, 500000, 300000)
TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True).transform
TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True).transform
COVERAGE_WGS84 = OXFORD_PILOT_WGS84.intersection(transform(TO_WGS84, SP_TILE_BNG))
RAIL_DISTANCE_COVERAGE_BNG = transform(TO_BNG, COVERAGE_WGS84).buffer(-SEARCH_RADIUS_M)

ATTRIBUTION = 'Contains Ordnance Survey data © Crown copyright and database right 2026.'
LICENCE = 'OS OpenData licensed under the Open Government Licence v3.0.'
LIMITATIONS = (
    'OS OpenMap - Local is generalized contextual mapping at nominal 1:10,000 '
    '(recommended viewing range 1:3,000 to 1:20,000), not a legal, cadastral '
    'or engineering survey. Building polygons may amalgamate buildings and '
    'structures and are not exact footprints. FunctionalSite classification '
    'records mapped function, theme and name but does not establish current '
    'operational status. RailwayTrack features are lines, can be broken under '
    'bridges, buildings or other obstructing detail, and exclude sidings and '
    'tracks of travelling structures; they are not surface footprints. A fully '
    'examined mapped zero means no qualifying feature is represented by this '
    'release at this scale, not that no real-world object exists.'
)

FEATURE_SCHEMAS = {
    'building': {
        'file': 'SP_Building', 'shape_type': shapefile.POLYGONZ,
        'fields': {'ID': ('C', 38, 0), 'FEATCODE': ('N', 5, 0)},
        'feature_code': 15014,
    },
    'functional_site': {
        'file': 'SP_FunctionalSite', 'shape_type': shapefile.POLYGONZ,
        'fields': {
            'ID': ('C', 38, 0), 'DISTNAME': ('C', 120, 0),
            'SITETHEME': ('C', 21, 0), 'CLASSIFICA': ('C', 90, 0),
            'FEATCODE': ('N', 5, 0),
        },
        'feature_codes': {15809, 15810, 15811, 15812, 15813},
    },
    'railway_track': {
        'file': 'SP_RailwayTrack', 'shape_type': shapefile.POLYLINEZ,
        'fields': {
            'ID': ('C', 38, 0), 'CLASSIFICA': ('C', 45, 0),
            'FEATCODE': ('N', 5, 0),
        },
        'feature_codes': {15300, 15301, 15302},
    },
    'railway_station': {
        'file': 'SP_RailwayStation', 'shape_type': shapefile.POINTZ,
        'fields': {
            'ID': ('C', 38, 0), 'DISTNAME': ('C', 150, 0),
            'CLASSIFICA': ('C', 65, 0), 'FEATCODE': ('N', 5, 0),
        },
        'feature_codes': {15420, 15421, 15422, 15424, 15425},
    },
}

SITE_THEMES = {
    'Air Transport', 'Education', 'Medical Care', 'Road Transport', 'Water Transport',
}
SITE_CLASSIFICATIONS = {
    'Airfield', 'Airport', 'Helicopter Station', 'Heliport',
    'Non State Primary Education', 'Non State Secondary Education',
    'Special Needs Education', 'Primary Education', 'Secondary Education',
    'Further Education', 'Higher or University Education', 'Hospice', 'Hospital',
    'Medical Care Accommodation', 'Vehicular Ferry Terminal',
    'Passenger Ferry Terminal', 'Port Consisting of Docks and Nautical Berthing',
    'Bus Station', 'Coach Station', 'Road User Services',
    'Bus Station,Coach Station',
    'Passenger Ferry Terminal,Vehicular Ferry Terminal',
    'Hospital,Medical Care Accommodation',
    'Further Education,Higher or University Education',
    'Further Education,Non State Primary Education,Non State Secondary Education',
    'Further Education,Non State Primary Education,Secondary Education',
    'Further Education,Non State Secondary Education',
    'Further Education,Primary Education',
    'Further Education,Primary Education,Secondary Education',
    'Further Education,Primary Education,Secondary Education,Special Needs Education',
    'Further Education,Secondary Education',
    'Further Education,Special Needs Education',
    'Non State Primary Education,Non State Secondary Education',
    'Non State Primary Education,Non State Secondary Education,Special Needs Education',
    'Non State Primary Education,Secondary Education',
    'Non State Secondary Education,Primary Education',
    'Non State Secondary Education,Special Needs Education',
    'Primary Education,Secondary Education',
    'Primary Education,Secondary Education,Special Needs Education',
    'Primary Education,Special Needs Education',
    'Secondary Education,Special Needs Education',
}
RAIL_TRACK_CLASSIFICATIONS = {'Multi Track', 'Single Track', 'Narrow Gauge'}
RAIL_STATION_CLASSIFICATIONS = {
    'Light Rapid Transit Station',
    'Light Rapid Transit Station And London Underground Station',
    'Light Rapid Transit Station And Railway Station',
    'London Underground Station', 'Railway Station',
    'Railway Station And London Underground Station',
}


def _canonical_geometry(value: dict[str, Any]) -> dict[str, Any]:
    """Drop unused Z values while retaining the source's BNG vertices."""
    geometry = shape(value)
    if geometry.has_z:
        geometry = transform(lambda x, y, z=None: (x, y), geometry)
    return mapping(geometry)


def _object_key(object_type: str, source_feature_id: str) -> str:
    return object_type + ':' + source_feature_id.upper()


def validate_properties(object_type: str, properties: dict[str, Any]) -> dict[str, Any]:
    if object_type not in FEATURE_SCHEMAS or not isinstance(properties, dict):
        raise ValueError('Unsupported or missing OpenMap Local source properties')
    source_id = properties.get('source_feature_id') or properties.get('ID')
    try:
        normalized_id = str(UUID(str(source_id))).upper()
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError('OpenMap Local source feature ID is not a UUID') from error
    code = properties.get('feature_code', properties.get('FEATCODE'))
    if isinstance(code, bool) or not isinstance(code, int):
        raise ValueError('OpenMap Local feature code is invalid')
    schema = FEATURE_SCHEMAS[object_type]
    valid_codes = schema.get('feature_codes', {schema.get('feature_code')})
    if code not in valid_codes:
        raise ValueError(f'Unexpected OpenMap Local feature code for {object_type}: {code}')
    normalized = {
        'object_type': object_type, 'source_feature_id': normalized_id,
        'feature_code': code,
    }
    if object_type == 'functional_site':
        theme = properties.get('site_theme', properties.get('SITETHEME'))
        classification = properties.get('classification', properties.get('CLASSIFICA'))
        if theme not in SITE_THEMES or classification not in SITE_CLASSIFICATIONS:
            raise ValueError('Unexpected OpenMap Local FunctionalSite code-list value')
        normalized.update(
            distinctive_name=(properties.get('distinctive_name', properties.get('DISTNAME')) or None),
            site_theme=theme, classification=classification,
        )
    elif object_type == 'railway_track':
        classification = properties.get('classification', properties.get('CLASSIFICA'))
        if classification not in RAIL_TRACK_CLASSIFICATIONS:
            raise ValueError('Unexpected OpenMap Local RailwayTrack classification')
        normalized['classification'] = classification
    elif object_type == 'railway_station':
        classification = properties.get('classification', properties.get('CLASSIFICA'))
        name = properties.get('distinctive_name', properties.get('DISTNAME'))
        if classification not in RAIL_STATION_CLASSIFICATIONS or not isinstance(name, str) or not name:
            raise ValueError('Unexpected OpenMap Local RailwayStation attributes')
        normalized.update(distinctive_name=name, classification=classification)
    return normalized


def validate_shapefile_schema(object_type: str, reader: shapefile.Reader) -> dict[str, Any]:
    expected = FEATURE_SCHEMAS[object_type]
    errors: list[str] = []
    if reader.shapeType != expected['shape_type']:
        errors.append(f"shape type {reader.shapeTypeName}")
    actual = {
        field.name: (field.field_type, field.size, field.decimal)
        for field in reader.fields if field.name != 'DeletionFlag'
    }
    if actual != expected['fields']:
        errors.append('DBF fields changed')
    if errors:
        raise ValueError(
            f'Unexpected OpenMap Local {object_type} shapefile schema: ' + '; '.join(errors)
        )
    return {
        'shape_type': reader.shapeTypeName,
        'fields': {
            name: {'type': field_type, 'length': length, 'decimal': decimal}
            for name, (field_type, length, decimal) in actual.items()
        },
    }


def validate_product_metadata(product: dict[str, Any], downloads: list[dict[str, Any]]) -> dict[str, Any]:
    if product.get('id') != PRODUCT_ID or product.get('version') != SOURCE_RELEASE:
        raise ValueError('Live OS OpenMap Local release no longer matches the pinned release')
    match = [item for item in downloads if item.get('area') == SOURCE_TILE
             and item.get('format') == 'ESRI® Shapefile']
    if len(match) != 1:
        raise ValueError('OS Downloads API did not return one SP shapefile artifact')
    item = match[0]
    if (item.get('md5') != DOWNLOAD_MD5 or item.get('fileName') != DOWNLOAD_FILE_NAME
            or item.get('size') != 132851994):
        raise ValueError('OS OpenMap Local SP artifact identity changed')
    return item


def acquire_archive(path: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    """Return a verified pinned archive and live official catalogue metadata."""
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        product_response = client.get(PRODUCT_URL)
        product_response.raise_for_status()
        product = product_response.json()
        downloads_response = client.get(PRODUCT_URL + '/downloads')
        downloads_response.raise_for_status()
        download = validate_product_metadata(product, downloads_response.json())
        if path is None:
            with client.stream('GET', DOWNLOAD_URL) as response:
                response.raise_for_status()
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as handle:
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 150_000_000:
                            raise ValueError('OpenMap Local archive exceeds bounded size')
                        handle.write(chunk)
                    archive_path = Path(handle.name)
        else:
            archive_path = Path(path)
    content = archive_path.read_bytes()
    content_sha256 = sha256(content).hexdigest()
    if (len(content) != download['size'] or md5(content).hexdigest() != download['md5']
            or content_sha256 != DOWNLOAD_SHA256):
        raise ValueError('OpenMap Local archive checksum or size mismatch')
    return archive_path, {
        'product': product, 'download': download,
        'sha256': content_sha256,
    }


def _layer_member(object_type: str, suffix: str) -> str:
    stem = FEATURE_SCHEMAS[object_type]['file']
    return f'OS OpenMap Local (ESRI Shape File) SP/data/{stem}.{suffix}'


def inspect_archive(archive_path: str | Path) -> dict[str, Any]:
    """Validate admitted layer schemas and return bounded source objects."""
    admitted: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    counts: dict[str, int] = defaultdict(int)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            required = {
                _layer_member(object_type, suffix)
                for object_type in FEATURE_SCHEMAS for suffix in ('shp', 'shx', 'dbf', 'prj')
            }
            if not required <= names:
                raise ValueError('OpenMap Local archive is missing an admitted shapefile member')
            for name in sorted(required):
                archive.extract(name, root)

        for object_type, expected in FEATURE_SCHEMAS.items():
            path = root / _layer_member(object_type, 'shp')
            projection_text = (root / _layer_member(object_type, 'prj')).read_text()
            if CRS.from_wkt(projection_text).to_epsg() != 27700:
                raise ValueError(
                    f'Unexpected OpenMap Local {object_type} coordinate reference system'
                )
            reader = shapefile.Reader(str(path))
            schemas[object_type] = validate_shapefile_schema(object_type, reader)
            # Polygon objects only support parcel intersection. Railway objects
            # retain the 5 km halo required for complete bounded distances.
            support = COVERAGE_WGS84
            if object_type.startswith('railway_'):
                support = transform(TO_BNG, support).buffer(SEARCH_RADIUS_M)
                bbox_bng = support.bounds
            else:
                bbox_bng = transform(TO_BNG, support).bounds
            for record in reader.iterShapeRecords(bbox=bbox_bng):
                geometry = _canonical_geometry(record.shape.__geo_interface__)
                geometry_bng = shape(geometry)
                if not geometry_bng.intersects(
                    support if object_type.startswith('railway_') else transform(TO_BNG, support)
                ):
                    continue
                properties = validate_properties(object_type, record.record.as_dict())
                admitted.append({'geometry': geometry, 'properties': properties})
                counts[object_type] += 1
    admitted.sort(key=lambda item: (
        item['properties']['object_type'], item['properties']['source_feature_id']
    ))
    return {'schemas': schemas, 'counts': dict(counts), 'features': admitted}


def coverage_for_parcel(parcel_geometry: dict[str, Any]) -> tuple[str, float | None]:
    parcel = shape(parcel_geometry)
    if COVERAGE_WGS84.covers(parcel):
        return 'covered', 1.0
    intersection = COVERAGE_WGS84.intersection(parcel)
    if not intersection.is_empty:
        parcel_bng = transform(TO_BNG, parcel)
        fraction = transform(TO_BNG, intersection).area / parcel_bng.area
        if 0 < fraction < 1:
            return 'partial', fraction
    return 'unknown', None


def _relationship(source_key: str, predicate: str, **measurements: float) -> dict[str, Any]:
    return {
        'source_object_key': source_key, 'predicate': predicate,
        'measurements': measurements,
        'processing_method': PROCESSING_VERSION,
    }


def _bounded_fraction(numerator: float, denominator: float) -> float:
    """Clamp only floating-point boundary noise around the mathematical [0, 1] range."""
    return min(1.0, max(0.0, numerator / denominator))


def summarize_relationships(parcel_geometry: dict[str, Any], rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Derive deterministic objects, predicates and parcel observations.

    ``rows`` must exhaust the admitted source candidates intersecting the
    parcel envelope for polygon layers and its 5 km envelope for rail layers.
    Geometry is the unmodified two-dimensional source geometry in EPSG:27700.
    """
    # WGS84 parcel coordinates cannot generally round-trip to BNG exactly.
    # A declared centimetre precision grid removes sub-millimetre transform
    # noise so boundary touch and crossing remain stable and inspectable.
    parcel = set_precision(transform(TO_BNG, shape(parcel_geometry)), SPATIAL_PRECISION_M)
    if parcel.is_empty or parcel.area <= 0:
        raise ValueError('Unsupported parcel geometry for OpenMap Local processing')
    candidates: dict[str, list[tuple[dict[str, Any], Any, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for row in rows:
        properties = validate_properties(
            (row.get('properties') or {}).get('object_type'), row.get('properties') or {}
        )
        geometry = row.get('geometry')
        if isinstance(geometry, str):
            geometry = json.loads(geometry)
        source_geometry = shape(geometry)
        working_geometry = set_precision(source_geometry, SPATIAL_PRECISION_M)
        expected_types = {
            'building': {'Polygon', 'MultiPolygon'},
            'functional_site': {'Polygon', 'MultiPolygon'},
            'railway_track': {'LineString', 'MultiLineString'},
            'railway_station': {'Point'},
        }
        if source_geometry.is_empty or source_geometry.geom_type not in expected_types[properties['object_type']]:
            raise ValueError('Unexpected OpenMap Local source geometry type')
        key = _object_key(properties['object_type'], properties['source_feature_id'])
        if key in seen:
            raise ValueError('Duplicate OpenMap Local source object in candidates: ' + key)
        seen.add(key)
        candidates[properties['object_type']].append(
            (properties, source_geometry, working_geometry)
        )

    retained: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []
    polygon_clips: dict[str, list[Any]] = {'building': [], 'functional_site': []}
    polygon_support: dict[str, list[str]] = {'building': [], 'functional_site': []}
    intersecting_tracks: list[tuple[str, Any]] = []

    def retain(properties: dict[str, Any], geometry: Any) -> str:
        key = _object_key(properties['object_type'], properties['source_feature_id'])
        if key not in retained:
            retained[key] = {
                **properties, 'source_object_key': key,
                'source_release': SOURCE_RELEASE, 'source_crs': SOURCE_CRS,
                'source_geometry': mapping(geometry),
                'source_geometry_fingerprint': fingerprint(mapping(geometry)),
            }
        return key

    for object_type in ('building', 'functional_site'):
        for properties, source_geometry, geometry in candidates[object_type]:
            intersection = parcel.intersection(geometry)
            if intersection.is_empty:
                continue
            key = retain(properties, source_geometry)
            if intersection.area > 0:
                predicate = 'contained_within' if parcel.covers(geometry) else 'overlaps'
                relationships.append(_relationship(
                    key, predicate, overlap_area_m2=intersection.area,
                    parcel_overlap_fraction=_bounded_fraction(intersection.area, parcel.area),
                    object_overlap_fraction=_bounded_fraction(intersection.area, geometry.area),
                ))
                polygon_clips[object_type].append(intersection)
                polygon_support[object_type].append(key)
            elif geometry.touches(parcel):
                relationships.append(_relationship(key, 'touches'))

    for properties, source_geometry, geometry in candidates['railway_track']:
        intersection = parcel.intersection(geometry)
        if intersection.is_empty:
            continue
        key = retain(properties, source_geometry)
        if geometry.touches(parcel):
            predicate = 'touches'
        elif parcel.covers(geometry):
            predicate = 'contained_within'
        elif geometry.crosses(parcel):
            predicate = 'crosses'
        else:
            predicate = 'intersects'
        length = intersection.length if predicate != 'touches' else 0.0
        relationships.append(_relationship(key, predicate, **(
            {'length_within_m': length} if length > 0 else {}
        )))
        if length > 0:
            intersecting_tracks.append((key, intersection))

    for properties, source_geometry, geometry in candidates['railway_station']:
        if not geometry.intersects(parcel):
            continue
        key = retain(properties, source_geometry)
        predicate = 'contained_within' if parcel.contains(geometry) else 'touches'
        relationships.append(_relationship(key, predicate))

    rail_distance_coverage = (
        'full' if RAIL_DISTANCE_COVERAGE_BNG.covers(parcel) else 'partial'
    )
    distance_support: dict[str, list[str]] = {}
    for object_type in ('railway_track', 'railway_station'):
        if rail_distance_coverage != 'full':
            distance_support[object_type] = []
            continue
        distances = [
            (parcel.distance(geometry), properties['source_feature_id'], properties,
             source_geometry, geometry)
            for properties, source_geometry, geometry in candidates[object_type]
        ]
        if not distances:
            distance_support[object_type] = []
            continue
        minimum = min(item[0] for item in distances)
        if minimum > SEARCH_RADIUS_M:
            distance_support[object_type] = []
            continue
        nearest = [item for item in distances if math.isclose(item[0], minimum, rel_tol=0, abs_tol=1e-9)]
        keys = []
        for distance, _, properties, source_geometry, _ in sorted(
                nearest, key=lambda item: item[1]):
            key = retain(properties, source_geometry)
            keys.append(key)
            relationships.append(_relationship(key, 'minimum_distance', minimum_distance_m=distance))
        distance_support[object_type] = keys

    observations: list[dict[str, Any]] = []
    for object_type, definition_id in (
        ('building', 'built.building.mapped_overlap_fraction'),
        ('functional_site', 'built.functional_site.mapped_overlap_fraction'),
    ):
        unioned = unary_union(polygon_clips[object_type]) if polygon_clips[object_type] else None
        numerator = unioned.area if unioned is not None else 0.0
        observations.append({
            'definition_id': definition_id, 'value': _bounded_fraction(numerator, parcel.area),
            'numerator': numerator, 'denominator': parcel.area,
            'numerator_unit': 'm2', 'denominator_unit': 'm2',
            'aggregation': 'clipped_source_polygon_spatial_union',
            'supporting_source_object_keys': sorted(polygon_support[object_type]),
        })

    track_union = unary_union([item[1] for item in intersecting_tracks]) if intersecting_tracks else None
    track_length = track_union.length if track_union is not None else 0.0
    observations.append({
        'definition_id': 'transport.railway_track.mapped_length_within',
        'value': track_length, 'numerator': track_length, 'denominator': None,
        'numerator_unit': 'm', 'denominator_unit': None,
        'aggregation': 'clipped_source_line_spatial_union',
        'supporting_source_object_keys': sorted(key for key, _ in intersecting_tracks),
    })
    for object_type, definition_id in (
        ('railway_track', 'transport.railway_track.distance_min'),
        ('railway_station', 'transport.railway_station.distance_min'),
    ):
        keys = distance_support[object_type]
        if keys:
            distance = next(
                relation['measurements']['minimum_distance_m']
                for relation in relationships
                if relation['predicate'] == 'minimum_distance'
                and relation['source_object_key'] == keys[0]
            )
            observations.append({
                'definition_id': definition_id, 'value': distance,
                'numerator': distance, 'denominator': None,
                'numerator_unit': 'm', 'denominator_unit': None,
                'aggregation': 'minimum_euclidean_distance_within_complete_5000m_search',
                'supporting_source_object_keys': keys,
            })

    return {
        'schema_version': SCHEMA_VERSION, 'processing_version': PROCESSING_VERSION,
        'source_release': SOURCE_RELEASE, 'source_crs': SOURCE_CRS,
        'coverage': 'covered', 'parcel_area_m2': parcel.area,
        'search_radius_m': SEARCH_RADIUS_M,
        'rail_distance_coverage': rail_distance_coverage,
        'objects': [retained[key] for key in sorted(retained)],
        'relationships': sorted(relationships, key=lambda item: (
            item['source_object_key'], item['predicate'], json.dumps(item['measurements'], sort_keys=True)
        )),
        'observations': sorted(observations, key=lambda item: item['definition_id']),
    }
