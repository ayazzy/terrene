import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { createCaptureBrowser } from '../app/acquisition-browser-state.ts';
import {
  defaultCaptureQuery as query,
  parseCaptureCatalogue,
  parseCaptureDetail,
  captureBounds,
  evidenceDateLabel,
  readCaptureCatalogue,
  readCaptureDetail,
} from '../app/acquisitions.ts';
import { GET as proxy } from '../app/api/[...path]/route.ts';

const entry = (id = '00000000-0000-4000-8000-000000000001') => ({
  acquisition_id: id,
  attempt_id: '10000000-0000-4000-8000-000000000001',
  source_id: 'nasa.power_merra2_daily',
  source_label: 'NASA POWER / MERRA-2 daily weather',
  adapter_version: 'nasa_power_daily_point_v1',
  family: 'weather_timeseries',
  manifest_sha256: 'a'.repeat(64),
  request_sha256: 'b'.repeat(64),
  geometry_fingerprint: 'c'.repeat(64),
  requested_geometry: { type: 'Point', coordinates: [-1.255, 51.745] },
  spatial_semantics: 'weather_query_point_not_area_coverage',
  capture_started: '2026-09-15T10:00:00Z',
  capture_completed: '2026-09-15T10:01:00Z',
  evidence_time: {
    kind: 'interval',
    start: '2024-02-28T00:00:00Z',
    end_exclusive: '2024-03-02T00:00:00Z',
  },
  counts: [{ series: 'T2M', measure: 'present_days', present: 0, expected: 3 }],
  evidence_semantics: ['Coarse point-query reanalysis.'],
  manifest_verified: true,
  artifact_verification: 'not_performed',
  artifact_count: 1,
  artifact_bytes: 123,
});
const page = (entries = [], next = null, q = query) => ({
  contract_version: 'acquisition_catalogue_v1',
  query: {
    bbox: null,
    source_id: null,
    start_date: null,
    end_date: null,
    ...q,
  },
  entries,
  scanned_count: entries.length,
  next_cursor: next,
  scan_complete: next === null,
  ordering: 'request_created_desc_id_desc',
  limitations: [],
});
const detail = (e) => ({
  contract_version: 'acquisition_detail_v1',
  entry: { ...e, artifact_verification: 'verified' },
  artifacts: [{ role: 'series', sha256: 'f'.repeat(64), bytes: 123 }],
});
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
function mockStorage(t, value) {
  const prior = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage');
  Object.defineProperty(globalThis, 'sessionStorage', {
    value,
    configurable: true,
  });
  t.after(() => {
    if (prior) Object.defineProperty(globalThis, 'sessionStorage', prior);
    else delete globalThis.sessionStorage;
  });
}
const second = () => entry('00000000-0000-4000-8000-000000000002');

test('contract preserves point geometry, zero availability and inclusive leap-day interval', () => {
  const e = entry();
  assert.deepEqual(parseCaptureCatalogue(page([e]), query).entries, [e]);
  assert.deepEqual(
    captureBounds(e.requested_geometry),
    [-1.255, 51.745, -1.255, 51.745],
  );
  assert.equal(evidenceDateLabel(e), '28 Feb 2024 – 1 Mar 2024');
  const undated = {
    ...e,
    family: 'raster',
    evidence_time: { kind: 'unknown', start: null, end_exclusive: null },
  };
  assert.equal(evidenceDateLabel(undated), 'Evidence date unknown');
});

test('catalogue rejects wrong filters, broken paging and unsafe evidence representations', () => {
  for (const mutate of [
    (p) => (p.query.source_id = 'naturescot.sssi'),
    (p) => (p.contract_version = 'other'),
    (p) => (p.scan_complete = false),
    (p) => (p.scanned_count = 51),
    (p) => p.entries.push(p.entries[0]),
    (p) => (p.entries[0].artifact_verification = 'verified'),
    (p) => (p.entries[0].counts[0].present = null),
    (p) => (p.entries[0].counts[0].present = 4),
    (p) => (p.entries[0].requested_geometry.coordinates = [NaN, 51]),
    (p) => (p.entries[0].spatial_semantics = 'acquisition_request_area'),
    (p) => (p.entries[0].capture_completed = 'bad'),
    (p) => (p.entries[0].evidence_time.start = null),
  ]) {
    const p = page([entry()]);
    mutate(p);
    assert.throws(() => parseCaptureCatalogue(p, query));
  }
});

test('detail pins exact request, attempt, source, geometry and manifest identities', () => {
  const e = entry();
  assert.deepEqual(parseCaptureDetail(detail(e), e), detail(e));
  for (const key of [
    'acquisition_id',
    'attempt_id',
    'source_id',
    'adapter_version',
    'manifest_sha256',
    'request_sha256',
    'geometry_fingerprint',
  ]) {
    const changed = detail(e);
    changed.entry[key] = 'wrong';
    assert.throws(() => parseCaptureDetail(changed, e));
  }
  const changed = detail(e);
  changed.artifacts[0].bytes = 1;
  assert.throws(() => parseCaptureDetail(changed, e));
});

