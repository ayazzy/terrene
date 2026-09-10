"""Natural England Priority Habitats Inventory (England), Version 3 semantics.

The authoritative layer is a mapped inventory.  This module validates the
small source schema CRC uses and performs deterministic parcel intersections;
it does not infer condition, ecological absence, restoration need, suitability
or legal feasibility.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

from backend.earth import fingerprint


SERVICE_URL = (
    'https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/'
    'Priority_Habitats_Inventory_England/FeatureServer/0'
)
CATALOGUE_URL = (
    'https://dsp.environment.data.gov.uk/dataset/'
    '92b43165-0dd0-4e69-a712-1e49bb5aa0d0'
)
ATTRIBUTE_METADATA_URL = (
    'https://environment.data.gov.uk/api/file/download?'
    'fileDataSetId=d30e3fa2-5ca6-4851-b19d-1429ad9d84e0&'
    'fileName=Priority_Habitats_Inventory_Attribute_Metadata.pdf'
)
SPATIAL_METADATA_URL = (
    'https://environment.data.gov.uk/api/file/download?'
    'fileDataSetId=d30e3fa2-5ca6-4851-b19d-1429ad9d84e0&'
    'fileName=Priority_Habitats_Inventory_Spatial_Metadata.pdf'
)
CLASSIFICATION = 'natural_england_priority_habitats_inventory_v3'
SCHEMA_VERSION = 'natural_england_phi_v3_schema_2025_09'
SOURCE_METADATA_REVISION_DATE = '2025-10-01'
CAPTURE_END_DATE = '2025-09-10'
SOURCE_CREATION_DATE = '2013-06-21'

PRIORITY_HABITATS = {
    'BLBOG': 'Blanket bog',
    'CALAM': 'Calaminarian grassland',
    'CFPGM': 'Coastal and floodplain grazing marsh',
    'SALTM': 'Coastal saltmarsh',
    'CSDUN': 'Coastal sand dunes',
    'CVSHI': 'Coastal vegetated shingle',
    'DWOOD': 'Deciduous woodland',
    'LPAVE': 'Limestone pavement',
    'LCGRA': 'Lowland calcareous grassland',
    'LDAGR': 'Lowland dry acid grassland',
    'LFENS': 'Lowland fens',
    'LHEAT': 'Lowland heathland',
    'LMEAD': 'Lowland meadows',
    'LRBOG': 'Lowland raised bog',
    'MCSLP': 'Maritime cliff and slope',
    'MHWSC': 'Mountain heaths and willow scrub',
    'MUDFL': 'Mudflats',
    'PMGRP': 'Purple moor grass and rush pastures',
    'RBEDS': 'Reedbeds',
    'SLAGO': 'Saline lagoons',
    'TORCH': 'Traditional orchard',
    'UCGRA': 'Upland calcareous grassland',
    'UHMEA': 'Upland hay meadow',
    'UHEAT': 'Upland heathland',
    'UFFSW': 'Upland flushes fens and swamps',
    'LAKES': 'Lakes',
    'PONDS': 'Ponds',
}

# PHI also maps these four main classes, but Natural England explicitly says
# they are not priority habitats.  CRC retains their feature relationships and
# never includes them in a priority-habitat overlap observation or union.
SUPPORTING_CLASSES = {
    'FHEAT': 'Fragmented heath',
    'GMOOR': 'Grass moorland',
    'GQSIG': 'Good quality semi improved grassland',
    'NMHAB': 'No main habitat but additional habitats present',
}
MAIN_CLASSES = PRIORITY_HABITATS | SUPPORTING_CLASSES

FEATURE_CLASSES = {
    # ANTHL and DEGRD(LRBOG) are present in the September 2025 live layer in
    # addition to the generic codes described in the service prose.
    'ANTHL': 'Anthills',
    'OLIGO': 'Oligotrophic lakes',
    'DYSTR': 'Dystrophic lakes',
    'MESOT': 'Mesotrophic lakes',
    'EUTRO': 'Eutrophic standing waters',
    'ICEAG': 'Ice age pond',
    'PWFLM': 'Pond with floating mats',
    'UPOWD': 'Upland oakwood',
    'LBYWD': 'Lowland beech and yew woodland',
    'UMAWD': 'Upland mixed ashwoods',
    'WETWD': 'Wet woodland',
    'LMDWD': 'Lowland mixed deciduous woodland',
    'UPBWD': 'Upland birchwoods',
    'ASNWD': 'Ancient semi natural woodland',
    'PAWDS': 'Plantations on ancient woodland',
    'CSOPT': 'Countryside Stewardship Option',
    'WAXCP': 'Waxcap grassland',
    'DRYHL': 'Dry heathland',
    'WETHL': 'Wet heathland',
    'CWDUN': 'Dunes under coniferous woodland',
    'DWDUN': 'Dunes under deciduous woodland',
    'DEGRD': 'Degraded',
    'DEGRD(LRBOG)': 'Degraded(Lowland raised bog)',
}

REQUIRED_FIELDS = {
    'OBJECTID': 'esriFieldTypeOID',
    'GlobalID': 'esriFieldTypeGlobalID',
    'UID': 'esriFieldTypeString',
    'MainHabs': 'esriFieldTypeString',
    'HabCodes': 'esriFieldTypeString',
    'FeatDesc': 'esriFieldTypeString',
    'FeatCodes': 'esriFieldTypeString',
    'OtherClass': 'esriFieldTypeString',
    'AddHabs': 'esriFieldTypeString',
    'PrimSource': 'esriFieldTypeString',
    'AreaHa': 'esriFieldTypeDouble',
    'Version': 'esriFieldTypeString',
}

ATTRIBUTION = (
    '© Natural England 2025. Contains OS data © Crown copyright and database '
    'rights 2022. OS AC0000851168. Contains data created and provided by '
    'Arnside and Silverdale AONB and Lancaster City Council, reproduced with '
    'permission. Contains, or is based on, Forestry Commission information; '
    '© Crown copyright and database right 2022, Ordnance Survey 100021242. '
    'Cumbria Biodiversity Data Centre on behalf of Cumbria Wildlife Trust, '
    'used under CC BY 4.0; and data created and provided by the National Trust, '
    'used under CC BY 4.0. Contains Environment Agency copyright/database-right '
    'data, including OS-derived data; Northumberland National Park Authority '
    'data under OGL v3.0; Natural England, Rural Payments Agency and North '
    'Yorkshire Council data. Exact embedded notices and source-year statements '
    'are identified by the official spatial metadata URL retained with the '
    'immutable acquisition metadata.'
)
LICENCE = (
    'The official spatial metadata declares the product publicly accessible '
    'under the Open Government Licence. Embedded contributor data retain their '
    'stated permissions, copyright notices and CC BY 4.0 terms where identified; '
    'downstream redistribution must follow those source-specific notices.'
)
LIMITATIONS = (
    'Natural England PHI Version 3 is a mapped inventory, not a current field '
    'survey or complete ecological survey. A mapped intersection establishes '
    'only that this release maps the stated main habitat class within the '
    'spatial support. No mapped overlap does not establish ecological absence. '
    'The source does not by itself establish habitat condition, ecological '
    'quality, irreplaceability, restoration need, restoration suitability or '
    'legal development feasibility. Additional-habitat codes mean a habitat '
    'may be present and are retained as qualifiers, not assigned mapped area.'
)


def _split(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str):
        raise ValueError('PHI list attributes must be strings or null')
    return [item.strip() for item in value.split(',') if item.strip()]


def service_edit_timestamp(metadata: dict[str, Any]) -> str | None:
    milliseconds = (metadata.get('editingInfo') or {}).get('dataLastEditDate')
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
        return None
    return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).isoformat()


def validate_service_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Reject a changed layer before CRC imports any features."""
    errors: list[str] = []
    if metadata.get('type') != 'Feature Layer':
        errors.append('not a feature layer')
    if metadata.get('geometryType') != 'esriGeometryPolygon':
        errors.append('geometry is not polygonal')
    wkid = (metadata.get('spatialReference') or {}).get('latestWkid')
    if wkid != 27700:
        errors.append('native CRS is not EPSG:27700')
    if metadata.get('objectIdField') != 'OBJECTID':
        errors.append('OBJECTID field changed')
    if metadata.get('globalIdField') != 'GlobalID':
        errors.append('GlobalID field changed')
    actual_fields = {field.get('name'): field.get('type') for field in metadata.get('fields', [])}
    for name, field_type in REQUIRED_FIELDS.items():
        if actual_fields.get(name) != field_type:
            errors.append(f'{name} field missing or changed')
    if errors:
        raise ValueError('Unexpected Natural England PHI service schema: ' + '; '.join(errors))
    return {
        'schema_version': SCHEMA_VERSION,
        'service_item_id': metadata.get('serviceItemId'),
        'native_crs': 'EPSG:27700',
        'geometry_type': metadata['geometryType'],
        'object_id_field': metadata['objectIdField'],
        'global_id_field': metadata['globalIdField'],
        'fields': {name: actual_fields[name] for name in REQUIRED_FIELDS},
        'service_data_last_edit': service_edit_timestamp(metadata),
        'source_metadata_revision_date': SOURCE_METADATA_REVISION_DATE,
        'capture_end_date': CAPTURE_END_DATE,
        'source_creation_date': SOURCE_CREATION_DATE,
        'attribute_metadata_url': ATTRIBUTE_METADATA_URL,
        'spatial_metadata_url': SPATIAL_METADATA_URL,
    }


