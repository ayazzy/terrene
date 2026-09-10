import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, css] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
]);

test('desktop sidebar presentation has one React-owned compact state', () => {
  assert.match(
    page,
    /className={`crc-shell\$\{navigationCompact \? ' nav-compact' : ''\}/,
  );
  assert.match(
    page,
    /onClick=\{\(\) => setNavigationCompact\(\(value\) => !value\)\}/,
  );
  assert.doesNotMatch(
    css,
    /\.crc-shell:has\(\.analysis-main\)[^{]*\{[^}]*--sidebar-width/s,
  );
  assert.doesNotMatch(
    css,
    /\.crc-shell:has\(\.analysis-main\)[^{]*(?:\.brand-wordmark|\.nav-text|\.sidebar-note|footer)/s,
  );
});

test('sidebar toggle exposes the current action and expanded state', () => {
  assert.equal((page.match(/'Expand sidebar'/g) || []).length, 2);
  assert.equal((page.match(/'Collapse sidebar'/g) || []).length, 2);
  assert.match(page, /aria-controls="primary-navigation"/);
  assert.match(page, /aria-expanded=\{!navigationCompact\}/);
  assert.match(
    page,
    /navigationCompact \? <PanelLeftOpen \/> : <PanelLeftClose \/>/,
  );
});
