import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, project, dossier, map, shell, mapCss] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/project-intelligence-workspace.tsx', import.meta.url),
    'utf8',
  ),
  readFile(new URL('../app/entity-dossier.tsx', import.meta.url), 'utf8'),
  readFile(new URL('../app/map.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/operating-shell.module.css', import.meta.url),
    'utf8',
  ),
  readFile(
    new URL('../app/infrastructure-map.module.css', import.meta.url),
    'utf8',
  ),
]);

test('Sites and Project Subjects use one docked entity dossier contract', () => {
  assert.match(page, /<EntityDossier\s+className="site-workspace"/);
  assert.match(
    project,
    /<EntityDossier\s+className="project-intelligence-workspace"/,
  );
  assert.match(dossier, /data-entity-dossier=/);
  assert.match(dossier, /HistoryState/);
  assert.match(dossier, /aria-hidden=\{!open\}/);
  assert.match(shell, /> \.entity-dossier\.dossier-collapsed/);
});

test('the project dossier relies on the shared map roster instead of a duplicate selector', () => {
  assert.doesNotMatch(project, /className="subject-list"/);
  assert.match(project, /TERRENE CONCLUSION/);
  assert.match(project, /SOURCE ASSERTIONS/);
  assert.match(project, /IMMUTABLE RUN HISTORY/);
});

test('both dossiers expose map layers while controlled layer state stays on the persistent map', () => {
  assert.match(page, /layersOpen=\{mapLayersOpen\}/);
  assert.match(page, /onLayersOpenChange=\{setMapLayersOpen\}/);
  assert.match(page, /onOpenLayers=\{\(\) => setMapLayersOpen\(true\)\}/g);
  assert.match(map, /const layerPanelOpen = layersOpen \?\? localLayersOpen/);
  assert.match(map, /setRosterOpen\(false\);[\s\S]*setLegendOpen\(false\)/);
  assert.match(map, /rosterOpen &&[\s\S]*!layerPanelOpen &&[\s\S]*!legendOpen/);
  assert.match(mapCss, /\.legendPanel\s*\{/);
});

test('collapse preserves the entity and immutable artifact URL state', () => {
  assert.match(page, /Open entity dossier/);
  assert.match(page, /onCollapse=\{collapseSitePanel\}/g);
  assert.match(dossier, /onClick=\{onCollapse\}/);
  assert.doesNotMatch(
    dossier,
    /onSubjectChange|onRunChange|onAssessmentChange/,
  );
});

test('project conclusions and questions navigate to exact retained assertions', () => {
  assert.match(project, /setFocusedClaimId\(claimId\)/);
  assert.match(project, /onSectionChange\('evidence'\)/);
  assert.match(project, /data-project-claim=\{item\.claim\.id\}/);
  assert.match(project, /exact_passage/);
  assert.match(project, /source_record_id/);
  assert.match(project, /source_version/);
});
