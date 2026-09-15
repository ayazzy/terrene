"""Trusted operator service/CLI for independent immutable geographic acquisitions.

Only operational claims are mutable. Completed attempts and their evidence are
append-only. Nothing here writes Sites, assessments, datasets or model runs.
"""
import argparse
import json
from pathlib import Path
import time
import uuid

import pyproj
import shapely
from pydantic import ValidationError
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from backend import core
from backend.acquisition_contracts import (
    AcquisitionError, AcquisitionRequest, BinaryArtifact, digest, encode,
    MAX_REQUEST_BYTES, SCOTLAND_ADAPTER_VERSION, RASTER_ADAPTERS, parse_request,
)
from backend.acquisition_sources import (
    ADAPTER_COVERAGE, source_descriptor, fetch_sssi, prepare_coverage, validate_capabilities, load_coverage,
)

requests = core.geographic_acquisitions
attempts = core.geographic_acquisition_attempts
LEASE_SECONDS = 600


def _org(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise AcquisitionError('invalid_organization')
    return value


def _object_key(org, sha):
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise AcquisitionError('integrity_failure')
    return f'geographic-acquisition/{digest(org.encode())}/objects/{sha}.json'


def _store(org, value):
    if isinstance(value, BinaryArtifact):
        if value.media_type not in ('image/tiff', 'application/xml', 'application/octet-stream'):
            raise AcquisitionError('unsupported_artifact_type')
        data = value.content
        sha = digest(data)
        key = _object_key(org, sha).removesuffix('.json') + '.bin'
        core.store_object_immutable(key, data)
        return {'key': key, 'sha256': sha, 'bytes': len(data), 'media_type': value.media_type}
    data = encode(value)
    sha = digest(data)
    key = _object_key(org, sha)
    core.store_object_immutable(key, data)
    return {'key': key, 'sha256': sha, 'bytes': len(data)}


def _load(org, reference):
    try:
        key = _object_key(org, reference['sha256'])
        binary = 'media_type' in reference
        if binary:
            if reference['media_type'] not in ('image/tiff', 'application/xml', 'application/octet-stream'):
                raise AcquisitionError('integrity_failure')
            key = key.removesuffix('.json') + '.bin'
        if reference['key'] != key:
            raise AcquisitionError('integrity_failure')
        data = core.load_object(reference['key'])
        if data is None or digest(data) != reference['sha256']:
            raise AcquisitionError('integrity_failure')
        if 'bytes' in reference and len(data) != reference['bytes']:
            raise AcquisitionError('integrity_failure')
        return data if binary else json.loads(data)
    except AcquisitionError:
        raise
    except Exception as exc:
        raise AcquisitionError('integrity_failure') from exc


def _register(org, request):
    payload = request.model_dump()
    sha = digest(encode(payload))
    try:
        with core.engine.begin() as connection:
            connection.execute(insert(requests).values(
                id=str(uuid.uuid4()), org=org, idempotency_key=request.idempotency_key,
                request_hash=sha, request=payload, created=core.now(), attempt_number=0, state='pending',
            ))
    except IntegrityError:
        pass  # Concurrent insert or retry: resolve only within this organization.
    with core.engine.connect() as connection:
        row = connection.execute(select(requests).where(
            requests.c.org == org, requests.c.idempotency_key == request.idempotency_key,
        )).mappings().one()
    if row['request_hash'] != sha:
        raise AcquisitionError('idempotency_conflict')
    return dict(row)


def _claim(row):
    now = time.time()
    if row['state'] == 'succeeded':
        return None
    if row['state'] == 'running' and row['lease'] > now:
        raise AcquisitionError('acquisition_in_progress')
    token = str(uuid.uuid4())
    number = row['attempt_number'] + 1
    attempt_id = str(uuid.uuid4())
    started = core.now()
    with core.engine.begin() as connection:
        result = connection.execute(update(requests).where(
            requests.c.id == row['id'], requests.c.org == row['org'],
            requests.c.attempt_number == row['attempt_number'], requests.c.state == row['state'],
        ).values(state='running', token=token, lease=now + LEASE_SECONDS, attempt_number=number))
        if result.rowcount != 1:
            raise AcquisitionError('acquisition_in_progress')
        if row['state'] == 'running':
            # An interrupted attempt never becomes evidence; retain its terminal reason.
            connection.execute(update(attempts).where(
                attempts.c.acquisition_id == row['id'], attempts.c.org == row['org'],
                attempts.c.number == row['attempt_number'], attempts.c.state == 'running',
            ).values(state='failed', error_code='interrupted', completed=started))
        connection.execute(insert(attempts).values(
            id=attempt_id, org=row['org'], acquisition_id=row['id'], number=number,
            started=started, state='running',
        ))
    return {'id': attempt_id, 'number': number, 'started': started, 'token': token}


def _finish(row, claim, state, error_code, completed, reference):
    with core.engine.begin() as connection:
        result = connection.execute(update(requests).where(
            requests.c.id == row['id'], requests.c.org == row['org'],
            requests.c.token == claim['token'], requests.c.state == 'running',
            requests.c.lease > time.time(),
        ).values(state=state, token=None, lease=None, completed_attempt_id=claim['id']))
        if result.rowcount != 1:
            raise AcquisitionError('claim_lost')
        result = connection.execute(update(attempts).where(
            attempts.c.id == claim['id'], attempts.c.org == row['org'], attempts.c.state == 'running',
        ).values(state=state, error_code=error_code, completed=completed,
                 manifest_key=reference['key'] if reference else None,
                 manifest_sha256=reference['sha256'] if reference else None))
        if result.rowcount != 1:
            raise AcquisitionError('integrity_failure')


def acquire(org: str, request: AcquisitionRequest | dict, *, client=None) -> dict:
    org = _org(org)
    # Revalidate even an existing model: frozen models still contain mutable dictionaries.
    request = parse_request(request)
    row = _register(org, request)
    claim = _claim(row)
    if claim is None:
        return read_acquisition(org, row['id'])
    artifacts, diagnostics, result = {}, {}, None
    state, error_code = 'succeeded', None
    try:
        if request.contract_version == 'geographic_satellite_request_v1':
            from backend.acquisition_satellite import fetch_satellite
            result = fetch_satellite(request, client=client, artifacts=artifacts, diagnostics=diagnostics)
        elif request.contract_version == 'geographic_weather_request_v1':
            from backend.acquisition_weather import fetch_weather
            result = fetch_weather(request, client=client, artifacts=artifacts, diagnostics=diagnostics)
        else:
            validate_capabilities(request)
        if request.adapter_version in RASTER_ADAPTERS:
            from backend.acquisition_rasters import fetch_raster
            result = fetch_raster(request, client=client, artifacts=artifacts, diagnostics=diagnostics)
        elif request.contract_version not in ('geographic_satellite_request_v1', 'geographic_weather_request_v1'):
            result = fetch_sssi(request, client=client, artifacts=artifacts, diagnostics=diagnostics)
    except AcquisitionError as exc:
        state, error_code = 'failed', exc.code
    except Exception:
        # Provider/geometry surprises are retained as failure, never as empty evidence.
        state, error_code = 'failed', 'processing_failure'
    completed = core.now()
    manifest = {
        'contract_version': 'geographic_acquisition_manifest_v1',
        'acquisition_id': row['id'], 'attempt_id': claim['id'], 'attempt_number': claim['number'],
        'org': org, 'request': request.model_dump(), 'request_hash': row['request_hash'],
        'geometry_fingerprint': request.geometry_fingerprint,
        'started': claim['started'], 'completed': completed, 'state': state, 'error_code': error_code,
        'source': source_descriptor(request.adapter_version), 'result': result, 'diagnostics': diagnostics,
        'processing': {'shapely': shapely.__version__, 'pyproj': pyproj.__version__,
                       'normalization_version': source_descriptor(request.adapter_version).get('normalization_version', 'sssi_polygon_selection_v1'),
                       'area_method': 'WGS84 ellipsoid geodesic area',
                       'artifact_hash_semantics': 'Canonical assembled JSON; response hashes are decoded HTTP bytes.'},
        'artifacts': {},
    }
    if request.contract_version == 'geographic_weather_request_v1':
        manifest['processing'].update(area_method='Not applicable: explicit WGS84 point query.',
            artifact_hash_semantics='Provider responses hash original decoded HTTP bytes; normalized metadata and daily series use canonical JSON.')
    if request.adapter_version in RASTER_ADAPTERS or request.contract_version == 'geographic_satellite_request_v1':
        import rasterio
        manifest['processing'].update(
            rasterio=rasterio.__version__, gdal=rasterio.__gdal_version__,
            artifact_hash_semantics='XML/GeoTIFF hashes cover original decoded HTTP bytes; JSON uses canonical encoding.',
        )
        if request.contract_version == 'geographic_satellite_request_v1':
            manifest['processing']['artifact_hash_semantics'] = (
                'Source ranges hash original HTTP bytes; window GeoTIFFs hash lossless derived native subsets; '
                'metadata and coverage use canonical JSON. Whole remote file checksums are unverified.')
    try:
        for name, value in artifacts.items():
            manifest['artifacts'][name] = _store(org, value)
        reference = _store(org, manifest)
    except Exception:
        # If storage itself is unavailable, retain a database-only diagnostic. No success is published.
        _finish(row, claim, 'failed', 'storage_failure', completed, None)
    else:
        _finish(row, claim, state, error_code, completed, reference)
    return read_acquisition(org, row['id'], attempt_id=claim['id'])


def read_acquisition(org: str, acquisition_id: str, *, attempt_id: str | None = None) -> dict:
    """Verify exact retained objects, then return a summary with no private keys.

    Use attempt_id to inspect historical failures after an eventual successful retry.
    No network request, fallback to another capture, or evidence writes are made.
    """
    org = _org(org)
    # One statement observes one database snapshot, including under PostgreSQL's
    # READ COMMITTED isolation. Separate request/history queries can straddle a
    # legitimate retry and falsely report corruption.
    with core.engine.connect() as connection:
        rows = connection.execute(select(
            *requests.c, *[column.label('history_' + column.name) for column in attempts.c],
        ).select_from(requests.outerjoin(attempts,
            (attempts.c.acquisition_id == requests.c.id) & (attempts.c.org == requests.c.org),
        )).where(
            requests.c.id == acquisition_id, requests.c.org == org,
        ).order_by(attempts.c.number)).mappings().all()
        if not rows:
            raise AcquisitionError('not_found')
        row = {column.name: rows[0][column.name] for column in requests.c}
        history = [{column.name: record['history_' + column.name] for column in attempts.c}
                   for record in rows if record['history_id'] is not None]
    if digest(encode(row['request'])) != row['request_hash']:
        raise AcquisitionError('integrity_failure')
    if len(history) != row['attempt_number'] or [a['number'] for a in history] != list(range(1, len(history) + 1)):
        raise AcquisitionError('integrity_failure')
    if row['state'] in ('succeeded', 'failed') and (
        not history or history[-1]['id'] != row['completed_attempt_id'] or history[-1]['state'] != row['state']
    ):
        raise AcquisitionError('integrity_failure')
    selected = attempt_id or row['completed_attempt_id']
    attempt = next((a for a in history if a['id'] == selected), None)
    if attempt_id and attempt is None:
        raise AcquisitionError('not_found')
    # During a retry do not present an old completed attempt as the current outcome.
    if attempt_id is None and row['state'] == 'running':
        attempt = history[-1] if history else None
    manifest, references = None, {}
    if attempt and attempt['manifest_key']:
        manifest = _load(org, {'key': attempt['manifest_key'], 'sha256': attempt['manifest_sha256']})
        expected = {'contract_version': 'geographic_acquisition_manifest_v1',
                    'org': org, 'acquisition_id': acquisition_id, 'attempt_id': attempt['id'],
                    'attempt_number': attempt['number'], 'request_hash': row['request_hash'],
                    'request': row['request'], 'started': attempt['started'],
                    'completed': attempt['completed'], 'state': attempt['state'], 'error_code': attempt['error_code']}
        if any(manifest.get(k) != v for k, v in expected.items()):
            raise AcquisitionError('integrity_failure')
        request = parse_request(manifest['request'])
        if manifest.get('geometry_fingerprint') != request.geometry_fingerprint:
            raise AcquisitionError('integrity_failure')
        for name, ref in manifest['artifacts'].items():
            _load(org, ref)
            references[name] = {k: ref[k] for k in ('sha256', 'bytes')}
            if 'media_type' in ref:
                references[name]['media_type'] = ref['media_type']
        if attempt['state'] == 'succeeded':
            required = {'provider_metadata_before', 'provider_metadata_after', 'assembled_provider_candidates',
                        'normalized_selection', 'normalization_lineage'}
            if request.adapter_version == SCOTLAND_ADAPTER_VERSION:
                required |= {'provider_item_before', 'provider_item_after'}
            if request.adapter_version in RASTER_ADAPTERS:
                required = {'provider_description_before', 'provider_description_after', 'native_raster', 'raster_coverage'}
                for name, kind in [('native_raster', 'image/tiff'), ('provider_description_before', 'application/xml'),
                                   ('provider_description_after', 'application/xml')]:
                    if references.get(name, {}).get('media_type') != kind:
                        raise AcquisitionError('integrity_failure')
                coverage_ref = manifest['artifacts'].get('raster_coverage', {})
                if 'media_type' in coverage_ref or _load(org, coverage_ref) != (manifest['result'] or {}).get('raster'):
                    raise AcquisitionError('integrity_failure')
            if request.contract_version == 'geographic_satellite_request_v1':
                from backend.acquisition_satellite import validate_retained
                required = validate_retained(request, manifest, references, lambda ref: _load(org, ref))
            if request.contract_version == 'geographic_weather_request_v1':
                from backend.acquisition_weather import validate_retained
                required = validate_retained(request, manifest, references, lambda ref: _load(org, ref))
            if set(references) != required or manifest['result'] is None or attempt['error_code'] is not None:
                raise AcquisitionError('integrity_failure')
            if request.contract_version not in ('geographic_satellite_request_v1', 'geographic_weather_request_v1'):
                load_coverage(request.coverage_profile_sha256,
                              expected_version=ADAPTER_COVERAGE[request.adapter_version])
    elif attempt and attempt['state'] == 'succeeded':
        raise AcquisitionError('integrity_failure')
    return {
        'contract_version': 'geographic_acquisition_summary_v1', 'acquisition_id': acquisition_id,
        'attempt_id': attempt['id'] if attempt else None,
        'state': attempt['state'] if attempt else row['state'],
        'error_code': attempt['error_code'] if attempt else None,
        'request': row['request'], 'request_hash': row['request_hash'],
        'source': manifest['source'] if manifest else None,
        'result': manifest['result'] if manifest else None,
        'started': attempt['started'] if attempt else None,
        'completed': attempt['completed'] if attempt else None,
        'manifest_sha256': attempt['manifest_sha256'] if attempt else None,
        'artifact_checksums': references,
        'attempts': [{k: a[k] for k in ('id', 'number', 'state', 'error_code', 'started', 'completed')}
                     for a in history],
    }


def read_acquisition_artifact(org, acquisition_id, name, *, attempt_id=None):
    """Trusted internal read of an exact checked artifact; never follows a caller URL."""
    summary = read_acquisition(org, acquisition_id, attempt_id=attempt_id)
    if name not in summary['artifact_checksums']:
        raise AcquisitionError('artifact_not_found')
    manifest = _load(org, {'key': _object_key(org, summary['manifest_sha256']),
                           'sha256': summary['manifest_sha256']})
    return _load(org, manifest['artifacts'][name])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('sources', 'prepare-coverage'):
        command = commands.add_parser(name)
        command.add_argument('--adapter-version', choices=list(ADAPTER_COVERAGE) + (['sentinel2_c1_native_window_v1', 'nasa_power_daily_point_v1'] if name == 'sources' else []), default='sssi_arcgis_v1')
    search = commands.add_parser('discover-satellite')
    search.add_argument('--area', required=True, type=Path)
    search.add_argument('--start', required=True)
    search.add_argument('--end', required=True)
    collect = commands.add_parser('acquire')
    collect.add_argument('--org', required=True)
    collect.add_argument('--request', required=True, type=Path)
    read = commands.add_parser('read')
    read.add_argument('--org', required=True)
    read.add_argument('--id', required=True)
    read.add_argument('--attempt-id')
    pair = commands.add_parser('pair-lidar')
    pair.add_argument('--org', required=True)
    pair.add_argument('--dtm-id', required=True)
    pair.add_argument('--dsm-id', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'sources':
            result = source_descriptor(args.adapter_version)
        elif args.command == 'prepare-coverage':
            result = prepare_coverage(adapter_version=args.adapter_version)
        elif args.command == 'discover-satellite':
            from backend.acquisition_satellite import discover
            with args.area.open('rb') as handle:
                data = handle.read(MAX_REQUEST_BYTES + 1)
            if len(data) > MAX_REQUEST_BYTES:
                raise AcquisitionError('request_payload_limit')
            result = discover(json.loads(data), {'mode':'interval','start':args.start,'end':args.end})
        elif args.command == 'acquire':
            with args.request.open('rb') as handle:
                data = handle.read(MAX_REQUEST_BYTES + 1)
            if len(data) > MAX_REQUEST_BYTES:
                raise AcquisitionError('request_payload_limit')
            result = acquire(args.org, parse_request(json.loads(data)))
        elif args.command == 'pair-lidar':
            from backend.lidar_pairing import read_lidar_pair
            result = read_lidar_pair(args.org, dtm_acquisition_id=args.dtm_id, dsm_acquisition_id=args.dsm_id)
        else:
            result = read_acquisition(args.org, args.id, attempt_id=args.attempt_id)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result.get('state') == 'failed' else 0
    except AcquisitionError as exc:
        print(json.dumps({'error_code': exc.code}))
    except (ValidationError, ValueError):
        print(json.dumps({'error_code': 'invalid_request'}))
    except Exception:
        print(json.dumps({'error_code': 'operator_failure'}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
