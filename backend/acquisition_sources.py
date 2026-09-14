"""Bounded current-publication Natural England adapter and pinned coverage setup."""
import json
import time

import httpx
from shapely import make_valid
from shapely.geometry import mapping, shape, box

from backend import core
from backend.acquisition_contracts import (
    AcquisitionError, ADAPTER_VERSION, FULL_EXTENT_ADAPTER_VERSION, SOURCE_ID, MAX_AREA_HA, digest, encode,
)

SSSI_URL = ('https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/'
            'SSSI_England/FeatureServer/0')
COVERAGE_URL = ('https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/'
                'Countries_December_2024_Boundaries_UK_BFC/FeatureServer/0')
COVERAGE_ITEM = 'https://www.arcgis.com/sharing/rest/content/items/d4f6b6bdf58a45b093c0c189bdf92e9d'
COVERAGE_VERSION = 'ons_england_dec2024_bfc_v1'
FULL_EXTENT_COVERAGE_VERSION = 'ons_england_dec2024_bfe_v1'
FULL_EXTENT_COVERAGE_URL = ('https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/'
                            'Countries_December_2024_Boundaries_UK_BFE/FeatureServer/0')
FULL_EXTENT_COVERAGE_ITEM = 'https://www.arcgis.com/sharing/rest/content/items/2d18d8d4d0b341dfbddebd39d66dbe79'
# Each adapter explicitly selects a policy; old requests must never gain coverage.
COVERAGE_POLICIES = {
    COVERAGE_VERSION: (COVERAGE_URL, COVERAGE_ITEM),
    FULL_EXTENT_COVERAGE_VERSION: (FULL_EXTENT_COVERAGE_URL, FULL_EXTENT_COVERAGE_ITEM),
}
ADAPTER_COVERAGE = {
    ADAPTER_VERSION: COVERAGE_VERSION,
    FULL_EXTENT_ADAPTER_VERSION: FULL_EXTENT_COVERAGE_VERSION,
}
LIMITS = {'max_area_ha': MAX_AREA_HA, 'max_features': 2_000, 'batch_size': 100,
          'max_response_bytes': 20_000_000, 'max_total_bytes': 60_000_000,
          'network_deadline_seconds': 180, 'request_timeout_seconds': 25}
DESCRIPTOR = {
    'source_id': SOURCE_ID, 'adapter_version': ADAPTER_VERSION,
    'capability_version': 'england_current_vector_v1',
    'data_family': 'vector', 'publisher': 'Natural England', 'jurisdiction': 'England',
    'designation_type': 'SSSI', 'native_identifier_field': 'REF_CODE',
    'publication_object_identifier_field': 'OBJECTID', 'native_crs': 'EPSG:27700',
    'retrieved_crs': 'OGC:CRS84', 'temporal_modes': ['current_publication'],
    'endpoint': SSSI_URL, 'access': 'public; no credentials', 'resolution_m': None,
    'licence': 'Open Government Licence; Natural England/Ordnance Survey attribution applies',
    'terms_url': 'https://www.data.gov.uk/dataset/5b632bd7-9838-4ef2-9101-ea9384421b0d/sites-of-special-scientific-interest-england3',
    'attribution': '© Natural England copyright. Contains Ordnance Survey data © Crown copyright and database right [year].',
    'limits': LIMITS,
    'coverage_method': 'Request must be wholly covered by pinned ONS England December 2024 BFC polygon.',
    'limitations': [
        'Notified SSSIs only; excludes proposed sites, impact risk zones and site condition.',
        'Current publication is not a historical archive or an immutable publisher release.',
        'Capture time is not designation, observation or publication time.',
        'ONS BFC coverage is clipped to mean high water and retains water exclusions; coastal, tidal-water and offshore requests may be declined.',
        'Complete retrieval and mapped absence do not establish complete real-world absence.',
        'Before/after metadata and ID checks detect some changes, but the service has no snapshot transaction.',
    ],
}


