import test from 'node:test';
import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';

const [page, map, mapCss, shellCss] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/map.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/infrastructure-map.module.css', import.meta.url),
    'utf8',
  ),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
]);

test('portfolio application chrome is above all geographic content', () => {
  assert.match(map, /data-primary-map="infrastructure-operating-picture"/);
  assert.match(mapCss, /\.roster\s*\{[^}]*z-index:\s*20/s);
  assert.match(
    shellCss,
    /\.portfolio-main > \.sites-views\)\s*\{[^}]*z-index:\s*16/s,
  );
  assert.match(
    shellCss,
    /\.spatial-main > \.entity-dossier\)\s*\{[^}]*z-index:\s*18/s,
  );
  assert.match(
    shellCss,
    /@media \(min-width: 80rem\)[\s\S]*?\.spatial-main > \.entity-dossier\)[^}]*width: min\(48rem, 40%\)/,
  );
});

test('the obsolete portfolio map controller cannot return', async () => {
  await assert.rejects(
    access(new URL('../app/portfolio-map.tsx', import.meta.url)),
    /ENOENT/,
  );
  assert.doesNotMatch(page, /PortfolioMap|portfolio-map/);
});

test('the retained map exposes local readiness without claiming live telemetry', () => {
  assert.match(map, /const startedAt = performance\.now\(\)/);
  assert.match(map, /data-map-ready=\{ready\}/);
  assert.match(map, /data-map-ready-ms=\{readyMs \?\? undefined\}/);
  assert.match(map, /aria-busy=\{!ready\}/);
  assert.doesNotMatch(map, /real[- ]?time|latency|telemetry/i);
});

test('drawing map is part of the stable client module graph', () => {
  assert.match(page, /import SiteMap from '\.\/map';/);
  assert.doesNotMatch(page, /dynamic\(\(\) => import\('\.\/map'\)/);
  assert.match(page, /<SiteMap[\s\S]*?\bdraw\b[\s\S]*?onDraw=/);
});

test('infrastructure raster treatment stays scoped to the primary map', () => {
  assert.match(map, /'raster-opacity': 0\.8/);
  assert.match(
    mapCss,
    /\.operatingMap :global\(\.map-canvas \.maplibregl-canvas\)/,
  );
  assert.doesNotMatch(mapCss, /portfolio-canvas|portfolio-map/);
});

test('saved entities expose identity, location and evidence state without hover', () => {
  assert.match(map, /\[rosterOpen, setRosterOpen\] = useState\(false\)/);
  assert.match(map, /infrastructureEntityLabel\(entity\)/);
  assert.match(map, /entity\.evidenceState/);
  assert.match(map, /aria-pressed=\{/);
  assert.match(map, /Unlocated intelligence/);
});

test('retained built-world objects share layer visibility and inspection state', () => {
  assert.match(map, /id={`map-built-\${layer\.id}`}/);
  assert.match(map, /setLayerHidden\(`built:\${layer\.id}`, !value\)/);
  assert.match(map, /queryRenderedFeatures\(e\.point/);
  assert.match(map, /setFeatureState\(feature, \{ selected: true \}\)/);
  assert.match(map, /source: SOURCE_IDS\.infrastructure/);
  assert.match(map, /type: 'fill-extrusion'/);
  assert.match(map, /\['==', \['get', 'height_backed'\], true\]/);
  assert.match(map, /buildingFlatLine: 'terrene-buildings-flat-line'/);
  assert.match(map, /'line-dasharray': \[2, 1\]/);
  assert.match(map, /onInspectMapObject\?\.\(objectId\)/);
  assert.match(map, /onClearMapObject\?\.\(\)/);
  assert.doesNotMatch(map, /DOMPoint|isPointInFill|data-map-object/);
  assert.match(map, /\{draw && \([\s\S]*className="geography-overlay"/);
});
