import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [page, catalogue, css] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/site-model-catalogue.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
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
  assert.match(catalogue, /Open model/);
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
    /@media \(max-width: 760px\)[\s\S]*?\.model-catalogue-card dl \{ grid-template-columns: 1fr; \}/,
  );
});
