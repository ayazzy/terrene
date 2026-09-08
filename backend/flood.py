"""Bounded, fail-closed OGC Features adapter for EA's current flood zones."""
from urllib.parse import urljoin, urlparse, parse_qs
import httpx

SERVICE = 'https://environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1'
COLLECTION = 'Flood_Zones_2_3_Rivers_and_Sea'
COLLECTION_URL = SERVICE + '/collections/' + COLLECTION
CATALOG_URL = 'https://www.data.gov.uk/dataset/104434b0-5263-4c90-9b1e-e43b1d57c750/flood-map-for-planning-flood-zones1'
CRS84 = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
# Focused Oxford corridor; sites outside this extent remain unknown for flood data.
FLOOD_BBOX = [-1.33, 51.72, -1.22, 51.82]
MAX_BYTES = 128 * 1024 * 1024
MAX_FEATURES = 50000
LIMITATIONS = (
    'Combined mapped extent of Flood Zones 2 and 3, at present day, from rivers and the sea; '
    'ignores benefits of defences. Zone 1 is not mapped. Groundwater, sewer and other flood '
    'sources are not represented, and not every small river is included. No overlap does not '
    'mean no flood risk. Not a property-level flood assessment, climate-change projection, '
    'functional-floodplain classification or evidence of wetland/restoration suitability.'
)
ATTRIBUTION = '© Environment Agency copyright and/or database right 2025. All rights reserved. Open Government Licence v3.'


def fetch_flood(bbox, client=None):
    """Follow only same-collection bounded next links; reject incomplete snapshots."""
    if client is None:
        with httpx.Client(timeout=60, follow_redirects=True) as owned_client:
            return fetch_flood(bbox, owned_client)

    budget = 0
    def read(url, params=None):
        nonlocal budget
        with client.stream('GET', url, params=params) as response:
            response.raise_for_status()
            chunks = []
            for chunk in response.iter_bytes():
                budget += len(chunk)
                if budget > MAX_BYTES:
                    raise ValueError('Flood import exceeded the bounded 128 MiB download limit.')
                chunks.append(chunk)
            import json
            return json.loads(b''.join(chunks)), response.headers, str(response.url)

    metadata, _, _ = read(COLLECTION_URL, {'f': 'json'})
    if metadata.get('id') != COLLECTION:
        raise ValueError('Unexpected EA flood collection; import rejected.')
    bbox_text = ','.join(map(str, bbox))
    item_links = [link['href'] for link in metadata.get('links', [])
                  if link.get('rel') == 'items' and link.get('type') == 'application/json']
    url = item_links[0] if item_links else COLLECTION_URL + '/items'
    initial = urlparse(url)
    if initial.scheme != 'https' or initial.netloc != 'environment.data.gov.uk' or not initial.path.endswith('/collections/' + COLLECTION + '/items'):
        raise ValueError('Unexpected flood collection items URL.')
    params = {'f': 'json', 'bbox': bbox_text, 'limit': 250, 'crs': CRS84}
    features, seen_ids, seen_pages, page_records = [], set(), set(), []
    expected = None
    zone_counts = {'FZ2': 0, 'FZ3': 0}
    while url:
        if url in seen_pages:
            raise ValueError('Flood pagination loop; import rejected.')
        seen_pages.add(url)
        data, headers, resolved_url = read(url, params)
        if headers.get('content-crs', '').strip('<>') != CRS84:
            raise ValueError('Flood response did not confirm longitude/latitude CRS84.')
        batch = data.get('features')
        matched = data.get('numberMatched')
        if data.get('type') != 'FeatureCollection' or not isinstance(batch, list):
            raise ValueError('Flood response is not a GeoJSON FeatureCollection.')
        if not isinstance(matched, int) or matched < 0 or matched > MAX_FEATURES:
            raise ValueError('Flood source did not confirm a bounded total feature count.')
        if expected is None:
            expected = matched
        if matched != expected or data.get('numberReturned') != len(batch):
            raise ValueError('Flood source counts changed or page is incomplete.')
        if len(features) + len(batch) > expected:
            raise ValueError('Flood source returned more features than declared.')
        for feature in batch:
            fid = feature.get('id')
            if not isinstance(fid, (str, int)) or fid in seen_ids:
                raise ValueError('Flood feature IDs are missing or repeated.')
            zone = (feature.get('properties') or {}).get('flood_zone')
            if zone not in zone_counts:
                raise ValueError('Unknown flood-zone value; schema review required.')
            if (feature.get('geometry') or {}).get('type') not in ('Polygon', 'MultiPolygon'):
                raise ValueError('Flood source returned a non-polygon geometry.')
            seen_ids.add(fid)
            zone_counts[zone] += 1
        features.extend(batch)
        page_records.append({'url': resolved_url, 'returned': len(batch), 'timestamp': data.get('timeStamp')})
        next_links = [link for link in data.get('links', []) if link.get('rel') == 'next']
        if len(next_links) > 1:
            raise ValueError('Ambiguous flood pagination; import rejected.')
        if not next_links:
            break
        if not batch or len(features) >= expected:
            raise ValueError('Unexpected flood continuation; import rejected.')
        next_url = urljoin(resolved_url, next_links[0]['href'])
        parsed = urlparse(next_url)
        current = urlparse(resolved_url)
        query = parse_qs(parsed.query)
        if (parsed.scheme != 'https' or parsed.netloc != 'environment.data.gov.uk'
                or parsed.path != current.path
                or query.get('bbox') != [bbox_text]
                or query.get('crs') != [CRS84]
                or query.get('limit') != ['250']
                or query.get('startIndex') != [str(len(features))]):
            raise ValueError('Flood next link changed the bounded query; import rejected.')
        url, params = next_url, None
    if len(features) != expected:
        raise ValueError('Flood pagination ended early; missing data is not zero overlap.')
    metadata.update(crc_download_bytes=budget, crc_pages=page_records,
                    crc_zone_counts=zone_counts, crc_bbox=bbox,
                    crc_output_crs=CRS84, crc_catalog_url=CATALOG_URL)
    return metadata, {'type': 'FeatureCollection', 'features': features}
