import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [globalCss, shellCss, mapCss, dossierCss] = await Promise.all([
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
  readFile(
    new URL('../app/infrastructure-map.module.css', import.meta.url),
    'utf8',
  ),
  readFile(
    new URL('../app/entity-dossier.module.css', import.meta.url),
    'utf8',
  ),
]);
const operatingCss = [globalCss, shellCss, mapCss, dossierCss].join('\n');

test('operating typography uses one readable semantic scale', () => {
  assert.match(globalCss, /--font-size-micro: 0\.6875rem;/);
  assert.match(globalCss, /--font-size-title: 1\.25rem;/);
  assert.match(globalCss, /--font-size-display: 1\.625rem;/);
  assert.doesNotMatch(
    operatingCss,
    /font-size:\s*(?:10px|11px|0?\.(?:5|5625|625|65|6875|7)rem)/,
  );
  assert.match(
    dossierCss,
    /\.kind \{[\s\S]*?font-size: var\(--font-size-micro\)/,
  );
  assert.match(
    globalCss,
    /\.brief-section > h3 \{[^}]*font-size: var\(--font-size-lg\)/,
  );
  assert.match(
    shellCss,
    /@media \(max-width: 74rem\)[\s\S]*?\.viewIdentity span \{[\s\S]*?display: none;/,
  );
});

test('secondary state text and keyboard states remain readable', () => {
  assert.match(globalCss, /--text-tertiary: #89978f;/);
  assert.match(globalCss, /--status-warning: #d0a45c;/);
  assert.match(globalCss, /--status-danger: #e08a80;/);
  assert.match(globalCss, /button:disabled \{[\s\S]*?opacity: 0\.62;/);
  assert.match(
    globalCss,
    /\[role='tab'\]:focus-visible,[\s\S]*?summary:focus-visible,[\s\S]*?outline: 2px solid var\(--focus-ring\)/,
  );
  assert.match(
    globalCss,
    /\.brief-rows > button:hover,[\s\S]*?\.brief-rows > button:focus-visible,[\s\S]*?background: var\(--surface-selected\)/,
  );
});

test('high-frequency dossier spacing follows the shared rhythm', () => {
  assert.match(
    globalCss,
    /\.screening-overview \{ padding: var\(--space-5\) var\(--space-5\) var\(--space-6\); \}/,
  );
  assert.match(
    globalCss,
    /\.brief-rows > button,[\s\S]*?gap: var\(--space-4\);[\s\S]*?padding: var\(--space-3\) 0;/,
  );
  assert.match(
    globalCss,
    /\.evidence-register-overview \{[\s\S]*?margin-top: var\(--space-5\);[\s\S]*?padding: var\(--space-4\);[\s\S]*?border-radius: var\(--radius-panel\);/,
  );
});

test('operator surfaces use a restrained shared radius scale', () => {
  assert.match(globalCss, /--radius-small: 0\.375rem;/);
  assert.match(globalCss, /--radius-control: 0\.5rem;/);
  assert.match(globalCss, /--radius-panel: 0\.75rem;/);
  assert.match(
    shellCss,
    /\.navigation button[\s\S]*?border-radius: var\(--radius-control\)/,
  );
  assert.match(
    shellCss,
    /\.searchResults \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(
    mapCss,
    /\.roster \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(
    mapCss,
    /\.legendPanel \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
});

test('desktop dossier is an inset operator surface and mobile remains a bottom sheet', () => {
  assert.match(
    shellCss,
    /\.spatial-main > \.entity-dossier\)[\s\S]*?top: calc\(var\(--topbar-height\) \+ 0\.75rem\);[\s\S]*?right: 0\.75rem;[\s\S]*?bottom: 0\.75rem;[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(
    shellCss,
    /@media \(max-width: 47\.5rem\)[\s\S]*?\.spatial-main > \.entity-dossier\)[\s\S]*?top: 42%;[\s\S]*?right: 0;[\s\S]*?bottom: 0;/,
  );
  assert.match(dossierCss, /\.dossier \{[\s\S]*?border-radius: inherit;/);
});

test('semantic pills and analytical tabs retain their distinct geometry', () => {
  assert.match(
    globalCss,
    /\.evidence-status-line span \{[\s\S]*?border-radius: 999px;/,
  );
  assert.match(globalCss, /\.model-tabs \{[\s\S]*?border-radius: 0;/);
  assert.match(globalCss, /\.model-tabs button \{[\s\S]*?border-radius: 0;/);
  assert.match(
    globalCss,
    /\.intelligence-tabs \{[\s\S]*?border-radius: 0 !important;/,
  );
});

test('list navigation stays dark with restrained selected and focus states', () => {
  assert.match(
    shellCss,
    /\.portfolio-list-main \.sites-view-bar \[role='tablist'\][\s\S]*?background: #151d1a/,
  );
  assert.match(
    shellCss,
    /\.portfolio-list-main \.sites-view-bar \[role='tab'\]\[data-active\][\s\S]*?background: #26322d/,
  );
  assert.match(
    shellCss,
    /\.portfolio-list-main \.sites-view-bar \[role='tab'\]:focus-visible[\s\S]*?outline-offset: 1px/,
  );
});
