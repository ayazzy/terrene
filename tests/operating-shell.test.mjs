import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [page, shell, css, layout, map] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/operating-shell.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
  readFile(new URL('../app/layout.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/map.tsx', import.meta.url), 'utf8'),
]);

test('shell identifies Terrene as infrastructure intelligence', () => {
  assert.match(shell, />Terrene</);
  assert.match(shell, />Infrastructure intelligence</);
  assert.match(shell, /Infrastructure operating picture/);
  assert.doesNotMatch(page, /Land opportunities|EARTH INTELLIGENCE/);
  assert.match(layout, /Terrene — Infrastructure Intelligence/);
  assert.doesNotMatch(layout, /Earth Intelligence|understanding land/);
  assert.doesNotMatch(`${page}\n${map}`, /land sites|land boundary/i);
  assert.doesNotMatch(shell, /Operational|Live evidence|SYSTEM STATUS/);
});

test('command bar exposes search and source records without redundant context', () => {
  assert.match(shell, /aria-label="Search infrastructure entities"/);
  assert.match(shell, /Search Sites and Project Subjects/);
  assert.match(shell, /entity\.kind === 'site'/);
  assert.match(shell, /<small>\{sourceLabel\}<\/small>[\s\S]*\{sourceStatus\}/);
  assert.match(shell, /<small>Source records<\/small>[\s\S]*\{sourceAsOf\}/);
  assert.doesNotMatch(shell, /<small>Scope<\/small>/);
  assert.doesNotMatch(shell, /<small>Selection<\/small>/);
  assert.doesNotMatch(page, /selection=\{commandSelection\}/);
  assert.match(page, /datasets\.map\(\(dataset\) => dataset\.retrieved\)/);
  assert.match(page, /dataset\.state === 'available'/);
  assert.match(page, /mapEvidence\.scene\?\.sources \|\| \[\]/);
  assert.match(page, /`\$\{retainedSceneSources\.length\} retained`/);
});

test('responsive shell keeps context explicit without claiming telemetry', () => {
  assert.match(css, /@media \(max-width: 47\.5rem\)/);
  assert.match(css, /--topbar-height: 6\.5rem/);
  assert.match(css, /\.mobileContext[\s\S]*display: block/);
  assert.match(shell, /\{contextLabel\} · \{sourceAsOf\.replace/);
  assert.match(page, /'Dates unavailable'/);
  assert.match(page, /'No sources recorded'/);
  assert.doesNotMatch(shell, /confidence|latency|sensor|readiness/i);
});
