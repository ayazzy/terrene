import type { Capture } from './acquisitions';

export type TerrainPreview = {
  contract_version: 'terrain_preview_v1';
  preview_fingerprint: string;
  capture: {
    acquisition_id: string;
    attempt_id: string;
    manifest_sha256: string;
    native_raster_sha256: string;
    source_id: string;
    adapter_version: string;
    capture_completed: string;
    observation_time: null;
    attribution: string;
    licence: string;
  };
  requested_geometry: Capture['requested_geometry'];
  native: {
    crs: 'EPSG:27700';
    resolution_m: 1;
    vertical_unit: 'metre';
    vertical_datum: 'Ordnance Datum Newlyn';
    area_cell_count: number;
    valid_cell_count: number;
    missing_cell_count: number;
    nodata_value: number;
    coverage_state: 'complete' | 'partial' | 'no_valid_cells';
  };
  grid: {
    crs: 'EPSG:3857';
    width: number;
    height: number;
    bounds: number[];
    transform: number[];
    coordinates_wgs84: [number, number][];
    coordinate_order: string;
    visible_pixel_count: number;
    transparent_pixel_count: number;
    state: 'visible_samples' | 'no_visible_samples';
  };
  legend: {
    kind: 'linear_grayscale';
    minimum_elevation_m: number | null;
    maximum_elevation_m: number | null;
    low_rgb: number[];
    high_rgb: number[];
    constant_rgb: number[];
    range_basis: string;
    missing_alpha: 0;
    valid_alpha: 255;
  };
  image: {
    media_type: 'image/png';
    encoding: 'base64';
    data: string;
    bytes: number;
    sha256: string;
  };
  rendering: {
    version: string;
    resampling: 'nearest';
    max_edge_pixels: 512;
    display_only: true;
  };
};
const record = (v: unknown): v is Record<string, unknown> =>
  !!v && typeof v === 'object' && !Array.isArray(v);
const sha = (v: unknown) => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const integer = (v: unknown, max: number): v is number =>
  Number.isSafeInteger(v) && (v as number) >= 0 && (v as number) <= max;
const numbers = (v: unknown, length: number): v is number[] =>
  Array.isArray(v) && v.length === length && v.every(Number.isFinite);
const same = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);
const invalid = () =>
  new Error('The terrain preview could not be verified. Retry to check again.');

