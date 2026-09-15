import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import {
  parseTerrainPreview,
  readTerrainPreview,
} from '../app/terrain-preview.ts';
import { createTerrainLayer } from '../app/terrain-layer-state.ts';
import { mountTerrainSource } from '../app/terrain-map-source.ts';

const capture = (id = '00000000-0000-4000-8000-000000000001') => ({
  acquisition_id: id,
  attempt_id: '10000000-0000-4000-8000-000000000001',
  manifest_sha256: 'a'.repeat(64),
  source_id: 'environment_agency.lidar_dtm_1m',
  capture_completed: '2026-09-15T12:00:00Z',
  requested_geometry: {
    type: 'Polygon',
    coordinates: [
      [
        [-1.3, 51.7],
        [-1.2, 51.7],
        [-1.2, 51.8],
        [-1.3, 51.8],
        [-1.3, 51.7],
      ],
    ],
  },
});
const png =
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAGUlEQVR42mNQUFD4/+HDh/8MDQ0N/xmAAABPNQeuyWgmyAAAAABJRU5ErkJggg==';
const coordinates = ([x, y]) => [
  ((x / 6378137) * 180) / Math.PI,
  ((2 * Math.atan(Math.exp(y / 6378137)) - Math.PI / 2) * 180) / Math.PI,
];
const fixture = (c = capture()) => ({
  contract_version: 'terrain_preview_v1',
  preview_fingerprint: 'b'.repeat(64),
  capture: {
    ...c,
    native_raster_sha256: 'c'.repeat(64),
    adapter_version: 'ea_lidar_dtm_wcs_v1',
    observation_time: null,
    attribution: '© Environment Agency',
    licence: 'Open Government Licence',
  },
  requested_geometry: c.requested_geometry,
  native: {
    crs: 'EPSG:27700',
    resolution_m: 1,
    vertical_unit: 'metre',
    vertical_datum: 'Ordnance Datum Newlyn',
    area_cell_count: 4,
    valid_cell_count: 3,
    missing_cell_count: 1,
    nodata_value: -9999,
    coverage_state: 'partial',
  },
  grid: {
    crs: 'EPSG:3857',
    width: 2,
    height: 2,
    bounds: [-140002, 6750000, -140000, 6750002],
    transform: [1, 0, -140002, 0, -1, 6750002, 0, 0, 1],
    coordinates_wgs84: [
      [-140002, 6750002],
      [-140000, 6750002],
      [-140000, 6750000],
      [-140002, 6750000],
    ].map(coordinates),
    coordinate_order: 'top_left_top_right_bottom_right_bottom_left',
    visible_pixel_count: 3,
    transparent_pixel_count: 1,
    state: 'visible_samples',
  },
  legend: {
    kind: 'linear_grayscale',
    minimum_elevation_m: 0,
    maximum_elevation_m: 10,
    low_rgb: [32, 32, 32],
    high_rgb: [240, 240, 240],
    constant_rgb: [128, 128, 128],
    range_basis: 'all_valid_native_cells_inside_request',
    missing_alpha: 0,
    valid_alpha: 255,
  },
  rendering: {
    version: 'ea_dtm_grayscale_web_mercator_v1',
    resampling: 'nearest',
    max_edge_pixels: 512,
    display_only: true,
  },
  image: {
    media_type: 'image/png',
    encoding: 'base64',
    data: png,
    bytes: Buffer.from(png, 'base64').length,
    sha256: createHash('sha256')
      .update(Buffer.from(png, 'base64'))
      .digest('hex'),
  },
});
const query = {
  source_id: 'environment_agency.lidar_dtm_1m',
  time_basis: 'capture',
  limit: 10,
};
const page = (entries = [], next = null) => ({
  entries,
  next_cursor: next,
  scan_complete: next === null,
});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};

