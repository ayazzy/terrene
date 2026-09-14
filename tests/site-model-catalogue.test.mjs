import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [page, catalogue, css, runs, runsHook] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/site-model-catalogue.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
  readFile(new URL('../app/site-reasoning-runs.ts', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/use-site-reasoning-runs.ts', import.meta.url),
    'utf8',
  ),
]);

test('Models opens as a catalogue before mounting model detail', () => {
  assert.match(page, /<TabsContent value="models">[\s\S]*?<SiteModelCatalogue/);
  assert.match(
    page,
    /key=\{\(assessment\?\.id \|\| current\.id\) \+ ':models'\}/,
  );
  assert.match(page, /model=\{result\?\.wetland_model\}/);
  assert.match(
    catalogue,
    /const \[selected, setSelected\] = useState\(false\)/,
  );
  assert.match(catalogue, /if \(selected\)[\s\S]*?Back to model catalogue/);
  assert.match(catalogue, /Open assessment result/);
});

test('catalogue exposes only the implemented model and truthful result state', () => {
  assert.equal(catalogue.match(/className="model-catalogue-card"/g)?.length, 1);
  assert.match(catalogue, /Wetland assessment/);
  assert.match(catalogue, /wetland_restoration_v0_1/);
  assert.match(catalogue, /className="model-catalogue-version"/);
  assert.match(catalogue, /className="model-catalogue-result-state"/);
  assert.match(catalogue, /INSUFFICIENT_DATA[\s\S]*?Insufficient evidence/);
  assert.match(catalogue, /No result for this assessment/);
  assert.match(
    catalogue,
    /Model outputs are interpretations, not Terrene Earth facts or team[\s\S]*?decisions/,
  );
});

test('snapshot-bound runs remain distinct and selectable in Models', () => {
  assert.match(catalogue, /Snapshot-bound runs/);
  assert.match(catalogue, /separate from the selected legacy assessment above/);
  assert.match(catalogue, /selectedRunId/);
  assert.match(catalogue, /aria-pressed=\{selectedRun\?\.id === run\.id\}/);
  assert.match(catalogue, /Evidence Snapshot/);
  assert.match(catalogue, /Input binding/);
  assert.match(catalogue, /not a Terrene Earth[\s\S]*?fact\s+or team decision/);
  assert.match(page, /reasoningRuns=\{siteReasoningRuns\.runs\}/);
  assert.match(page, /siteReasoningRuns\.refresh\(\)/);
});

test('Site reasoning run reads are finite, scoped and no-store', () => {
  assert.match(runs, /`\/api\/sites\/\$\{siteId\}\/reasoning-runs`/);
  assert.match(runs, /cache: 'no-store'/);
  assert.match(runs, /site_reasoning_run_catalogue_v1/);
  assert.match(runs, /catalogue\.site_id !== siteId/);
  assert.match(runsHook, /createLatestRequestFence/);
  assert.match(runsHook, /abort\.signal\.aborted/);
  assert.match(runsHook, /catalogueSiteId === siteId/);
  assert.match(runsHook, /setState\('unavailable'\)/);
  assert.match(runsHook, /setRevision\(\(value\) => value \+ 1\)/);
});

test('catalogue and detail use the shared operating-card hierarchy', () => {
  assert.match(
    css,
    /\.model-catalogue-card \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(css, /\.model-catalogue-state\.is-warning/);
  assert.match(
    css,
    /\.model-catalogue-result-state \{\s*text-transform: capitalize;/,
  );
  assert.match(css, /\.model-catalogue-back/);
  assert.match(
    css,
    /\.site-reasoning-run-catalogue \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(
    css,
    /\.site-reasoning-run-list > button\[aria-pressed='true'\]/,
  );
  assert.match(
    css,
    /@media \(max-width: 760px\)[\s\S]*?\.model-catalogue-card dl \{ grid-template-columns: 1fr; \}/,
  );
  assert.match(
    css,
    /@media \(max-width: 760px\)[\s\S]*?\.site-reasoning-runs-layout,[\s\S]*?grid-template-columns: 1fr/,
  );
});