def normalize_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Validate only the PHI attributes CRC gives semantic meaning."""
    if not isinstance(properties, dict):
        raise ValueError('PHI feature properties are missing')
    main_codes = _split(properties.get('HabCodes'))
    main_names = _split(properties.get('MainHabs'))
    if not main_codes or len(main_codes) != len(main_names):
        raise ValueError('PHI main habitat names/codes are empty or misaligned')
    for code, name in zip(main_codes, main_names, strict=True):
        if MAIN_CLASSES.get(code) != name:
            raise ValueError(f'Invalid PHI main habitat code/name pair: {code!r} / {name!r}')

    feature_codes = _split(properties.get('FeatCodes'))
    feature_names = _split(properties.get('FeatDesc'))
    if len(feature_codes) != len(feature_names):
        raise ValueError('PHI feature description/code lists are misaligned')
    for code, name in zip(feature_codes, feature_names, strict=True):
        if FEATURE_CLASSES.get(code) != name:
            raise ValueError(f'Invalid PHI feature code/name pair: {code!r} / {name!r}')

    additional_codes = _split(properties.get('AddHabs'))
    unknown_additional = sorted(set(additional_codes) - set(MAIN_CLASSES))
    if unknown_additional:
        raise ValueError('Invalid PHI additional habitat code(s): ' + ', '.join(unknown_additional))

    object_id = properties.get('OBJECTID')
    uid = properties.get('UID')
    global_id = properties.get('GlobalID')
    version = properties.get('Version')
    area_ha = properties.get('AreaHa')
    if isinstance(object_id, bool) or not isinstance(object_id, int):
        raise ValueError('PHI OBJECTID is invalid')
    if not isinstance(uid, str) or not uid:
        raise ValueError('PHI UID is missing')
    if not isinstance(global_id, str) or not global_id:
        raise ValueError('PHI GlobalID is missing')
    if not isinstance(version, str) or not version:
        raise ValueError('PHI publication Version is missing')
    if (isinstance(area_ha, bool) or not isinstance(area_ha, (int, float))
            or not math.isfinite(area_ha) or area_ha < 0):
        raise ValueError('PHI source AreaHa is invalid')
    return {
        'object_id': object_id,
        'uid': uid,
        'global_id': global_id,
        'source_area_ha_rounded': float(area_ha),
        'source_release': version,
        'main_habitats': [
            {
                'code': code,
                'name': name,
                'status': 'priority' if code in PRIORITY_HABITATS else 'supporting_non_priority',
            }
            for code, name in zip(main_codes, main_names, strict=True)
        ],
        'feature_qualifiers': [
            {'code': code, 'description': name}
            for code, name in zip(feature_codes, feature_names, strict=True)
        ],
        'other_classification': properties.get('OtherClass') or None,
        'additional_habitat_codes': additional_codes,
        'primary_source': properties.get('PrimSource') or None,
    }


def summarize_intersections(parcel_geometry: dict[str, Any], rows: list[dict[str, Any]],
                            project, unproject=None) -> dict[str, Any]:
    """Return exact per-class and unioned PHI overlap for one fully covered parcel.

    ``rows`` must be the exhaustive set of imported features whose envelopes
    intersect the parcel.  Spatial indexing may over-select; exact Shapely
    intersection below removes false positives.
    """
    parcel = transform(project, shape(parcel_geometry))
    if parcel.is_empty or parcel.area <= 0:
        raise ValueError('Unsupported parcel geometry for PHI intersection')
    parcel_area_ha = parcel.area / 10000
    by_code: dict[str, list[Any]] = defaultdict(list)
    priority_clips: list[Any] = []
    source_features: list[dict[str, Any]] = []
    releases: set[str] = set()
    seen_uids: set[str] = set()

    for row in rows:
        geometry = row.get('geometry')
        if isinstance(geometry, str):
            import json
            geometry = json.loads(geometry)
        source_geometry = shape(geometry)
        if source_geometry.is_empty or source_geometry.geom_type not in ('Polygon', 'MultiPolygon'):
            raise ValueError('PHI imported geometry is empty or non-polygonal')
        clipped = parcel.intersection(transform(project, source_geometry))
        if clipped.is_empty or clipped.area == 0:
            continue
        normalized = normalize_properties(row.get('properties') or {})
        if normalized['uid'] in seen_uids:
            raise ValueError('Duplicate PHI UID in parcel candidates: ' + normalized['uid'])
        seen_uids.add(normalized['uid'])
        releases.add(normalized['source_release'])
        priority_codes = [
            item['code'] for item in normalized['main_habitats']
            if item['status'] == 'priority'
        ]
        for code in priority_codes:
            by_code[code].append(clipped)
        if priority_codes:
            priority_clips.append(clipped)
        source_features.append({
            **normalized,
            'source_geometry_fingerprint': fingerprint(geometry),
            'intersection_area_ha': clipped.area / 10000,
            'intersection_fraction_of_parcel': clipped.area / parcel.area,
        })

    if len(releases) > 1:
        raise ValueError('PHI parcel features contain mixed publication versions')
    habitats = []
    for code, geometries in sorted(by_code.items()):
        area_ha = parcel.intersection(unary_union(geometries)).area / 10000
        feature_ids = sorted(
            feature['uid'] for feature in source_features
            if any(item['code'] == code for item in feature['main_habitats'])
        )
        habitats.append({
            'habitat_code': code,
            'habitat_name': PRIORITY_HABITATS[code],
            'mapped_intersection_area_ha': area_ha,
            'parcel_area_ha': parcel_area_ha,
            'overlap_fraction': area_ha / parcel_area_ha,
            'source_feature_ids': feature_ids,
        })
    unioned = parcel.intersection(unary_union(priority_clips)) if priority_clips else None
    union_area_ha = unioned.area / 10000 if unioned is not None else 0.0
    return {
        'classification': CLASSIFICATION,
        'schema_version': SCHEMA_VERSION,
        'source_release': next(iter(releases), None),
        'parcel_area_ha': parcel_area_ha,
        'habitats': habitats,
        'any_main_priority_habitat': {
            'definition': 'spatial union of polygons carrying at least one main priority HabCode',
            'mapped_intersection_area_ha': union_area_ha,
            'parcel_area_ha': parcel_area_ha,
            'overlap_fraction': union_area_ha / parcel_area_ha,
            'source_feature_ids': sorted(
                feature['uid'] for feature in source_features
                if any(item['status'] == 'priority' for item in feature['main_habitats'])
            ),
        },
        'source_features': sorted(source_features, key=lambda item: item['uid']),
        'union_geometry': (
            mapping(transform(unproject, unioned))
            if unioned is not None and unproject is not None else None
        ),
    }
