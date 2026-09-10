import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  contextPath, readScreeningContext, requestScreeningContext, screeningAssessmentKey, screeningValue,
} from '../app/screening-context.ts';

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

test('computed panel is keyed to the selected assessment and has no team-decision write', () => {
  const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
  const panel = readFileSync(new URL('../app/screening-context-panel.tsx', import.meta.url), 'utf8');
  assert.match(page, /<ScreeningContextPanel\s+key=\{assessment.id\}\s+assessment=\{assessment\}/);
  assert.match(panel, /separate from your team’s review status/);
  assert.match(panel, /requestGeneration\.current \+= 1;\s+abort\.abort\(\)/);
  assert.match(panel, /\[assessmentId, assessmentKey, assessmentSiteId, assessmentVersion, retry\]/);
  assert.match(panel, /state === 'unsupported'/);
  assert.match(panel, /state === 'unauthorized'/);
  assert.doesNotMatch(panel, /state !== 'loading'/);
  assert.doesNotMatch(panel, /PATCH|\/sites\/|statuses|setSelectedAssessment/);
  assert.match(panel, /contextPath\(assessment.id\) \+ '\/report'/);
  assert.match(panel, /source-semantic context/i);
});
