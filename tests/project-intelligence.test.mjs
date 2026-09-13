import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import {
  claimValue,
  evidenceStateLabel,
  humanize,
  projectEvidenceSourceKey,
  readProjectIntelligenceRun,
  readProjectIntelligenceRuns,
} from '../app/project-intelligence.ts';

const [page, workspace, state] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/project-intelligence-workspace.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/use-project-intelligence-state.ts', import.meta.url), 'utf8'),
]);

function mockSession(t) {
  const previous = globalThis.sessionStorage;
  globalThis.sessionStorage = { getItem: () => 'project-token' };
  t.after(() => {
    if (previous) globalThis.sessionStorage = previous;
    else delete globalThis.sessionStorage;
  });
}

test('project intelligence helpers preserve evidence semantics', () => {
  assert.equal(humanize('construction_complete'), 'Construction complete');
  assert.equal(evidenceStateLabel('insufficient_evidence'), 'Insufficient evidence');
  assert.equal(claimValue({ state: 'known', date: '2032-01-01' }), '2032-01-01');
  assert.equal(claimValue({ state: 'unknown', reason: 'Not published' }), 'Unknown · Not published');
  assert.notEqual(
    projectEvidenceSourceKey('register', 'version-1'),
    projectEvidenceSourceKey('register', 'version-2'),
  );
});

test('run reads are GET-only, authenticated, and scoped to the selected subject', async (t) => {
  mockSession(t);
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    calls.push({ path, options });
    return Response.json([{ id: 'run-1', project_subject_id: 'subject/1' }]);
  });
  await readProjectIntelligenceRuns('subject/1');
  assert.equal(calls[0].path, '/api/project-subjects/subject%2F1/intelligence-runs');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer project-token');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(calls[0].options.method, undefined);

  t.mock.method(globalThis, 'fetch', async () =>
    Response.json([{ id: 'run-2', project_subject_id: 'another-subject' }]),
  );
  await assert.rejects(
    readProjectIntelligenceRuns('subject/1'),
    /does not match the selected Project Subject/,
  );
});

test('run detail rejects a contradictory immutable envelope', async (t) => {
  mockSession(t);
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    id: 'run-1',
    result: { evidence_binding_id: 'binding-a' },
    evidence_binding: { id: 'binding-b' },
  }));
  await assert.rejects(
    readProjectIntelligenceRun('run-1'),
    /does not match its immutable evidence envelope/,
  );
});

test('workspace remains isolated, read-only, and makes evidence states first-class', () => {
  assert.match(page, /view === 'project-intelligence'/);
  assert.match(page, /useOperatingPictureState\(\)/);
  assert.match(page, /<ProjectIntelligenceWorkspace\s+enabled=/);
  assert.match(page, /selectedSubjectId=\{requestedProjectSubjectId\}/);
  assert.match(page, /selectedRunId=\{requestedProjectRunId\}/);
  assert.match(page, /onSubjectChange=\{\(id, method\) =>/);
  assert.match(workspace, /SOURCE ASSERTIONS/);
  assert.match(workspace, /TERRENE CONCLUSION/);
  assert.match(workspace, /Conflicts &amp; unknowns/);
  assert.match(workspace, /IMMUTABLE RUN HISTORY/);
  assert.doesNotMatch(workspace, /POST|PATCH|DELETE|pursue|dismiss|confidence/i);
  assert.match(state, /createLatestRequestFence\(\)/);
  assert.match(state, /subjectRequest\.current\.isCurrent\(request\)/);
  assert.match(state, /runRequest\.current\.isCurrent\(request\)/);
  assert.match(state, /detailRequest\.current\.isCurrent\(request\)/);
  assert.match(state, /run\?\.project_subject_id === selectedSubjectId/);
  assert.match(state, /runRequest\.current\.invalidate\(\)/);
  assert.match(state, /detailRequest\.current\.invalidate\(\)/);
  assert.match(workspace, /projectEvidenceSourceKey\(\s*item\.source_record_id,\s*item\.source_version/);
});