test('new search rejects late old results even when transport ignores abort', async () => {
  const old = deferred(),
    fresh = deferred();
  let calls = 0;
  const b = createCaptureBrowser(
    {
      catalogue: () => (++calls === 1 ? old.promise : fresh.promise),
      detail: async (e) => detail(e),
    },
    query,
  );
  const first = b.search(query);
  const nextQuery = { ...query, bbox: '-2,51,0,53' };
  const next = b.search(nextQuery);
  fresh.resolve(page([second()], null, nextQuery));
  await next;
  old.resolve(page([entry()]));
  await first;
  assert.deepEqual(b.getSnapshot().entries, [second()]);
  assert.deepEqual(b.getSnapshot().query, nextQuery);
});

test('empty filtered page remains continuable and preserves exact query/cursor', async () => {
  const calls = [];
  const q = { ...query, start_date: '2024-02-28', end_date: '2024-03-01' };
  const b = createCaptureBrowser(
    {
      catalogue: async (q, c) => {
        calls.push([q, c]);
        return c
          ? page([entry()], null, q)
          : { ...page([], 'next', q), scanned_count: 50 };
      },
      detail: async (e) => detail(e),
    },
    q,
  );
  await b.search(q);
  assert.equal(b.getSnapshot().page.scan_complete, false);
  assert.equal(b.getSnapshot().entries.length, 0);
  await b.more();
  assert.deepEqual(calls, [
    [q, undefined],
    [q, 'next'],
  ]);
  assert.equal(b.getSnapshot().scanned, 51);
  assert.equal(b.getSnapshot().entries.length, 1);
  await b.more();
  assert.equal(calls.length, 2);
});

test('continuation is single-flight and failed page is retried without duplicating results', async () => {
  const pending = deferred();
  let calls = 0;
  const b = createCaptureBrowser(
    {
      catalogue: async () => {
        calls++;
        if (calls === 1) return page([entry()], 'next');
        if (calls === 2) return pending.promise;
        return page([entry(), second()]);
      },
      detail: async (e) => detail(e),
    },
    query,
  );
  await b.search(query);
  const more = b.more();
  await b.more();
  assert.equal(calls, 2);
  pending.reject(new Error('Offline'));
  await more;
  assert.equal(b.getSnapshot().entries.length, 1);
  assert.equal(b.getSnapshot().listStatus, 'error');
  await b.more();
  assert.equal(b.getSnapshot().entries.length, 2);
  assert.equal(b.getSnapshot().listError, '');
});

test('non-advancing cursor produces recoverable error rather than an infinite scan', async () => {
  const b = createCaptureBrowser(
    { catalogue: async () => page([], 'same'), detail: async (e) => detail(e) },
    query,
  );
  await b.search(query);
  await b.more();
  assert.equal(b.getSnapshot().listStatus, 'error');
  assert.match(b.getSnapshot().listError, /did not advance/);
});

test('switching captures and closing prevent stale detail from reappearing', async () => {
  const old = deferred(),
    next = deferred();
  let calls = 0;
  const b = createCaptureBrowser(
    {
      catalogue: async () => page([entry(), second()]),
      detail: () => (++calls === 1 ? old.promise : next.promise),
    },
    query,
  );
  await b.search(query);
  const first = b.select(entry());
  const secondRead = b.select(second());
  assert.equal(b.getSnapshot().detail, null);
  next.resolve(detail(second()));
  await secondRead;
  old.resolve(detail(entry()));
  await first;
  assert.equal(
    b.getSnapshot().detail.entry.acquisition_id,
    second().acquisition_id,
  );
  const late = deferred();
  const c = createCaptureBrowser(
    { catalogue: async () => page([]), detail: () => late.promise },
    query,
  );
  const task = c.select(entry());
  c.close();
  late.resolve(detail(entry()));
  await task;
  assert.equal(c.getSnapshot().detail, null);
  assert.equal(c.getSnapshot().selected, null);
});

test('search change and unmount fence pending detail and list updates', async () => {
  const pending = deferred();
  const b = createCaptureBrowser(
    { catalogue: async () => page([]), detail: () => pending.promise },
    query,
  );
  const selection = b.select(entry());
  await b.search(query);
  pending.resolve(detail(entry()));
  await selection;
  assert.equal(b.getSnapshot().detail, null);
  const late = deferred();
  const c = createCaptureBrowser(
    { catalogue: () => late.promise, detail: async (e) => detail(e) },
    query,
  );
  let notifications = 0;
  c.subscribe(() => notifications++);
  const task = c.search(query);
  c.dispose();
  const before = notifications;
  late.resolve(page([entry()]));
  await task;
  assert.equal(notifications, before);
  assert.equal(c.getSnapshot().entries.length, 0);
});