def source_descriptor(adapter_version=ADAPTER_VERSION):
    if adapter_version == ADAPTER_VERSION:
        return DESCRIPTOR
    if adapter_version != FULL_EXTENT_ADAPTER_VERSION:
        raise AcquisitionError('unsupported_adapter')
    return {
        **DESCRIPTOR, 'adapter_version': FULL_EXTENT_ADAPTER_VERSION,
        'capability_version': 'england_current_vector_v2',
        'coverage_profile_version': FULL_EXTENT_COVERAGE_VERSION,
        'coverage_method': 'Request must be wholly covered by pinned ONS England December 2024 BFE extent-of-realm polygon.',
        'limitations': [line for line in DESCRIPTOR['limitations'] if not line.startswith('ONS BFC')]
        + ['ONS BFE is an administrative operational footprint, generally to mean low water; it does not establish complete marine or legal designation coverage.'],
    }


class BoundedClient:
    def __init__(self, client=None, *, max_response=None, max_total=None, seconds=None, request_timeout=None):
        self.client = client or httpx.Client(follow_redirects=False)
        self.owned = client is None
        self.max_response = max_response or LIMITS['max_response_bytes']
        self.max_total = max_total or LIMITS['max_total_bytes']
        self.deadline = time.monotonic() + (seconds or LIMITS['network_deadline_seconds'])
        self.request_timeout = request_timeout or LIMITS['request_timeout_seconds']
        self.bytes_received = 0
        self.responses = []

    def close(self):
        if self.owned:
            self.client.close()

    def get(self, url, params):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise AcquisitionError('network_deadline')
        try:
            with self.client.stream('GET', url, params=params,
                                    timeout=min(remaining, self.request_timeout)) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    self.bytes_received += len(chunk)
                    if size > self.max_response or self.bytes_received > self.max_total:
                        raise AcquisitionError('byte_limit')
                    if time.monotonic() > self.deadline:
                        raise AcquisitionError('network_deadline')
                    chunks.append(chunk)
                data = b''.join(chunks)
                # These hashes describe decoded response bytes, not the compressed wire payload.
                self.responses.append({'endpoint': url, 'parameters': params,
                                       'decoded_response_sha256': digest(data), 'decoded_bytes': size})
                value = json.loads(data)
                if not isinstance(value, dict) or value.get('error'):
                    raise AcquisitionError('provider_error')
                return value
        except httpx.HTTPError as exc:
            raise AcquisitionError('network_failure') from exc
        except (ValueError, UnicodeError) as exc:
            raise AcquisitionError('invalid_provider_json') from exc


def _profile_key(sha):
    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise AcquisitionError('invalid_coverage_identity')
    return f'geographic-acquisition/coverage/{sha}.json'


def load_coverage(sha, *, expected_version=None):
    try:
        data = core.load_object(_profile_key(sha))
        if data is None:
            raise AcquisitionError('coverage_not_prepared')
        if digest(data) != sha:
            raise AcquisitionError('coverage_integrity_failure')
        profile = json.loads(data)
        policy = COVERAGE_POLICIES.get(profile['version'])
        if (policy is None or profile['endpoint'] != policy[0]
                or profile['feature']['properties']['CTRY24CD'] != 'E92000001'):
            raise AcquisitionError('coverage_integrity_failure')
        if expected_version is not None and profile['version'] != expected_version:
            raise AcquisitionError('coverage_version_mismatch')
        geometry = shape(profile['feature']['geometry'])
        if geometry.geom_type not in ('Polygon', 'MultiPolygon') or geometry.is_empty or not geometry.is_valid:
            raise AcquisitionError('coverage_integrity_failure')
        return profile, geometry
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError('coverage_integrity_failure') from exc


