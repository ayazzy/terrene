import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, shell, shellCss, css] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/operating-shell.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
]);

test('operating rail has one React-owned compact state and defaults narrow', () => {
  assert.match(
    page,
    /navigationCompact, setNavigationCompact\] = useState\(true\)/,
  );
  assert.match(page, /<OperatingRail[\s\S]*compact=\{navigationCompact\}/);
  assert.match(
    page,
    /onCompactChange=\{\(\) =>[\s\S]*setNavigationCompact\(\(value\) => !value\)/,
  );
  assert.match(shellCss, /--sidebar-compact: 3\.75rem/);
  assert.doesNotMatch(
    css,
    /\.crc-shell:has\(\.analysis-main\)[^{]*\{[^}]*--sidebar-width/s,
  );
  assert.doesNotMatch(
    css,
    /\.crc-shell:has\(\.analysis-main\)[^{]*(?:\.brand-wordmark|\.nav-text|\.sidebar-note|footer)/s,
  );
});

test('rail toggle and compact navigation remain labelled without visible text', () => {
  assert.equal((shell.match(/'Expand navigation'/g) || []).length, 2);
  assert.equal((shell.match(/'Collapse navigation'/g) || []).length, 2);
  assert.match(shell, /aria-controls="primary-navigation"/);
  assert.match(shell, /aria-expanded=\{!compact\}/);
  assert.match(shell, /mobileOpen \? \([\s\S]*<X \/>/);
  assert.match(shell, /compact \? \([\s\S]*<PanelLeftOpen \/>/);
  assert.match(shell, /aria-label=\{item\.label\}/);
  assert.match(shellCss, /button:focus-visible::after/);
});

test('narrow navigation opens and closes with deterministic focus', () => {
  assert.match(shell, /if \(event\.key === 'Escape'\) onMobileClose\(\)/);
  assert.match(shell, /closeButton\.current\?\.focus\(\)/);
  assert.match(shell, /mobileMenuButton\.current\?\.focus\(\)/);
  assert.match(shell, /aria-expanded=\{mobileNavigationOpen\}/);
  assert.match(page, /onMobileClose=\{closeMobileNavigation\}/);
});

test('dossier collapse and reopen preserve keyboard focus', () => {
  assert.match(page, /dossierFocusIntent\.current = 'reopen'/);
  assert.match(page, /reopenAnalysisButton\.current\?\.focus\(\)/);
  assert.match(page, /dossierFocusIntent\.current = 'close'/);
  assert.match(page, /analysisCloseButton\.current\?\.focus\(\)/);
  assert.match(
    page,
    /ref=\{reopenAnalysisButton\}[\s\S]*onClick=\{reopenSitePanel\}/,
  );
  assert.match(
    page,
    /ref=\{analysisCloseButton\}[\s\S]*onClick=\{collapseSitePanel\}/,
  );
});