test('terrain parser binds image bytes, placement and native legend to exact capture', async () => {
  const f = fixture();
  assert.deepEqual(await parseTerrainPreview(f, capture()), f);
  for (const mutate of [
    (v) => (v.capture.attempt_id = 'wrong'),
    (v) => (v.capture.manifest_sha256 = 'd'.repeat(64)),
    (v) =>
      (v.capture.source_id = 'environment_agency.lidar_dsm_last_return_1m'),
    (v) => (v.native.vertical_unit = 'cm'),
    (v) => (v.native.missing_cell_count = 0),
    (v) => (v.grid.width = 513),
    (v) => v.grid.coordinates_wgs84.reverse(),
    (v) => (v.grid.transform[4] = 1),
    (v) => (v.grid.visible_pixel_count = 4),
    (v) => (v.legend.minimum_elevation_m = NaN),
    (v) => (v.legend.missing_alpha = 255),
    (v) => (v.rendering.display_only = false),
    (v) => (v.image.data = v.image.data.slice(0, -4) + 'AAAA'),
    (v) => (v.image.sha256 = 'f'.repeat(64)),
    (v) => (v.image.media_type = 'image/svg+xml'),
    (v) => (v.requested_geometry = { type: 'Point', coordinates: [0, 0] }),
  ]) {
    const copy = structuredClone(f);
    mutate(copy);
    await assert.rejects(() => parseTerrainPreview(copy, capture()));
  }
});
test('empty terrain keeps null legend distinct from valid zero', async () => {
  const f = fixture();
  f.native.valid_cell_count = 0;
  f.native.missing_cell_count = 4;
  f.native.coverage_state = 'no_valid_cells';
  f.grid.visible_pixel_count = 0;
  f.grid.transparent_pixel_count = 4;
  f.grid.state = 'no_visible_samples';
  f.legend.minimum_elevation_m = null;
  f.legend.maximum_elevation_m = null;
  assert.equal(
    (await parseTerrainPreview(f, capture())).legend.minimum_elevation_m,
    null,
  );
  f.legend.minimum_elevation_m = 0;
  await assert.rejects(() => parseTerrainPreview(f, capture()));
});
test('preview reader uses authenticated no-store GET and rejects changed sessions', async () => {
  const originalFetch = globalThis.fetch,
    originalStorage = globalThis.sessionStorage;
  let token = 'session-a';
  const calls = [];
  globalThis.sessionStorage = { getItem: () => token };
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify(fixture()));
  };
  try {
    const signal = new AbortController().signal;
    await readTerrainPreview(capture(), signal);
    assert.equal(calls[0].options.headers.Authorization, 'Bearer session-a');
    assert.equal(calls[0].options.cache, 'no-store');
    assert.equal(calls[0].options.method, 'GET');
    assert.equal(calls[0].options.signal, signal);
    assert.match(calls[0].url, /terrain-preview\?attempt_id=10000000/);
    globalThis.fetch = async () => {
      token = 'other';
      return new Response(JSON.stringify(fixture()));
    };
    await assert.rejects(
      () => readTerrainPreview(capture(), signal),
      (e) => e.status === 401,
    );
    globalThis.fetch = async () =>
      new Response('private-secret', { status: 500 });
    await assert.rejects(
      () => readTerrainPreview(capture(), signal),
      (e) => !e.message.includes('private-secret'),
    );
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.sessionStorage = originalStorage;
  }
});
test('selection and clearing fence late images; hiding during read stays hidden', async () => {
  const first = deferred(),
    second = deferred();
  let n = 0;
  const c = createTerrainLayer({
    catalogue: async () => page(),
    preview: () => (++n === 1 ? first.promise : second.promise),
  });
  const a = capture(),
    b = capture('00000000-0000-4000-8000-000000000002');
  const p1 = c.select(a),
    p2 = c.select(b);
  first.resolve(fixture(a));
  await p1;
  assert.equal(c.getSnapshot().preview, null);
  c.show(false);
  second.resolve(fixture(b));
  await p2;
  assert.equal(c.getSnapshot().shown, false);
  assert.equal(c.getSnapshot().selected, b);
  c.clear();
  assert.equal(c.getSnapshot().preview, null);
  assert.equal(c.getSnapshot().selected, null);
  c.dispose();
});
test('new search clears terrain and stale pages cannot replace the current query', async () => {
  const a = deferred(),
    b = deferred();
  let n = 0;
  const c = createTerrainLayer({
    catalogue: () => (++n === 1 ? a.promise : b.promise),
    preview: async () => fixture(),
  });
  await c.select(capture());
  const p1 = c.search(query),
    p2 = c.search({ ...query, bbox: '-2,51,0,53' });
  assert.equal(c.getSnapshot().preview, null);
  b.resolve(page([capture()]));
  await p2;
  a.resolve(page([]));
  await p1;
  assert.equal(c.getSnapshot().entries.length, 1);
  assert.ok(c.getSnapshot().query.bbox);
  c.dispose();
});
test('empty continuation remains usable and duplicate requests are single flight', async () => {
  const next = deferred();
  let n = 0;
  const c = createTerrainLayer({
    catalogue: async () => (++n === 1 ? page([], 'next') : next.promise),
    preview: async () => fixture(),
  });
  await c.search(query);
  const p = c.more();
  await c.more();
  assert.equal(n, 2);
  next.resolve(page([capture()]));
  await p;
  assert.equal(c.getSnapshot().entries.length, 1);
  c.dispose();
});
test('access failures clear retained selection and catalogue', async () => {
  const c = createTerrainLayer({
    catalogue: async () => page([capture()]),
    preview: async () => {
      throw Object.assign(new Error('Sign in again.'), { status: 403 });
    },
  });
  await c.search(query);
  await c.select(capture());
  assert.equal(c.getSnapshot().entries.length, 0);
  assert.equal(c.getSnapshot().preview, null);
  assert.equal(c.getSnapshot().selected, null);
  c.dispose();
});
test('timeout and disposal reject uncooperative late preview reads', async () => {
  const late = deferred();
  const c = createTerrainLayer(
    { catalogue: async () => page(), preview: () => late.promise },
    5,
  );
  const read = c.select(capture());
  await new Promise((r) => setTimeout(r, 15));
  assert.equal(c.getSnapshot().previewStatus, 'error');
  late.resolve(fixture());
  await read;
  assert.equal(c.getSnapshot().preview, null);
  c.dispose();
  const late2 = deferred();
  const d = createTerrainLayer({
    catalogue: async () => page(),
    preview: () => late2.promise,
  });
  const pending = d.select(capture());
  d.dispose();
  late2.resolve(fixture());
  await pending;
  assert.equal(d.getSnapshot().preview, null);
});