def prepare_coverage(*, client=None, adapter_version=ADAPTER_VERSION):
    """Explicit one-time operator bootstrap; no boundary data is bundled in Git."""
    if adapter_version not in ADAPTER_COVERAGE:
        raise AcquisitionError('unsupported_adapter')
    version = ADAPTER_COVERAGE[adapter_version]
    endpoint, item_endpoint = COVERAGE_POLICIES[version]
    reader = BoundedClient(client, max_response=100_000_000, max_total=110_000_000,
                           seconds=240, request_timeout=75)
    try:
        metadata = reader.get(endpoint, {'f': 'json'})
        item = reader.get(item_endpoint, {'f': 'json'})
        if item.get('id') != item_endpoint.rsplit('/', 1)[1] or item.get('owner') != 'ONSGeography_data':
            raise AcquisitionError('coverage_schema_changed')
        if version == FULL_EXTENT_COVERAGE_VERSION:
            spatial = metadata.get('extent', {}).get('spatialReference', {})
            if (item.get('url') != endpoint.rsplit('/', 1)[0] or item.get('type') != 'Feature Service'
                    or metadata.get('geometryType') != 'esriGeometryPolygon'
                    or spatial.get('latestWkid', spatial.get('wkid')) != 27700):
                raise AcquisitionError('coverage_schema_changed')
        collection = reader.get(endpoint + '/query', {
            'f': 'geojson', 'where': "CTRY24CD='E92000001'", 'outFields': '*',
            'outSR': '4326', 'returnGeometry': 'true',
        })
        if (collection.get('type') != 'FeatureCollection' or collection.get('exceededTransferLimit')
                or len(collection.get('features', [])) != 1):
            raise AcquisitionError('incomplete_coverage')
        feature = collection['features'][0]
        geometry = shape(feature['geometry'])
        if (feature['properties'].get('CTRY24CD') != 'E92000001' or not geometry.is_valid
                or geometry.is_empty or geometry.geom_type not in ('Polygon', 'MultiPolygon')):
            raise AcquisitionError('invalid_coverage_geometry')
        if version == FULL_EXTENT_COVERAGE_VERSION:
            if collection.get('crs') != {'type': 'name', 'properties': {'name': 'EPSG:4326'}}:
                raise AcquisitionError('coverage_schema_changed')
            after = reader.get(endpoint, {'f': 'json'})
            if encode(after) != encode(metadata):
                raise AcquisitionError('coverage_changed_during_capture')
        profile = {'version': version, 'endpoint': endpoint,
                   'captured_at': core.now(), 'metadata': metadata, 'item_metadata': item,
                   'feature': feature, 'responses': reader.responses,
                   'method': 'Whole-area covers test; no repair, buffer or clipping.',
                   'limitations': 'December 2024 full resolution, clipped to mean high water; operational coverage, not legal advice.'}
        if version == FULL_EXTENT_COVERAGE_VERSION:
            profile.update(metadata_after=after,
                           limitations='December 2024 full resolution, extent of realm, generally mean low water. Operational administrative footprint; not complete marine or legal designation coverage.')
        data = encode(profile)
        sha = digest(data)
        core.store_object_immutable(_profile_key(sha), data)
        load_coverage(sha, expected_version=version)
        return {'coverage_profile_sha256': sha, 'version': version,
                'captured_at': profile['captured_at'], 'country': 'England'}
    finally:
        reader.close()


def validate_capabilities(request):
    if request.temporal.mode != 'current_publication':
        raise AcquisitionError('unsupported_time')
    profile, coverage = load_coverage(request.coverage_profile_sha256,
                                      expected_version=ADAPTER_COVERAGE[request.adapter_version])
    if not coverage.covers(shape(request.area)):
        raise AcquisitionError('unsupported_geography')
    return profile


def _metadata(reader):
    value = reader.get(SSSI_URL, {'f': 'json'})
    fields = {f['name']: f.get('type') for f in value.get('fields', [])}
    spatial = value.get('extent', {}).get('spatialReference', {})
    if (value.get('geometryType') != 'esriGeometryPolygon' or value.get('objectIdField') != 'OBJECTID'
            or fields.get('OBJECTID') != 'esriFieldTypeOID' or 'REF_CODE' not in fields
            or spatial.get('latestWkid', spatial.get('wkid')) != 27700):
        raise AcquisitionError('source_schema_changed')
    return value


def _ids(reader, envelope):
    value = reader.get(SSSI_URL + '/query', {
        'f': 'json', 'where': '1=1', 'geometry': ','.join(map(str, envelope)),
        'geometryType': 'esriGeometryEnvelope', 'inSR': '4326',
        'spatialRel': 'esriSpatialRelIntersects', 'returnIdsOnly': 'true',
    })
    ids = value.get('objectIds')
    if (value.get('exceededTransferLimit') or value.get('objectIdFieldName') != 'OBJECTID'
            or not isinstance(ids, list) or any(type(i) is not int for i in ids)
            or len(ids) != len(set(ids))):
        raise AcquisitionError('incomplete_selection')
    if len(ids) > LIMITS['max_features']:
        raise AcquisitionError('feature_limit')
    return sorted(ids)