/** Validate exact selection, placement, legend semantics and the received PNG bytes. */
export async function parseTerrainPreview(
  value: unknown,
  selected: Capture,
): Promise<TerrainPreview> {
  if (!record(value)) throw invalid();
  const {
    capture: c,
    native: n,
    grid: g,
    legend: l,
    image: i,
    rendering: r,
    requested_geometry: geo,
  } = value;
  if (
    !record(c) ||
    !record(n) ||
    !record(g) ||
    !record(l) ||
    !record(i) ||
    !record(r) ||
    !record(geo)
  )
    throw invalid();
  if (
    value.contract_version !== 'terrain_preview_v1' ||
    !sha(value.preview_fingerprint) ||
    selected.source_id !== 'environment_agency.lidar_dtm_1m' ||
    c.source_id !== selected.source_id ||
    c.adapter_version !== 'ea_lidar_dtm_wcs_v1' ||
    c.acquisition_id !== selected.acquisition_id ||
    c.attempt_id !== selected.attempt_id ||
    c.manifest_sha256 !== selected.manifest_sha256 ||
    !sha(c.native_raster_sha256) ||
    c.capture_completed !== selected.capture_completed ||
    c.observation_time !== null ||
    typeof c.attribution !== 'string' ||
    !c.attribution ||
    typeof c.licence !== 'string' ||
    geo.type !== selected.requested_geometry.type ||
    !same(geo.coordinates, selected.requested_geometry.coordinates) ||
    n.crs !== 'EPSG:27700' ||
    n.resolution_m !== 1 ||
    n.vertical_unit !== 'metre' ||
    n.vertical_datum !== 'Ordnance Datum Newlyn' ||
    !Number.isFinite(n.nodata_value) ||
    !integer(n.area_cell_count, 4000000) ||
    !n.area_cell_count ||
    !integer(n.valid_cell_count, n.area_cell_count) ||
    n.missing_cell_count !== n.area_cell_count - n.valid_cell_count ||
    n.coverage_state !==
      (n.valid_cell_count === n.area_cell_count
        ? 'complete'
        : n.valid_cell_count
          ? 'partial'
          : 'no_valid_cells') ||
    g.crs !== 'EPSG:3857' ||
    !integer(g.width, 512) ||
    !g.width ||
    !integer(g.height, 512) ||
    !g.height ||
    !integer(g.visible_pixel_count, g.width * g.height) ||
    g.transparent_pixel_count !== g.width * g.height - g.visible_pixel_count ||
    g.state !==
      (g.visible_pixel_count ? 'visible_samples' : 'no_visible_samples') ||
    !numbers(g.bounds, 4) ||
    !numbers(g.transform, 9) ||
    g.coordinate_order !== 'top_left_top_right_bottom_right_bottom_left' ||
    !Array.isArray(g.coordinates_wgs84) ||
    g.coordinates_wgs84.length !== 4 ||
    !g.coordinates_wgs84.every((p) => numbers(p, 2)) ||
    l.kind !== 'linear_grayscale' ||
    l.range_basis !== 'all_valid_native_cells_inside_request' ||
    !same(l.low_rgb, [32, 32, 32]) ||
    !same(l.high_rgb, [240, 240, 240]) ||
    !same(l.constant_rgb, [128, 128, 128]) ||
    l.missing_alpha !== 0 ||
    l.valid_alpha !== 255 ||
    r.version !== 'ea_dtm_grayscale_web_mercator_v1' ||
    r.resampling !== 'nearest' ||
    r.max_edge_pixels !== 512 ||
    r.display_only !== true ||
    i.media_type !== 'image/png' ||
    i.encoding !== 'base64' ||
    !sha(i.sha256) ||
    !integer(i.bytes, 1100000) ||
    i.bytes < 33 ||
    typeof i.data !== 'string' ||
    i.data.length > 1500000 ||
    !/^[A-Za-z0-9+/]+={0,2}$/.test(i.data)
  )
    throw invalid();
  if (n.valid_cell_count === 0) {
    if (
      l.minimum_elevation_m !== null ||
      l.maximum_elevation_m !== null ||
      g.visible_pixel_count !== 0
    )
      throw invalid();
  } else if (
    typeof l.minimum_elevation_m !== 'number' ||
    typeof l.maximum_elevation_m !== 'number' ||
    !Number.isFinite(l.minimum_elevation_m) ||
    !Number.isFinite(l.maximum_elevation_m) ||
    l.minimum_elevation_m < -500 ||
    l.maximum_elevation_m > 9000 ||
    l.minimum_elevation_m > l.maximum_elevation_m
  )
    throw invalid();
  const [west, south, east, north] = g.bounds,
    t = g.transform;
  const near = (a: number, b: number) => Math.abs(a - b) < 0.000001;
  if (
    !(west < east && south < north) ||
    t[0] <= 0 ||
    t[4] >= 0 ||
    t[1] !== 0 ||
    t[3] !== 0 ||
    !same(t.slice(6), [0, 0, 1]) ||
    !near(t[2], west) ||
    !near(t[5], north) ||
    !near(west + t[0] * g.width, east) ||
    !near(north + t[4] * g.height, south)
  )
    throw invalid();
  for (const [index, [x, y]] of [
    [west, north],
    [east, north],
    [east, south],
    [west, south],
  ].entries()) {
    const [lon, lat] = g.coordinates_wgs84[index] as number[];
    if (
      Math.abs(lon) > 180 ||
      Math.abs(lat) > 85.051129 ||
      !near(lon, ((x / 6378137) * 180) / Math.PI) ||
      !near(
        lat,
        ((2 * Math.atan(Math.exp(y / 6378137)) - Math.PI / 2) * 180) / Math.PI,
      )
    )
      throw invalid();
  }
  let bytes: Uint8Array<ArrayBuffer>;
  try {
    bytes = Uint8Array.from(atob(i.data), (ch) => ch.charCodeAt(0));
  } catch {
    throw invalid();
  }
  if (
    bytes.length !== i.bytes ||
    !same(Array.from(bytes.slice(0, 8)), [137, 80, 78, 71, 13, 10, 26, 10])
  )
    throw invalid();
  const header = new DataView(bytes.buffer);
  if (
    header.getUint32(8) !== 13 ||
    header.getUint32(12) !== 0x49484452 ||
    header.getUint32(16) !== g.width ||
    header.getUint32(20) !== g.height ||
    bytes[24] !== 8 ||
    bytes[25] !== 6
  )
    throw invalid();
  const hash = Array.from(
    new Uint8Array(await crypto.subtle.digest('SHA-256', bytes.buffer)),
    (v) => v.toString(16).padStart(2, '0'),
  ).join('');
  if (hash !== i.sha256) throw invalid();
  return value as unknown as TerrainPreview;
}

export async function readTerrainPreview(
  selected: Capture,
  signal: AbortSignal,
) {
  const token = sessionStorage.getItem('crc-token');
  const checkSession = () => {
    if (token !== sessionStorage.getItem('crc-token'))
      throw Object.assign(new Error('Your session changed. Search again.'), {
        status: 401,
      });
  };
  const response = await fetch(
    `/api/acquisitions/${encodeURIComponent(selected.acquisition_id)}/terrain-preview?attempt_id=${encodeURIComponent(selected.attempt_id)}`,
    {
      method: 'GET',
      cache: 'no-store',
      signal,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    },
  );
  checkSession();
  if (!response.ok)
    throw Object.assign(
      new Error(
        response.status === 401 || response.status === 403
          ? 'Sign in with an organization account to view terrain.'
          : 'Terrain could not be verified or the service is unavailable. Retry to check again.',
      ),
      { status: response.status },
    );
  const result = await parseTerrainPreview(await response.json(), selected);
  checkSession();
  return result;
}
