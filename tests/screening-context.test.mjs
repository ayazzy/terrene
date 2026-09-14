import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  contextPath, readScreeningContext, requestScreeningContext, screeningAssessmentKey, screeningValue,
} from '../app/screening-context.ts';
import { resolveWorkspaceAssessment } from '../app/site-workspace-view-model.ts';

const assessment = { id: 'historical/id', site_id: 'site', version: 1, state: 'completed' };
function run(version = 1) {
  return { id: 'run-' + version, site_id: 'site', boundary_version: version, evidence_snapshot_id: 'snapshot-' + version,
    result: { module_id: 'site_screening_context', site_id: 'site', boundary_version: version, evidence_snapshot_id: 'snapshot-' + version } };
}
function mockRequest(t, handler) {
  t.mock.method(globalThis, 'fetch', handler);
  const previous = globalThis.sessionStorage;
  globalThis.sessionStorage = { getItem: () => 'test-session' };
  t.after(() => { if (previous) globalThis.sessionStorage = previous; else delete globalThis.sessionStorage; });
}

test('selected historical and current assessment use their own scoped action, not the current site', async t => {
  const calls = [];
  mockRequest(t, async (path, options) => {
    calls.push({ path, options });
    return Response.json(run(path.includes('current') ? 2 : 1));
  });
  assert.equal((await requestScreeningContext(assessment, 'GET')).boundary_version, 1);
  const current = { ...assessment, id: 'current', version: 2 };
  assert.equal((await requestScreeningContext(current, 'POST')).boundary_version, 2);
  assert.equal(calls[0].path, '/api/assessments/historical%2Fid/screening-context');
  assert.equal(calls[0].options.method, 'GET');
  assert.equal(calls[1].options.method, 'POST');
  assert.equal(calls[1].options.headers.Authorization, 'Bearer test-session');
  assert.equal(contextPath(assessment.id) + '/report', calls[0].path + '/report');
});

test('absent is distinct from failed, and a wrong-boundary response fails closed', async t => {
  mockRequest(t, async () => Response.json(null));
  assert.equal(await requestScreeningContext(assessment, 'GET'), null);
  await assert.rejects(requestScreeningContext(assessment, 'POST'), /No persisted/);
  t.mock.method(globalThis, 'fetch', async () => Response.json(run(2)));
  await assert.rejects(requestScreeningContext(assessment, 'GET'), /selected assessment boundary/);
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Stored evidence integrity failed' }, { status: 500 }));
  await assert.rejects(requestScreeningContext(assessment, 'GET'), /integrity failed/);
});

test('read states distinguish absent, available, unsupported, access, and retryable failures', async t => {
  mockRequest(t, async () => Response.json(null));
  assert.deepEqual(await readScreeningContext(assessment), { state: 'absent', run: null, error: '' });
  t.mock.method(globalThis, 'fetch', async () => Response.json(run()));
  assert.equal((await readScreeningContext(assessment)).state, 'available');
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Historical evidence is unsupported.' }, { status: 409 }));
  assert.equal((await readScreeningContext(assessment)).state, 'unsupported');
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Sign in required.' }, { status: 401 }));
  assert.equal((await readScreeningContext(assessment)).state, 'unauthorized');
  t.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Service unavailable.' }, { status: 503 }));
  assert.equal((await readScreeningContext(assessment)).state, 'failed');
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network unavailable'); });
  assert.equal((await readScreeningContext(assessment)).state, 'failed');
});

test('an unresolved read times out into a finite retryable failure', async t => {
  mockRequest(t, async () => new Promise(() => {}));
  const started = Date.now();
  const result = await readScreeningContext(assessment, undefined, 10);
  assert.equal(result.state, 'failed');
  assert.match(result.error, /too long.*retry/i);
  assert.ok(Date.now() - started < 500);
});

test('selection changes can abort the previous read', async t => {
  const controller = new AbortController();
  mockRequest(t, async (_path, options) => {
    assert.ok(options.signal instanceof AbortSignal);
    controller.abort();
    options.signal.throwIfAborted();
  });
  await assert.rejects(requestScreeningContext(assessment, 'GET', controller.signal), { name: 'AbortError' });
});

test('assessment identity is stable across refresh objects and changes across selections', () => {
  assert.equal(screeningAssessmentKey(assessment), screeningAssessmentKey({ ...assessment }));
  assert.notEqual(screeningAssessmentKey(assessment), screeningAssessmentKey({ ...assessment, id: 'new' }));
  assert.notEqual(screeningAssessmentKey(assessment), screeningAssessmentKey({ ...assessment, version: 2 }));
});

test('values preserve mapped zero, boolean semantics and independent source measurements', () => {
  assert.equal(screeningValue({ value: {kind:'number',value:0}, unit:'fraction' }), '0%');
  assert.equal(screeningValue({ value: {kind:'boolean',value:false}, unit:'boolean' }), 'No');
  assert.equal(screeningValue({ value: {kind:'number',value:.9532}, unit:'fraction' }), '95.32%');
  assert.equal(screeningValue({ value: {kind:'number',value:.433473}, unit:'fraction' }), '43.347%');
});

test('workspace controller scopes current and historical assessment state', () => {
  const current = { ...assessment, id: 'current', version: 2, result: {}, geometry: {}, created: 'now', dataset_ids: [] };
  const historical = { ...current, id: 'historical', version: 1 };
  const site = { id: 'site', version: 2, assessment: current };
  assert.equal(resolveWorkspaceAssessment(site, [historical], historical.id).id, historical.id);
  assert.equal(resolveWorkspaceAssessment(site, [{ ...historical, site_id: 'other' }], historical.id).id, current.id);
  assert.equal(resolveWorkspaceAssessment(site, [], 'stale-selection').id, current.id);
});

test('workspace hierarchy keeps Screening Context primary and team decisions separate', () => {
  const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
  const panel = readFileSync(new URL('../app/screening-context-panel.tsx', import.meta.url), 'utf8');
  const state = readFileSync(new URL('../app/site-workspace-state.ts', import.meta.url), 'utf8');
  assert.match(page, /<TabsTrigger value="overview">Brief<\/TabsTrigger>[\s\S]*<TabsTrigger value="evidence">Evidence<\/TabsTrigger>[\s\S]*<TabsTrigger value="models">Models<\/TabsTrigger>[\s\S]*<TabsTrigger value="history">History<\/TabsTrigger>/);
  assert.match(page, /key=\{assessment.id \+ ':overview'\}[\s\S]*mode="overview"/);
  assert.match(page, /TERRENE REASONING[\s\S]*Wetland assessment/);
  assert.match(panel, /This brief does not score the site or make a team decision/);
  assert.match(state, /requestGeneration\.current \+= 1;\s+abort\.abort\(\)/);
  assert.match(state, /assessmentVersion,\s+contextRetry,/);
  assert.match(panel, /state === 'unsupported'/);
  assert.match(panel, /state === 'unauthorized'/);
  assert.doesNotMatch(panel, /state !== 'loading'/);
  assert.doesNotMatch(panel, /PATCH|\/sites\/|statuses|setSelectedAssessment/);
  assert.match(state, /contextPath\(assessment.id\) \+ '\/report'/);
  assert.match(panel, /source-semantic context/i);
});