def fetch_sssi(request, *, client=None, artifacts=None, diagnostics=None):
    """Collect envelope candidates completely, then select using normalized polygons.

    Artifacts/diagnostics accumulate even on failure for the attempt manifest.
    """
    artifacts = artifacts if artifacts is not None else {}
    diagnostics = diagnostics if diagnostics is not None else {}
    reader = BoundedClient(client)
    try:
        area = shape(request.area)
        envelope = list(area.bounds)
        before = _metadata(reader)
        artifacts['provider_metadata_before'] = before
        ids = _ids(reader, envelope)
        diagnostics.update({'envelope': envelope, 'expected_object_ids': ids})
        original = {'type': 'FeatureCollection', 'features': []}
        artifacts['assembled_provider_candidates'] = original
        size = min(LIMITS['batch_size'], before.get('maxRecordCount', 100))
        if type(size) is not int or size < 1:
            raise AcquisitionError('source_schema_changed')
        for offset in range(0, len(ids), size):
            batch = ids[offset:offset + size]
            value = reader.get(SSSI_URL + '/query', {
                'f': 'geojson', 'objectIds': ','.join(map(str, batch)), 'outFields': '*',
                'outSR': '4326', 'returnGeometry': 'true',
            })
            if value.get('type') != 'FeatureCollection' or value.get('exceededTransferLimit'):
                raise AcquisitionError('incomplete_selection')
            if value.get('crs') and value['crs'] not in (
                {'type': 'name', 'properties': {'name': 'EPSG:4326'}},
                {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'}},
            ):
                raise AcquisitionError('source_crs_changed')
            features = value.get('features')
            if not isinstance(features, list):
                raise AcquisitionError('incomplete_selection')
            returned = [f.get('properties', {}).get('OBJECTID') for f in features]
            original['features'].extend(features)  # Retain response features before normalization.
            if (any(type(i) is not int for i in returned) or sorted(returned) != batch
                    or any('id' in f and f['id'] != f['properties']['OBJECTID'] for f in features)):
                raise AcquisitionError('inconsistent_feature_ids')
        after_ids = _ids(reader, envelope)
        after = _metadata(reader)
        artifacts['provider_metadata_after'] = after
        if after_ids != ids or encode(before) != encode(after):
            raise AcquisitionError('source_changed_during_capture')
        normalized, lineage, selected_ids, native_ids = [], [], [], []
        for feature in original['features']:
            try:
                geometry = shape(feature['geometry'])
                if geometry.is_empty or geometry.geom_type not in ('Polygon', 'MultiPolygon') or not box(-180, -90, 180, 90).covers(geometry):
                    raise ValueError('invalid_geometry')
                repaired = not geometry.is_valid
                normalized_geometry = make_valid(geometry) if repaired else geometry
                if (not normalized_geometry.is_valid or normalized_geometry.is_empty
                        or normalized_geometry.geom_type not in ('Polygon', 'MultiPolygon')):
                    raise ValueError('unsafe_repair')
                native = feature['properties']['REF_CODE']
                if not isinstance(native, str) or not native.strip():
                    raise ValueError('missing_native_id')
                selected = normalized_geometry.intersects(area)
                oid = feature['properties']['OBJECTID']
                lineage.append({'object_id': oid, 'native_id': native, 'repaired': repaired,
                                'method': 'shapely.make_valid' if repaired else 'unchanged',
                                'selected': selected})
                if selected:
                    selected_ids.append(oid)
                    native_ids.append(native)
                    normalized.append({'type': 'Feature', 'id': oid, 'properties': feature['properties'],
                                       'geometry': mapping(normalized_geometry)})
            except (ValueError, TypeError, KeyError) as exc:
                raise AcquisitionError('invalid_source_geometry_or_identity') from exc
        artifacts['normalized_selection'] = {'type': 'FeatureCollection', 'features': normalized}
        artifacts['normalization_lineage'] = lineage
        return {'feature_count': len(normalized), 'candidate_count': len(ids),
                'selected_object_ids': selected_ids, 'native_feature_ids': native_ids,
                'selection': 'Full normalized provider features intersecting request polygon; not clipped.',
                'envelope': envelope, 'completeness': 'complete_provider_selection',
                'publisher_editing_info': before.get('editingInfo'),
                'publisher_release_id': None, 'observation_time': None, 'publication_time': None}
    finally:
        diagnostics['responses'] = reader.responses
        diagnostics['decoded_bytes_received'] = reader.bytes_received
        reader.close()
