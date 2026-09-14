import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [page, css, shellCss] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
]);

test('portfolio list has a dedicated intelligence-led visual hierarchy', () => {
  assert.match(page, /portfolio-list-main/);
  assert.match(page, /Infrastructure site roster/);
  assert.match(page, /aria-label="Portfolio summary"/);
  assert.match(page, /Screening protocol/);
  assert.match(page, /className="portfolio-status-strip"/);
  assert.doesNotMatch(page, /className="portfolio-list-hero"/);
  assert.match(shellCss, /:global\(\.portfolio-status-strip\)/);
  assert.match(shellCss, /:global\(\.portfolio-summary\)[^{]*\{/);
  assert.match(css, /\.portfolio-site-table tbody tr\[data-selected='true'\]/);
  assert.match(page, /className="site-locator"[\s\S]*aria-hidden="true"/);
  assert.match(css, /\.portfolio-site-table \.site-locator \{/);
  assert.doesNotMatch(css, /\.portfolio-site-table \.site-icon/);
});

test('portfolio ledger keeps evidence and team state distinct', () => {
  assert.match(page, /Evidence coverage/);
  assert.match(page, /Screening state/);
  assert.match(page, /Team review/);
  assert.match(page, /Reference-layer coverage unknown/);
  assert.match(page, /className="coverage-track"/);
  assert.match(page, /<Status[\s\S]*value=\{s\.status\}/);
  assert.match(
    page,
    /Screening states describe geographic observations and[\s\S]*Review decisions remain[\s\S]*team-owned/,
  );
});

test('portfolio comparison and site navigation remain available', () => {
  assert.match(page, /disabled=\{compare\.length < 2\}/);
  assert.match(page, /compare\.length >= 3/);
  assert.match(page, /aria-label=\{'Open ' \+ s\.name\}/);
  assert.match(page, /onClick=\{\(\) => openSite\(s\)\}/);
  assert.match(css, /@media \(max-width: 74rem\)[\s\S]*nth-child\(7\)/);
});
