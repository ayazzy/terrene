"""Read-only, organization-scoped discovery of retained successful acquisitions."""
import base64
from datetime import date, datetime, timedelta, timezone
import json
import math
import re
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from shapely.geometry import box, shape
from sqlalchemy import select, and_, or_

from backend import core, acquisition as store
from backend.acquisition_weather import VARIABLES
from backend.acquisition_satellite import BANDS
from backend.acquisition_contracts import Contract, AcquisitionError, digest, encode, parse_request, SOURCE_ADAPTERS

SOURCES = set(SOURCE_ADAPTERS) | {'copernicus.sentinel2_c1_l2a_earthsearch','nasa.power_merra2_daily'}
SCAN_LIMIT = 50
LABELS = {'natural_england.sssi':'Natural England SSSI','naturescot.sssi':'NatureScot SSSI',
          'environment_agency.lidar_dtm_1m':'EA LIDAR terrain',
          'environment_agency.lidar_dsm_last_return_1m':'EA LIDAR last-return surface',
          'copernicus.sentinel2_c1_l2a_earthsearch':'Copernicus Sentinel-2 C1 L2A',
          'nasa.power_merra2_daily':'NASA POWER / MERRA-2 daily weather'}


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone_required')
    return parsed.astimezone(timezone.utc)


class CatalogueQuery(Contract):
    bbox: str | None = Field(default=None,max_length=200)
    source_id: str | None = Field(default=None,max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    time_basis: Literal['evidence','capture'] = 'evidence'
    limit: int = Field(default=10,ge=1,le=20)
    cursor: str | None = Field(default=None,max_length=2000)

    @model_validator(mode='after')
    def valid_query(self):
        if self.source_id is not None and self.source_id not in SOURCES:
            raise ValueError('unsupported_source')
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError('both_dates_required')
        if self.start_date and (self.start_date > self.end_date or self.end_date == date.max):
            raise ValueError('invalid_interval')
        if self.bbox is not None:
            values = self.bounds
            if (len(values) != 4 or not all(math.isfinite(v) for v in values)
                    or not -180 <= values[0] < values[2] <= 180 or not -90 <= values[1] < values[3] <= 90):
                raise ValueError('invalid_bbox')
        return self

    @property
    def bounds(self):
        return [float(v) for v in self.bbox.split(',')] if self.bbox is not None else None

    @property
    def fingerprint(self):
        return digest(encode(self.model_dump(mode='json',exclude={'cursor'})))


class EvidenceTime(Contract):
    kind: Literal['instant','interval','unknown']
    start: str | None = None
    end_exclusive: str | None = None


class AvailableCount(Contract):
    series: str
    measure: Literal['selected_features','valid_cells','present_days']
    present: int = Field(ge=0,strict=True)
    expected: int | None = Field(default=None,ge=0,strict=True)


class ArtifactReference(Contract):
    role: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    bytes: int = Field(ge=0,strict=True)


class CatalogueEntry(Contract):
    acquisition_id: str
    attempt_id: str
    source_id: str
    source_label: str
    adapter_version: str
    family: Literal['vector','raster','satellite','weather_timeseries']
    manifest_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    request_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    geometry_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    requested_geometry: dict
    spatial_semantics: Literal['acquisition_request_area','weather_query_point_not_area_coverage']
    capture_started: str
    capture_completed: str
    evidence_time: EvidenceTime
    counts: list[AvailableCount]
    evidence_semantics: list[str]
    manifest_verified: Literal[True] = True
    artifact_verification: Literal['not_performed','verified']
    artifact_count: int
    artifact_bytes: int
    detail_path: str


class AcquisitionCatalogue(Contract):
    contract_version: Literal['acquisition_catalogue_v1'] = 'acquisition_catalogue_v1'
    query: dict
    entries: list[CatalogueEntry]
    scanned_count: int
    next_cursor: str | None
    scan_complete: bool
    ordering: Literal['request_created_desc_id_desc'] = 'request_created_desc_id_desc'
    limitations: list[str] = [
        'Successful independent acquisitions only; no entry does not establish no evidence or real-world absence.',
        'Location filters intersect requested geometries; counts describe the retained request, not the search window.',
        'Weather query points do not establish surrounding grid or parcel coverage; values are historical coarse reanalysis, not station data or forecasts.',
        'Raster valid cells are availability, not accuracy; spectral availability does not exclude clouds or shadows.',
        'Vector counts are selected mapped features or components, not necessarily distinct designations.',
        'Unknown evidence dates are excluded from evidence-date filters; capture time is never substituted.',
        'Catalogue checks manifests, not artifact bytes; open an exact capture to verify retained artifacts.',
        'Pagination is a bounded live scan, not a database snapshot or a guarantee of complete source coverage.',
    ]


class AcquisitionDetail(Contract):
    contract_version: Literal['acquisition_detail_v1'] = 'acquisition_detail_v1'
    entry: CatalogueEntry
    artifacts: list[ArtifactReference]


def _rows(org, *, after=None):
    r,a = store.requests,store.attempts
    query = select(*r.c,*[c.label('terminal_number' if c.name == 'number' else 'attempt_'+c.name) for c in a.c]).select_from(r.outerjoin(a,
        (a.c.id == r.c.completed_attempt_id) & (a.c.org == r.c.org) & (a.c.acquisition_id == r.c.id)))
    query = query.where(r.c.org == org,r.c.state == 'succeeded')
    if after is not None:
        query = query.where(or_(r.c.created < after[0],and_(r.c.created == after[0],r.c.id < after[1])))
    return query.order_by(r.c.created.desc(),r.c.id.desc()).limit(SCAN_LIMIT+1)


def _manifest(org,row):
    """Verify only the retained request, terminal attempt envelope and manifest."""
    if (digest(encode(row['request'])) != row['request_hash']
            or row['attempt_state'] != 'succeeded'
            or row['attempt_number'] != row['terminal_number']
            or row['attempt_id'] != row['completed_attempt_id']
            or row['attempt_error_code'] is not None):
        raise AcquisitionError('integrity_failure')
    manifest = store._load(org,{'key':row['attempt_manifest_key'],'sha256':row['attempt_manifest_sha256']})
    expected = {'contract_version':'geographic_acquisition_manifest_v1','org':org,
        'acquisition_id':row['id'],'attempt_id':row['completed_attempt_id'],'attempt_number':row['attempt_number'],
        'request':row['request'],'request_hash':row['request_hash'],'state':'succeeded','error_code':None,
        'started':row['attempt_started'],'completed':row['attempt_completed']}
    if any(manifest.get(k) != v for k,v in expected.items()):
        raise AcquisitionError('integrity_failure')
    request = parse_request(row['request'])
    if (manifest.get('geometry_fingerprint') != request.geometry_fingerprint
            or manifest['source']['source_id'] != request.source_id
            or manifest['source']['adapter_version'] != request.adapter_version):
        raise AcquisitionError('integrity_failure')
    for role,ref in manifest['artifacts'].items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,100}',role):
            raise AcquisitionError('integrity_failure')
        ArtifactReference(role=role,sha256=ref['sha256'],bytes=ref['bytes'])
        expected_key = store._object_key(org,ref['sha256'])
        if 'media_type' in ref: expected_key = expected_key.removesuffix('.json')+'.bin'
        if ref['key'] != expected_key or type(ref['bytes']) is not int or ref['bytes'] < 0:
            raise AcquisitionError('integrity_failure')
    if not manifest['artifacts'] or manifest['result'] is None:
        raise AcquisitionError('integrity_failure')
    return manifest,request


