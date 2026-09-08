"""Independent, bounded EA WWNP reconnection benchmark; never a model input."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import httpx
from pyproj import Transformer
from shapely import make_valid
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union

COLLECTION_URL = 'https://environment.data.gov.uk/spatialdata/wwnp-floodplain-reconnection-potential/ogc/features/v1/collections/WWNP_Floodplain_Reconnection_Potential'
CATALOG_URL = 'https://www.data.gov.uk/dataset/11873c69-d971-44ce-a648-872da9be847f/wwnp-floodplain-reconnection-potential'
CRS84 = 'http://www.opengis.net/def/crs/OGC/1.3/CRS84'
BBOX = [-1.33, 51.72, -1.22, 51.82]
METHOD = 'crc_wwnp_benchmark_v1 / polygon union and parcel intersection in EPSG:27700'
MEANING = ('Binary mapped floodplain reconnection potential, not a high/low wetland suitability map. '
           'EA targets currently poorly connected floodplain near watercourses; an existing active '
           'floodplain may not be mapped. Absence is not evidence of low wetland potential. '
           'Mapping is an independent broadscale benchmark, not ground truth or an input to CRC.')


def fetch_benchmark(cache_dir, bbox=None, refresh=False, client=None):
    """One bounded response, requiring complete counts; larger extracts fail closed."""
    bbox = list(bbox or BBOX)
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    key = sha256(json.dumps(bbox).encode()).hexdigest()[:16]
    manifest = cache / f'wwnp-{key}.json'
    if manifest.is_file() and not refresh:
        saved = json.loads(manifest.read_text())
        content = Path(saved['storage_reference']).read_bytes()
        if sha256(content).hexdigest() != saved['sha256']:
            raise ValueError('WWNP cached source checksum mismatch')
        return saved
    if client is None:
        with httpx.Client(timeout=90, follow_redirects=True) as owned:
            return fetch_benchmark(cache_dir, bbox, refresh, owned)
    params = {'bbox': ','.join(map(str, bbox)), 'limit': 10000, 'f': 'json', 'crs': CRS84}
    chunks, total = [], 0
    with client.stream('GET', COLLECTION_URL + '/items', params=params) as response:
        response.raise_for_status()
        if response.headers.get('content-crs', '').strip('<>') != CRS84:
            raise ValueError('WWNP response did not confirm CRS84')
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > 32 * 1024 * 1024:
                raise ValueError('WWNP extract exceeds bounded 32 MiB limit')
            chunks.append(chunk)
        resolved = str(response.url)
    content = b''.join(chunks)
    data = json.loads(content)
    features = data.get('features')
    if (data.get('type') != 'FeatureCollection' or not isinstance(features, list)
            or data.get('numberMatched') != len(features)
            or data.get('numberReturned') != len(features)
            or any(link.get('rel') == 'next' for link in data.get('links', []))):
        raise ValueError('Incomplete WWNP extract; absence cannot be interpreted')
    identifiers = [f.get('id') for f in features]
    if None in identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError('WWNP feature IDs missing or repeated')
    repairs = []
    for f in features:
        g = shape(f['geometry'])
        if g.geom_type not in ('Polygon', 'MultiPolygon') or g.is_empty:
            raise ValueError('Unexpected WWNP geometry')
        if not g.is_valid:
            repairs.append(f['id'])
    digest = sha256(content).hexdigest()
    source = cache / f'wwnp-{digest}.geojson'
    source.write_bytes(content)
    result = {'dataset': 'EA WWNP Floodplain Reconnection Potential', 'source_url': COLLECTION_URL,
              'catalog_url': CATALOG_URL, 'request_url': resolved, 'bbox': bbox,
              'retrieved_at': datetime.now(timezone.utc).isoformat(),
              'source_response_timestamp': data.get('timeStamp'),
              'dataset_creation_date': '2017-09-01', 'catalog_revision_date': '2024-05-31',
              'observation_date': None, 'spatial_resolution_m': None,
              'storage_reference': str(source.resolve()), 'sha256': digest,
              'feature_count': len(features), 'download_bytes': total,
              'reference_repairs': repairs, 'method': METHOD, 'meaning': MEANING,
              'attribution': '© Environment Agency copyright and/or database right 2015. Open Government Licence v3.'}
    manifest.write_text(json.dumps(result, indent=2))
    return result


def benchmark_overlap(geometry, snapshot):
    parcel = shape(geometry)
    if not box(*snapshot['bbox']).covers(parcel):
        return {'status': 'unknown', 'overlap_fraction': None, 'reason': 'Outside complete benchmark extract', 'meaning': MEANING}
    content = Path(snapshot['storage_reference']).read_bytes()
    if sha256(content).hexdigest() != snapshot['sha256']:
        raise ValueError('WWNP raw geometry checksum mismatch')
    features = json.loads(content)['features']
    project = Transformer.from_crs(4326, 27700, always_xy=True).transform
    geoms, hit_ids = [], []
    for feature in features:
        g = shape(feature['geometry'])
        if not g.is_valid:
            g = make_valid(g)
        if g.intersects(parcel):
            geoms.append(transform(project, g))
            hit_ids.append(feature['id'])
    projected = transform(project, parcel)
    hit = projected.intersection(unary_union(geoms))
    fraction = max(0, min(1, hit.area / projected.area))
    return {'status': 'mapped_overlap' if fraction > 0 else 'no_mapped_overlap',
            'overlap_fraction': fraction, 'overlap_ha': hit.area / 10000,
            'feature_ids': hit_ids, 'source_sha256': snapshot['sha256'],
            'method': METHOD, 'meaning': MEANING}