class FakeMap {
  constructor() {
    this.sources = new Map();
    this.layers = new Map([
      ['base', { id: 'base' }],
      ['terrene-sites-fill', { id: 'terrene-sites-fill' }],
    ]);
    this.events = new Map();
    this.loaded = true;
    this.calls = [];
  }
  on(type, fn) {
    if (!this.events.has(type)) this.events.set(type, new Set());
    this.events.get(type).add(fn);
  }
  off(type, fn) {
    this.events.get(type)?.delete(fn);
  }
  fire(type, event = {}) {
    for (const fn of this.events.get(type) || []) fn(event);
  }
  isStyleLoaded() {
    return this.loaded;
  }
  getStyle() {
    return { layers: [...this.layers.values()] };
  }
  getSource(id) {
    return this.sources.get(id);
  }
  getLayer(id) {
    return this.layers.get(id);
  }
  addSource(id, source) {
    this.sources.set(id, { ...source, loaded: false });
    this.calls.push(['source', id, source]);
  }
  addLayer(layer, before) {
    this.layers.set(layer.id, layer);
    this.calls.push(['layer', layer, before]);
  }
  removeLayer(id) {
    this.layers.delete(id);
    this.calls.push(['removeLayer', id]);
  }
  removeSource(id) {
    this.sources.delete(id);
    this.calls.push(['removeSource', id]);
  }
  isSourceLoaded(id) {
    return this.sources.get(id)?.loaded;
  }
  ready(id) {
    this.sources.get(id).loaded = true;
    this.fire('sourcedata', { sourceId: id });
  }
  resetStyle() {
    this.sources.clear();
    this.layers = new Map([
      ['base', { id: 'base' }],
      ['terrene-sites-fill', { id: 'terrene-sites-fill' }],
    ]);
    this.fire('style.load');
  }
}
test('image layer sits below Terrene geometry and style reload restores exact image', () => {
  const map = new FakeMap(),
    states = [];
  const stop = mountTerrainSource(map, fixture(), (s) => states.push(s));
  const id = [...map.sources.keys()][0];
  assert.match(map.sources.get(id).url, /^data:image\/png;base64,/);
  assert.equal(
    map.calls.find((c) => c[0] === 'layer')[2],
    'terrene-sites-fill',
  );
  assert.equal(map.getLayer(id).paint['raster-resampling'], 'nearest');
  assert.equal(map.getLayer(id).paint['raster-fade-duration'], 0);
  map.ready(id);
  assert.equal(states.at(-1), 'visible');
  map.resetStyle();
  assert.equal(states.at(-1), 'loading');
  assert.equal(map.sources.size, 1);
  map.ready(id);
  assert.equal(states.at(-1), 'visible');
  stop();
  assert.equal(map.sources.size, 0);
  assert.equal(map.layers.size, 2);
  map.resetStyle();
  assert.equal(map.sources.size, 0);
});
test('terrain failure removes its source without altering basemap or other layers', () => {
  const map = new FakeMap(),
    states = [];
  const stop = mountTerrainSource(map, fixture(), (s) => states.push(s));
  const id = [...map.sources.keys()][0];
  map.fire('error', { sourceId: 'base' });
  assert.equal(states.at(-1), 'loading');
  map.fire('error', { sourceId: id });
  assert.equal(states.at(-1), 'failed');
  assert.equal(map.sources.size, 0);
  assert.equal(map.layers.size, 2);
  stop();
});
test('a disposed old source cannot replace a newer capture or report late readiness', () => {
  const map = new FakeMap(),
    states = [];
  const stop = mountTerrainSource(map, fixture(), (s) => states.push(s));
  const old = [...map.sources.keys()][0];
  stop();
  const other = fixture();
  other.preview_fingerprint = 'd'.repeat(64);
  const stop2 = mountTerrainSource(map, other, () => {});
  const count = states.length;
  map.fire('sourcedata', { sourceId: old });
  assert.equal(states.length, count);
  assert.equal(map.sources.size, 1);
  stop2();
});
test('unloaded images time out and never remain silently visible', async () => {
  const map = new FakeMap(),
    states = [];
  const stop = mountTerrainSource(map, fixture(), (s) => states.push(s), 5);
  await new Promise((r) => setTimeout(r, 15));
  assert.equal(states.at(-1), 'failed');
  assert.equal(map.sources.size, 0);
  stop();
});
test('UI integrates selection and legend without replacing map or assessment state', async () => {
  const [map, ui, css] = await Promise.all(
    [
      '../app/map.tsx',
      '../app/terrain-map-layer.tsx',
      '../app/terrain-map-layer.module.css',
    ].map((p) => readFile(new URL(p, import.meta.url), 'utf8')),
  );
  assert.match(map, /useTerrainMapLayer\(projection\)/);
  assert.match(map, /TerrainLayerControls/);
  assert.match(ui, /Search this view/);
  assert.match(ui, /Fit terrain extent/);
  assert.match(ui, /Survey dates unknown/);
  assert.match(ui, /separate from the saved assessment/);
  assert.match(css, /overflow-wrap: anywhere/);
  assert.match(css, /flex-wrap: wrap/);
});