def _entry(manifest, request, sha, *, verified=False):
    family = manifest['source']['data_family']
    result = manifest['result']
    expected_family = ('weather_timeseries' if request.source_id == 'nasa.power_merra2_daily' else
                       'satellite' if request.source_id == 'copernicus.sentinel2_c1_l2a_earthsearch' else
                       'raster' if request.source_id.startswith('environment_agency.') else 'vector')
    if family != expected_family or result.get('data_family',family) != family:
        raise AcquisitionError('integrity_failure')
    time = EvidenceTime(kind='unknown')
    counts = []
    if family == 'weather_timeseries':
        start = date.fromisoformat(request.start_date)
        end = date.fromisoformat(request.end_date)+timedelta(days=1)
        time = EvidenceTime(kind='interval',start=start.isoformat()+'T00:00:00+00:00',end_exclusive=end.isoformat()+'T00:00:00+00:00')
        counts = [AvailableCount(series=k,measure='present_days',present=v['present_days'],expected=v['expected_days']) for k in VARIABLES for v in [result['variables'][k]]]
    elif family == 'satellite':
        time = EvidenceTime(kind='instant',start=utc(result['observation_time']).isoformat())
        counts = [AvailableCount(series=k,measure='valid_cells',present=v['valid_cell_count'],expected=v['area_cell_count']) for k in BANDS for v in [result['bands'][k]]]
    elif family == 'raster':
        counts = [AvailableCount(series='elevation',measure='valid_cells',present=result['raster']['valid_cell_count'],expected=result['raster']['area_cell_count'])]
    elif family == 'vector':
        counts = [AvailableCount(series='mapped_features',measure='selected_features',present=result['feature_count'])]
    if any(v.expected is not None and v.present > v.expected for v in counts):
        raise AcquisitionError('integrity_failure')
    if utc(manifest['started']) > utc(manifest['completed']):
        raise AcquisitionError('integrity_failure')
    semantics = {
        'vector': ['Selected mapped features/components are not necessarily distinct designations.',
                   'Mapped absence does not establish real-world absence; evidence dates are unknown.'],
        'raster': ['Historical composite elevation; local survey dates are unknown.',
                   'Valid cells describe availability, not accuracy or current survey coverage.'],
        'satellite': ['Dated native spectral cells and provider scene classification.',
                      'Non-nodata cells can contain clouds or shadows; counts do not establish clear-ground coverage.'],
        'weather_timeseries': ['Historical coarse MERRA-2 reanalysis queried at a point.',
                               'Not station observations, parcel averages, forecasts or climate projections.'],
    }[family] + ['Counts apply to the entire retained request, not the catalogue search window.',
                'Evidence availability is not predictive confidence.']
    acquisition_id = str(UUID(manifest['acquisition_id']))
    attempt_id = str(UUID(manifest['attempt_id']))
    return CatalogueEntry(acquisition_id=acquisition_id,attempt_id=attempt_id,
        source_id=request.source_id,source_label=LABELS[request.source_id],adapter_version=request.adapter_version,
        family=family,manifest_sha256=sha,request_sha256=manifest['request_hash'],geometry_fingerprint=request.geometry_fingerprint,
        requested_geometry=request.point if family == 'weather_timeseries' else request.area,
        spatial_semantics='weather_query_point_not_area_coverage' if family == 'weather_timeseries' else 'acquisition_request_area',
        capture_started=utc(manifest['started']).isoformat(),capture_completed=utc(manifest['completed']).isoformat(),
        evidence_time=time,counts=counts,evidence_semantics=semantics,artifact_verification='verified' if verified else 'not_performed',
        artifact_count=len(manifest['artifacts']),artifact_bytes=sum(ref['bytes'] for ref in manifest['artifacts'].values()),
        detail_path=f'/api/acquisitions/{acquisition_id}?attempt_id={attempt_id}')


