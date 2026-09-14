import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [page, preflight, css, backend] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/assessment-preflight.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
  readFile(new URL('../backend/api.py', import.meta.url), 'utf8'),
]);

test('New assessment opens a preflight before the existing POST is invoked', () => {
  assert.match(
    page,
    /className="assessment-action"[\s\S]*?onClick=\{\(\) => setAssessmentPreflightOpen\(true\)\}/,
  );
  assert.match(
    page,
    /<AssessmentPreflight[\s\S]*?onConfirm=\{\(\) => void createAssessment\(\)\}/,
  );
  assert.match(
    page,
    /await api\('\/sites\/' \+ active \+ '\/assessments', 'POST'\)/,
  );
  assert.match(page, /if \(submitted\) setAssessmentPreflightOpen\(false\)/);
});

test('preflight reflects the backend pinned-input and deduplication semantics', () => {
  assert.match(backend, /ds=sorted\(d\['id'\] for d in latest\(c\)\)/);
  assert.match(backend, /\[org,id,s\['version'\],ds,spec\['signature'\]\]/);
  assert.match(preflight, /Exact Site identity and[\s\S]*?boundary version/);
  assert.match(preflight, /source version[\s\S]*?will be pinned/);
  assert.match(preflight, /service-selected model specification/);
  assert.match(
    preflight,
    /Identical inputs may reuse[\s\S]*?existing saved assessment/,
  );
  assert.match(preflight, /Earlier assessments remain unchanged/);
  assert.match(preflight, /Team review status is not changed/);
});

test('preflight keeps source availability separate from boundary coverage', () => {
  assert.match(
    preflight,
    /Registration does not guarantee coverage of this boundary/,
  );
  assert.match(
    preflight,
    /out-of-coverage evidence remains unknown, never zero/,
  );
  assert.match(
    preflight,
    /Evidence Snapshot context—not registered input for this new[\s\S]*?assessment/,
  );
  assert.match(page, /retainedSceneSources=\{retainedSceneSources\}/);
  assert.match(
    preflight,
    /current saved Site boundary and latest[\s\S]*?not the historical assessment being viewed/,
  );
  assert.match(preflight, /sources.length > 0 && sourceReadState === 'ready'/);
  assert.match(
    css,
    /\.assessment-preflight-dialog \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(css, /\.assessment-preflight-body \{[\s\S]*?overflow-y: auto/);
  assert.match(css, /\.assessment-preflight-actions button:disabled/);
  assert.match(
    css,
    /@media \(max-width: 760px\) \{[\s\S]*?\.assessment-preflight-dialog/,
  );
});
