import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, map, nature, screening, css] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/map.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/nature-panel.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/screening-context-panel.tsx', import.meta.url),
    'utf8',
  ),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
]);

test('wetland sections use compact line tabs instead of four boxed panels', () => {
  assert.match(page, /className="model-tabs"\s+variant="line"/);
  assert.match(css, /\.model-tabs\s*\{[^}]*display:\s*flex !important/s);
  assert.match(css, /\.model-tabs button\s*\{[^}]*flex:\s*0 0 auto/s);
  assert.doesNotMatch(
    css,
    /\.model-module \.model-tabs[^}]*grid-template-columns/s,
  );
});

test('layer labels only grow their copy instead of the checkbox root', () => {
  assert.match(map, /className="layer-row-copy"/);
  assert.match(css, /\.layer-row-copy\s*\{[^}]*flex:\s*1/s);
  assert.doesNotMatch(css, /\.layer-row label > span\s*\{/);
});

test('evidence keeps readable source context ahead of collapsed provenance', () => {
  assert.match(nature, /className="evidence-summary"/);
  assert.match(nature, /className="technical-provenance"/);
  assert.match(nature, /<summary>Technical provenance<\/summary>/);
  assert.match(nature, /className="raw-provenance"/);
  assert.match(css, /\.technical-provenance > summary/);
});

test('evidence register is an index of compact expandable records', () => {
  assert.match(screening, /className="evidence-register-overview"/);
  assert.match(screening, /className="evidence-record"/);
  assert.match(screening, /className="evidence-record is-gap"/);
  assert.match(screening, /className="evidence-supporting-heading"/);
  assert.match(css, /\.screening-evidence \.evidence-record > summary/);
});

test('model observations open in a closable drawer without replacing context', () => {
  assert.match(nature, /<Sheet\s/);
  assert.match(nature, /className="nature-evidence evidence-drawer"/);
  assert.match(nature, /Back to \{evidenceReturnLabel\}/);
  assert.doesNotMatch(nature, /\{!evidence &&/);
  assert.match(nature, /className="model-overview-status"/);
  assert.doesNotMatch(nature, /defaultValue=\{componentKeys\[section\]\}/);
  assert.match(page, /className="model-reference-layers"/);
});