def _cursor(org,query,row):
    return base64.urlsafe_b64encode(encode({'v':1,'org':digest(org.encode()),'query':query.fingerprint,
        'after':[row['created'],row['id']]})).decode().rstrip('=')


def _position(org,query):
    if query.cursor is None: return None
    try:
        data=json.loads(base64.b64decode(query.cursor+'='*(-len(query.cursor)%4),altchars=b'-_',validate=True))
        after=data['after']
        if (set(data) != {'v','org','query','after'} or data['v'] != 1 or data['org'] != digest(org.encode())
                or data['query'] != query.fingerprint or not isinstance(after,list) or len(after) != 2):
            raise ValueError('cursor_mismatch')
        utc(after[0]);UUID(after[1])
    except Exception as exc:
        raise AcquisitionError('invalid_catalogue_cursor') from exc
    with core.engine.connect() as c:
        marker=c.execute(select(store.requests.c.id).where(store.requests.c.org == org,
            store.requests.c.id == after[1],store.requests.c.created == after[0],store.requests.c.state == 'succeeded')).first()
    if marker is None:
        raise AcquisitionError('invalid_catalogue_cursor')
    return after


def list_acquisitions(org,query):
    org=store._org(org)
    query=CatalogueQuery.model_validate(query.model_dump() if isinstance(query,CatalogueQuery) else query)
    position=_position(org,query)
    with core.engine.connect() as c: rows=c.execute(_rows(org,after=position)).mappings().all()
    entries=[];scanned=0;last=None
    spatial=box(*query.bounds) if query.bbox else None
    lower=utc(query.start_date.isoformat()+'T00:00:00Z') if query.start_date else None
    upper=utc((query.end_date+timedelta(days=1)).isoformat()+'T00:00:00Z') if query.end_date else None
    for record in rows[:SCAN_LIMIT]:
        row=dict(record)
        scanned+=1;last=row
        manifest,request=_manifest(org,row)
        entry=_entry(manifest,request,row['attempt_manifest_sha256'])
        if query.source_id and entry.source_id != query.source_id: continue
        if spatial is not None and not spatial.intersects(shape(entry.requested_geometry)): continue
        if lower is not None:
            timing=EvidenceTime(kind='instant',start=entry.capture_completed) if query.time_basis == 'capture' else entry.evidence_time
            if timing.kind == 'unknown': continue
            start=utc(timing.start)
            if timing.kind == 'instant':
                if not lower <= start < upper: continue
            elif not (start < upper and utc(timing.end_exclusive) > lower): continue
        entries.append(entry)
        if len(entries) == query.limit: break
    more=scanned < len(rows)
    return AcquisitionCatalogue(query=query.model_dump(mode='json',exclude={'cursor'}),entries=entries,
        scanned_count=scanned,next_cursor=_cursor(org,query,last) if more else None,scan_complete=not more)


def read_acquisition_detail(org,acquisition_id,*,attempt_id):
    org=store._org(org)
    try:
        UUID(acquisition_id);UUID(attempt_id)
    except ValueError as exc:
        raise AcquisitionError('not_found') from exc
    summary=store.read_acquisition(org,acquisition_id,attempt_id=attempt_id)
    if summary['state'] != 'succeeded': raise AcquisitionError('not_found')
    manifest=store._load(org,{'key':store._object_key(org,summary['manifest_sha256']),'sha256':summary['manifest_sha256']})
    request=parse_request(summary['request'])
    if (manifest['source']['source_id'] != request.source_id
            or manifest['source']['adapter_version'] != request.adapter_version):
        raise AcquisitionError('integrity_failure')
    return AcquisitionDetail(entry=_entry(manifest,request,summary['manifest_sha256'],verified=True),
        artifacts=[ArtifactReference(role=key,sha256=ref['sha256'],bytes=ref['bytes']) for key,ref in manifest['artifacts'].items()])
