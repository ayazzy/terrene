/** Read-only projections of acquisition_catalogue_v1 / acquisition_detail_v1. */
export const acquisitionSources = [
  ['natural_england.sssi', 'Natural England SSSI'],
  ['naturescot.sssi', 'NatureScot SSSI'],
  ['environment_agency.lidar_dtm_1m', 'EA LIDAR terrain'],
  ['environment_agency.lidar_dsm_last_return_1m', 'EA LIDAR surface'],
  ['copernicus.sentinel2_c1_l2a_earthsearch', 'Sentinel-2 imagery'],
  ['nasa.power_merra2_daily', 'Historical weather'],
] as const;

export type CaptureQuery = {
  source_id?: string;
  bbox?: string;
  start_date?: string;
  end_date?: string;
  time_basis: 'evidence' | 'capture';
  limit: number;
};
export const defaultCaptureQuery: CaptureQuery = {
  time_basis: 'evidence',
  limit: 10,
};
export type Capture = {
  acquisition_id: string;
  attempt_id: string;
  source_id: string;
  source_label: string;
  adapter_version: string;
  family: 'vector' | 'raster' | 'satellite' | 'weather_timeseries';
  manifest_sha256: string;
  request_sha256: string;
  geometry_fingerprint: string;
  requested_geometry: {
    type: 'Point' | 'Polygon' | 'MultiPolygon';
    coordinates: unknown[];
  };
  spatial_semantics:
    | 'acquisition_request_area'
    | 'weather_query_point_not_area_coverage';
  capture_started: string;
  capture_completed: string;
  evidence_time: {
    kind: 'unknown' | 'instant' | 'interval';
    start: string | null;
    end_exclusive: string | null;
  };
  counts: {
    series: string;
    measure: 'selected_features' | 'valid_cells' | 'present_days';
    present: number;
    expected: number | null;
  }[];
  evidence_semantics: string[];
  manifest_verified: true;
  artifact_verification: 'not_performed' | 'verified';
  artifact_count: number;
  artifact_bytes: number;
};
export type CaptureCatalogue = {
  contract_version: 'acquisition_catalogue_v1';
  query: {
    bbox: string | null;
    source_id: string | null;
    start_date: string | null;
    end_date: string | null;
    time_basis: 'evidence' | 'capture';
    limit: number;
  };
  entries: Capture[];
  scanned_count: number;
  next_cursor: string | null;
  scan_complete: boolean;
  ordering: 'request_created_desc_id_desc';
  limitations: string[];
};
export type CaptureDetail = {
  contract_version: 'acquisition_detail_v1';
  entry: Capture;
  artifacts: { role: string; sha256: string; bytes: number }[];
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const sha = /^[0-9a-f]{64}$/;
const count = (v: unknown): v is number =>
  Number.isSafeInteger(v) && (v as number) >= 0;
const record = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === 'object' && !Array.isArray(v);
const strings = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every((s) => typeof s === 'string');
const instant = (v: unknown): v is string =>
  typeof v === 'string' &&
  /(?:Z|[+-]\d\d:\d\d)$/.test(v) &&
  Number.isFinite(Date.parse(v));

export function captureBounds(
  geometry: Capture['requested_geometry'],
): number[] {
  const points: number[][] = [];
  function walk(value: unknown) {
    if (!Array.isArray(value) || !value.length)
      throw new Error('Invalid capture location.');
    if (typeof value[0] === 'number') {
      if (
        value.length !== 2 ||
        !value.every(Number.isFinite) ||
        Math.abs(value[0]) > 180 ||
        Math.abs(value[1]) > 90
      )
        throw new Error('Invalid capture location.');
      points.push(value);
    } else value.forEach(walk);
  }
  walk(geometry.coordinates);
  return points.reduce(
    (b, [x, y]) => [
      Math.min(b[0], x),
      Math.min(b[1], y),
      Math.max(b[2], x),
      Math.max(b[3], y),
    ],
    [Infinity, Infinity, -Infinity, -Infinity],
  );
}
function isCapture(value: unknown, verified: boolean): value is Capture {
  if (!record(value)) return false;
  const time = value.evidence_time,
    geometry = value.requested_geometry;
  if (
    !(
      typeof value.acquisition_id === 'string' &&
      uuid.test(value.acquisition_id) &&
      typeof value.attempt_id === 'string' &&
      uuid.test(value.attempt_id) &&
      [
        value.manifest_sha256,
        value.request_sha256,
        value.geometry_fingerprint,
      ].every((v) => typeof v === 'string' && sha.test(v)) &&
      acquisitionSources.some(([id]) => id === value.source_id) &&
      typeof value.source_label === 'string' &&
      typeof value.adapter_version === 'string' &&
      ['vector', 'raster', 'satellite', 'weather_timeseries'].includes(
        String(value.family),
      ) &&
      value.manifest_verified === true &&
      value.artifact_verification ===
        (verified ? 'verified' : 'not_performed') &&
      instant(value.capture_started) &&
      instant(value.capture_completed) &&
      strings(value.evidence_semantics) &&
      count(value.artifact_count) &&
      count(value.artifact_bytes) &&
      record(time) &&
      record(geometry) &&
      ['Point', 'Polygon', 'MultiPolygon'].includes(String(geometry.type)) &&
      Array.isArray(geometry.coordinates) &&
      Array.isArray(value.counts) &&
      value.counts.every(
        (c) =>
          record(c) &&
          typeof c.series === 'string' &&
          ['selected_features', 'valid_cells', 'present_days'].includes(
            String(c.measure),
          ) &&
          count(c.present) &&
          (c.expected === null ||
            (count(c.expected) && c.present <= c.expected)),
      )
    )
  )
    return false;
  const weather = value.family === 'weather_timeseries';
  if (
    weather !== (geometry.type === 'Point') ||
    value.spatial_semantics !==
      (weather
        ? 'weather_query_point_not_area_coverage'
        : 'acquisition_request_area')
  )
    return false;
  if (time.kind === 'unknown') {
    if (time.start !== null || time.end_exclusive !== null) return false;
  } else if (time.kind === 'instant') {
    if (!instant(time.start) || time.end_exclusive !== null) return false;
  } else if (time.kind === 'interval') {
    if (
      !instant(time.start) ||
      !instant(time.end_exclusive) ||
      Date.parse(time.start) >= Date.parse(time.end_exclusive)
    )
      return false;
  } else return false;
  if (
    (weather && time.kind !== 'interval') ||
    (value.family === 'satellite' && time.kind !== 'instant') ||
    (['vector', 'raster'].includes(String(value.family)) &&
      time.kind !== 'unknown')
  )
    return false;
  try {
    captureBounds(geometry as Capture['requested_geometry']);
  } catch {
    return false;
  }
  return true;
}
export function parseCaptureCatalogue(
  value: unknown,
  query: CaptureQuery,
): CaptureCatalogue {
  if (
    !record(value) ||
    value.contract_version !== 'acquisition_catalogue_v1' ||
    !record(value.query) ||
    Object.keys({
      ...query,
      bbox: null,
      source_id: null,
      start_date: null,
      end_date: null,
    }).some(
      (key) =>
        (value.query as Record<string, unknown>)[key] !==
        (query[key as keyof CaptureQuery] ?? null),
    ) ||
    !Array.isArray(value.entries) ||
    value.entries.length > query.limit ||
    !value.entries.every((e) => isCapture(e, false)) ||
    new Set(value.entries.map((e) => e.acquisition_id)).size !==
      value.entries.length ||
    !count(value.scanned_count) ||
    value.scanned_count > 50 ||
    value.scanned_count < value.entries.length ||
    typeof value.scan_complete !== 'boolean' ||
    (value.scan_complete
      ? value.next_cursor !== null
      : typeof value.next_cursor !== 'string' ||
        !value.next_cursor ||
        value.next_cursor.length > 2000) ||
    value.ordering !== 'request_created_desc_id_desc' ||
    !strings(value.limitations)
  )
    throw new Error(
      'The capture catalogue could not be read safely. Retry the search.',
    );
  return value as CaptureCatalogue;
}
export function parseCaptureDetail(
  value: unknown,
  selected: Capture,
): CaptureDetail {
  if (
    !record(value) ||
    value.contract_version !== 'acquisition_detail_v1' ||
    !isCapture(value.entry, true) ||
    (
      [
        'acquisition_id',
        'attempt_id',
        'manifest_sha256',
        'request_sha256',
        'geometry_fingerprint',
        'source_id',
        'adapter_version',
      ] as const
    ).some(
      (key) => value.entry && (value.entry as Capture)[key] !== selected[key],
    ) ||
    !Array.isArray(value.artifacts) ||
    value.artifacts.length !== value.entry.artifact_count ||
    !value.artifacts.every(
      (a) =>
        record(a) &&
        typeof a.role === 'string' &&
        typeof a.sha256 === 'string' &&
        sha.test(a.sha256) &&
        count(a.bytes),
    ) ||
    value.artifacts.reduce((n, a) => n + a.bytes, 0) !==
      value.entry.artifact_bytes
  )
    throw new Error('The returned detail does not match the selected capture.');
  return value as CaptureDetail;
}
export function captureQueryParams(query: CaptureQuery, cursor?: string) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query))
    if (value !== undefined && value !== '') params.set(key, String(value));
  if (cursor) params.set('cursor', cursor);
  return params;
}
async function read(path: string, signal: AbortSignal) {
  const token = sessionStorage.getItem('crc-token');
  const response = await fetch(path, {
    method: 'GET',
    cache: 'no-store',
    signal,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (token !== sessionStorage.getItem('crc-token'))
    throw Object.assign(new Error('Your session changed. Search again.'), {
      status: 401,
    });
  if (!response.ok) {
    const message =
      response.status === 401 || response.status === 403
        ? 'Sign in with an organization account to view retained captures.'
        : response.status === 404
          ? 'This capture is no longer accessible.'
          : response.status === 422
            ? 'The search or continuation is invalid. Start a new search.'
            : 'Retained evidence could not be verified or the service is unavailable. Retry to check again.';
    throw Object.assign(new Error(message), { status: response.status });
  }
  const data: unknown = await response.json();
  if (token !== sessionStorage.getItem('crc-token'))
    throw Object.assign(new Error('Your session changed. Search again.'), {
      status: 401,
    });
  return data;
}
export async function readCaptureCatalogue(
  query: CaptureQuery,
  cursor: string | undefined,
  signal: AbortSignal,
) {
  return parseCaptureCatalogue(
    await read(
      '/api/acquisitions?' + captureQueryParams(query, cursor),
      signal,
    ),
    query,
  );
}
export async function readCaptureDetail(
  selected: Capture,
  signal: AbortSignal,
) {
  return parseCaptureDetail(
    await read(
      `/api/acquisitions/${encodeURIComponent(selected.acquisition_id)}?attempt_id=${encodeURIComponent(selected.attempt_id)}`,
      signal,
    ),
    selected,
  );
}
export function evidenceDateLabel(entry: Capture) {
  const time = entry.evidence_time;
  if (time.kind === 'unknown') return 'Evidence date unknown';
  const format = (value: string) =>
    new Intl.DateTimeFormat('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(new Date(value));
  if (time.kind === 'instant') return format(time.start!);
  return `${format(time.start!)} – ${format(new Date(Date.parse(time.end_exclusive!) - 86400000).toISOString())}`;
}
