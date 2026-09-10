import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, map, css] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/portfolio-map.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
]);

function layer(name) {
  const match = css.match(new RegExp(`--portfolio-layer-${name}:\\s*(\\d+)`));
  assert.ok(match, `missing portfolio layer ${name}`);
  return Number(match[1]);
}

test('portfolio application chrome is above all geographic content', () => {
  const geography = layer('geography');
  const locators = layer('locators');
  const mapControls = layer('map-controls');
  const appChrome = layer('app-chrome');

  assert.ok(geography < locators);
  assert.ok(locators < mapControls);
  assert.ok(mapControls < appChrome);
  assert.match(
    css,
    /\.portfolio-boundaries\s*\{[^}]*var\(--portfolio-layer-geography\)/s,
  );
  assert.match(
    css,
    /\.portfolio-pins\s*\{[^}]*var\(--portfolio-layer-locators\)/s,
  );
  assert.match(
    css,
    /\.portfolio-context,[\s\S]*\.maplibregl-ctrl-top-right\s*\{[^}]*var\(--portfolio-layer-map-controls\)/,
  );
  assert.match(
    css,
    /\.portfolio-main \.sites-view-bar\s*\{[^}]*var\(--portfolio-layer-app-chrome\)/s,
  );
});

test('drawing map is part of the stable client module graph', () => {
  assert.match(page, /import SiteMap from '\.\/map';/);
  assert.doesNotMatch(page, /dynamic\(\(\) => import\('\.\/map'\)/);
  assert.match(page, /<SiteMap[\s\S]*?\bdraw\b[\s\S]*?onDraw=/);
});

test('portfolio raster treatment stays scoped and restrained', () => {
  assert.match(map, /'raster-opacity': 0\.7/);
  assert.match(map, /'raster-contrast': -0\.12/);
  assert.match(css, /\.portfolio-canvas \.maplibregl-canvas\s*\{[^}]*contrast\(0\.58\)/s);
  assert.doesNotMatch(css, /\.map-wrap \.maplibregl-canvas[^}]*filter/s);
});

test('saved locators expose site name, area, and status beyond hover', () => {
  assert.match(map, /aria-describedby=\{`portfolio-pin-context-/);
  assert.match(map, /onFocus=\{\(\) => setHovered\(site\.id\)\}/);
  assert.match(map, /hovered === site\.id \|\| selected === site\.id/);
  assert.match(map, /\{siteArea\(site\)\}[\s\S]*\{site\.status\}/);
});
