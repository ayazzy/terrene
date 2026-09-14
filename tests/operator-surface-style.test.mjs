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
