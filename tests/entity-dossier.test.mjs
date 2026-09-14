import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [page, project, dossier, dossierCss, map, shell, mapCss] =
  await Promise.all([
    readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
    readFile(
      new URL('../app/project-intelligence-workspace.tsx', import.meta.url),
      'utf8',
    ),
    readFile(new URL('../app/entity-dossier.tsx', import.meta.url), 'utf8'),
    readFile(
      new URL('../app/entity-dossier.module.css', import.meta.url),
      'utf8',
    ),
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
  assert.match(
    page,
    /onOpenLayers=\{\(\) => setMapLayersOpen\(\(open\) => !open\)\}/g,
  );
  assert.match(dossier, /aria-expanded=\{layersOpen\}/);
  assert.match(dossier, /aria-controls="map-layers"/);
  assert.match(map, /const layerPanelOpen = layersOpen \?\? localLayersOpen/);
  assert.match(map, /setRosterOpen\(false\);[\s\S]*setLegendOpen\(false\)/);
  assert.match(map, /rosterOpen &&[\s\S]*!layerPanelOpen &&[\s\S]*!legendOpen/);
  assert.match(mapCss, /\.legendPanel\s*\{/);
});

test('site analysis navigation stays above the optional object inspector', () => {
  const analysisTabs = page.indexOf('aria-label="Site analysis sections"');
  const objectInspector = page.indexOf('<MapFeatureInspector', analysisTabs);
  assert.notEqual(analysisTabs, -1);
  assert.notEqual(objectInspector, -1);
  assert.ok(analysisTabs < objectInspector);
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

test('the dossier owns one bounded scroll chain and cannot shrink its identity header', () => {
  assert.match(dossier, /className=\{`\$\{styles\.dossier\} entity-dossier/);
  assert.match(dossierCss, /\.dossier\s*\{[\s\S]*?display:\s*flex/);
  assert.match(dossierCss, /\.header\s*\{[\s\S]*?flex:\s*0 0 auto/);
  assert.match(
    dossierCss,
    /\.body\s*\{[\s\S]*?flex:\s*1 1 auto[\s\S]*?overflow:\s*auto/,
  );
  assert.match(
    dossierCss,
    /\.body > :global\(\.investigation\)\s*\{[\s\S]*?flex:\s*1 1 0[\s\S]*?min-height:\s*0[\s\S]*?overflow:\s*hidden/,
  );
  assert.match(
    dossierCss,
    /\.body :global\(\.findings-panel\)\s*\{[\s\S]*?height:\s*100%[\s\S]*?overflow-y:\s*auto/,
  );
});

test('dossier layout responds to its own width and uses one content gutter', () => {
  assert.match(dossierCss, /container-name:\s*entity-dossier/);
  assert.match(
    dossierCss,
    /@container entity-dossier \(max-width: 42rem\)[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\)/,
  );
  assert.match(
    dossierCss,
    /@container entity-dossier \(max-width: 42rem\)[\s\S]*?\.map-feature-inspector-body[\s\S]*?flex-direction:\s*column/,
  );
  assert.match(dossierCss, /--dossier-gutter:\s*1rem/);
  assert.match(
    dossierCss,
    /\.dossier:global\(\.site-workspace\) \.identity\s*\{\s*padding-right:\s*10rem/,
  );
});
