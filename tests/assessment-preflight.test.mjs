import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [page, preflight, css, backend] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/assessment-preflight.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
  readFile(new URL('../backend/api.py', import.meta.url), 'utf8'),
]);

test('New analysis opens an explicit snapshot reasoning preflight', () => {
  assert.match(
    page,
    /className="assessment-action"[\s\S]*?onClick=\{openAssessmentPreflight\}/,
  );
  assert.match(page, />\s*New analysis\s*</);
  assert.match(page, /mobile-assessment-action[\s\S]*?New analysis/);
  assert.match(page, /api\(`\/sites\/\$\{active\}\/reasoning-inputs`\)/);
  assert.match(page, /reasoningRequestFence\.current/);
  assert.match(page, /if \(!requestFence\.isCurrent\(request\)\) return/);
  assert.match(
    page,
    /catalogue\.contract_version !==[\s\S]*?'site_reasoning_input_catalogue_v1'/,
  );
  assert.match(page, /catalogue\.site_id !== active/);
});

test('current immutable evidence is preferred and its exact envelope is submitted', () => {
  assert.match(
    preflight,
    /Number\(right\.current_boundary\) - Number\(left\.current_boundary\)/,
  );
  assert.match(
    preflight,
    /orderedSnapshots\.find\(\(snapshot\) => snapshot\.current_boundary\)/,
  );
  assert.match(preflight, /onRunSnapshot\(selectedSnapshot\.run_request\)/);
  assert.match(
    page,
    /api\([\s\S]*?`\/sites\/\$\{active\}\/reasoning-runs`[\s\S]*?'POST',[\s\S]*?request/,
  );
  assert.match(
    page,
    /run\.evidence_snapshot_id !== request\.evidence_snapshot_id/,
  );
  assert.match(page, /run\.model_signature !== request\.model_signature/);
  assert.match(backend, /'\/api\/sites\/\{id\}\/reasoning-inputs'/);
  assert.match(backend, /'\/api\/sites\/\{id\}\/reasoning-runs'/);
});

test('retained reasoning and legacy acquisition remain visibly separate', () => {
  assert.match(preflight, /Use retained evidence/);
  assert.match(preflight, /Run a model without reacquiring sources/);
  assert.match(preflight, /Acquire new evidence/);
  assert.match(preflight, /Use the legacy registered-dataset pipeline/);
  assert.match(preflight, /role="radiogroup"[\s\S]*?type="radio"/);
  assert.match(preflight, /sources\.length > 0 && sourceReadState === 'ready'/);
  assert.match(
    page,
    /await api\('\/sites\/' \+ active \+ '\/assessments', 'POST'\)/,
  );
  assert.match(preflight, /unavailable evidence remains unknown, never zero/);
  assert.match(
    preflight,
    /retained building and height evidence is[\s\S]*?not silently treated as a wetland input/,
  );
});

test('historical selection, unavailable reads and completed runs stay explicit', () => {
  assert.match(
    preflight,
    /Historical boundary v\$\{snapshot\.boundary_version\}/,
  );
  assert.match(
    preflight,
    /This run stays tied to historical boundary v[\s\S]*?It will not use or[\s\S]*?change the current boundary/,
  );
  assert.match(preflight, /Evidence Snapshots could not be verified/);
  assert.match(preflight, /onRetryReasoning/);
  assert.match(preflight, /REASONING COMPLETE/);
  assert.match(preflight, /Wetland model run retained/);
  assert.match(
    preflight,
    /This is a Terrene Reasoning result, not an Earth fact/,
  );
  assert.match(
    css,
    /\.assessment-mode-picker > label\.is-selected \{[\s\S]*?var\(--surface-selected\)/,
  );
  assert.match(css, /\.assessment-snapshot-options \{[\s\S]*?overflow-y: auto/);
  assert.match(css, /\.assessment-run-complete \{[\s\S]*?border-radius/);
  assert.match(css, /\.assessment-preflight-body \{[\s\S]*?overflow-y: auto/);
  assert.match(
    css,
    /\[data-slot='dialog-overlay'\] \{ z-index: 90 !important; \}/,
  );
  assert.match(
    css,
    /\.assessment-preflight-dialog \{[\s\S]*?z-index: 100 !important/,
  );
  assert.match(
    css,
    /@media \(max-width: 760px\) \{[\s\S]*?\.assessment-mode-picker,[\s\S]*?grid-template-columns: 1fr/,
  );
  assert.match(css, /translate: -50% 0 !important/);
  assert.match(
    css,
    /\.site-actions-menu \.mobile-assessment-action \{ display: inline-flex !important; \}/,
  );
});