test('detail failure clears old evidence and retry can verify selected capture', async () => {
  let fail = false;
  const b = createCaptureBrowser(
    {
      catalogue: async () => page([]),
      detail: async (e) => {
        if (fail) throw new Error('Corrupt evidence');
        return detail(e);
      },
    },
    query,
  );
  await b.select(entry());
  fail = true;
  await b.select(second());
  assert.equal(b.getSnapshot().detail, null);
  assert.equal(b.getSnapshot().detailStatus, 'error');
  fail = false;
  await b.select(second());
  assert.equal(
    b.getSnapshot().detail.entry.acquisition_id,
    second().acquisition_id,
  );
  assert.equal(b.getSnapshot().detailError, '');
});

test('access failure clears all previously displayed captures and details', async () => {
  for (const operation of ['catalogue', 'detail']) {
    let fail = false;
    const error = Object.assign(new Error('Sign in'), { status: 401 });
    const b = createCaptureBrowser(
      {
        catalogue: async () => {
          if (fail && operation === 'catalogue') throw error;
          return page([entry()], 'next');
        },
        detail: async (e) => {
          if (fail && operation === 'detail') throw error;
          return detail(e);
        },
      },
      query,
    );
    await b.search(query);
    await b.select(entry());
    fail = true;
    if (operation === 'catalogue') await b.more();
    else await b.select(second());
    assert.equal(b.getSnapshot().entries.length, 0);
    assert.equal(b.getSnapshot().detail, null);
    assert.equal(b.getSnapshot().selected, null);
    assert.equal(b.getSnapshot().listStatus, 'error');
  }
});

test('browser readers are authenticated no-store GETs and ignore untrusted detail URLs', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push([url, options]);
    return Response.json(
      url.includes('attempt_id') ? detail(entry()) : page([entry()]),
    );
  });
  mockStorage(t, {
    getItem: () => 'test-token',
  });
  const calls = [];
  const signal = new AbortController().signal;
  await readCaptureCatalogue(query, undefined, signal);
  await readCaptureDetail(
    { ...entry(), detail_path: 'https://untrusted.test/' },
    signal,
  );
  assert.equal(calls.length, 2);
  assert.match(
    calls[1][0],
    /^\/api\/acquisitions\/00000000-.*\?attempt_id=10000000-/,
  );
  for (const [, options] of calls) {
    assert.equal(options.method, 'GET');
    assert.equal(options.cache, 'no-store');
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    assert.equal(options.signal, signal);
  }
});

test('readers reject a session change during response and sanitize server failure', async (t) => {
  let token = 'first';
  mockStorage(t, { getItem: () => token });
  t.mock.method(globalThis, 'fetch', async () => {
    token = 'second';
    return Response.json(page([entry()]));
  });
  await assert.rejects(
    readCaptureCatalogue(query, undefined, new AbortController().signal),
    (e) => e.status === 401,
  );
  t.mock.method(globalThis, 'fetch', async () =>
    Response.json({ detail: 'private storage key' }, { status: 500 }),
  );
  await assert.rejects(
    readCaptureCatalogue(query, undefined, new AbortController().signal),
    (e) => !e.message.includes('private storage'),
  );
});

test('same-origin proxy retains upstream no-store and bearer authentication', async (t) => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(options.headers.get('authorization'), 'Bearer test');
    return Response.json(
      { ok: true },
      { headers: { 'Cache-Control': 'no-store' } },
    );
  });
  const response = await proxy(
    new Request('http://localhost/api/acquisitions?limit=10', {
      headers: { authorization: 'Bearer test' },
    }),
  );
  assert.equal(response.headers.get('cache-control'), 'no-store');
});

test('browser integrates separately from assessment sources and exposes accessible recovery', async () => {
  const [component, css, pageSource] = await Promise.all(
    [
      'app/acquisition-browser.tsx',
      'app/acquisition-browser.module.css',
      'app/page.tsx',
    ].map((p) => readFile(new URL('../' + p, import.meta.url), 'utf8')),
  );
  assert.match(pageSource, /<AcquisitionBrowser \/>/);
  assert.match(pageSource, /Assessment source library/);
  assert.match(component, /No matches in the captures checked so far/);
  assert.match(component, /Retry file verification/);
  assert.match(component, /captureButtons.current.get\(id\)\?\.focus\(\)/);
  assert.match(component, /detailHeading.current\?\.focus\(\)/);
  assert.match(css, /@media \(max-width: 600px\)/);
  assert.match(css, /overflow-wrap: anywhere/);
});
