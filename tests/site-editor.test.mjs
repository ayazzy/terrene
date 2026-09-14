import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, map, editor, globals, shellCss] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/map.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/site-editor-panel.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
]);

test('Add site opens a contextual editor over the one persistent map', () => {
  assert.match(
    page,
    /onAddSite=\{[\s\S]*?view === 'workspace' && !newSite[\s\S]*?startNew/,
  );
  assert.match(map, /<Plus size=\{16\} \/> Add site/);
  assert.match(page, /<SiteEditorPanel[\s\S]*?editing=\{editing\}/);
  assert.equal((page.match(/<SiteMap/g) || []).length, 1);
  assert.match(editor, /data-map-reserved-surface="right"/);
  assert.match(
    editor,
    /Define the Site while keeping its geographic context visible/,
  );
  assert.doesNotMatch(page, /<Dialog[^>]*open=\{newSite\}|draw-screen/);
});

test('new Site drafts clear prior identity and remain unsaved until submit', () => {
  assert.match(
    page,
    /function startNew\(\)[\s\S]*?mode: 'map',[\s\S]*?selection: null,[\s\S]*?artifact: null,[\s\S]*?assetId: null,[\s\S]*?setNewSite\(true\)/,
  );
  assert.match(page, /editing \? 'PATCH' : 'POST'/);
  assert.match(page, /expected_version: current\.version/);
  assert.match(
    editor,
    /onSubmit=\{\(event\) => \{[\s\S]*?event\.preventDefault\(\);[\s\S]*?onSave\(\)/,
  );
  assert.match(
    editor,
    /disabled=\{busy \|\| !name\.trim\(\) \|\| !boundaryReady\}/,
  );
});

test('drawing sessions cannot leak vertices between redraw attempts', () => {
  assert.match(page, /setDrawSession\(\(session\) => session \+ 1\)/);
  assert.match(map, /drawSessionRef\.current = drawSession/);
  assert.match(
    map,
    /current\.session === drawSessionRef\.current[\s\S]*?current\.points[\s\S]*?: \[\]/,
  );
  assert.match(
    map,
    /draftVertices\.session === drawSession \? draftVertices\.points : \[\]/,
  );
});

test('cancelling a new draft restores the portfolio camera', () => {
  assert.match(
    map,
    /if \(geometry\) fit\(geometry\);[\s\S]*?else if \(entities\.length && !selectedEntity\) fitAllEntities\(\)/,
  );
});

test('the editor reserves map space and becomes a bottom sheet on narrow screens', () => {
  assert.match(globals, /\.site-creation-body\s*\{[^}]*overflow-y:\s*auto/s);
  assert.match(
    shellCss,
    /\.spatial-main > \.site-creation-panel\)[^}]*position: absolute[^}]*right: 0\.75rem[^}]*bottom: 0\.75rem/s,
  );
  assert.match(
    shellCss,
    /@media \(max-width: 47\.5rem\)[\s\S]*?\.spatial-main > \.site-creation-panel\)[\s\S]*?top: 42%[\s\S]*?width: 100%/,
  );
  assert.match(
    map,
    /\[data-map-reserved-surface="right"\][\s\S]*?sideDockOverlap[\s\S]*?bottomDockOverlap[\s\S]*?right: sideDockOverlap \+ 48/,
  );
});
