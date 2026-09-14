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

test('boundary drawing reuses the stable primary map module', () => {
  assert.match(page, /import SiteMap from '\.\/map';/);
  assert.doesNotMatch(page, /dynamic\(\(\) => import\('\.\/map'\)/);
  assert.equal((page.match(/<SiteMap/g) || []).length, 1);
  assert.match(page, /draw=\{newSite && drawing\}/);
  assert.match(page, /drawSession=\{drawSession\}/);
  assert.match(page, /boundaryEditing=\{newSite\}/);
  assert.doesNotMatch(page, /draw-screen|site-dialog/);
});

test('the primary map prefers a dark vector style with a legacy raster fallback', () => {
  assert.match(map, /NEXT_PUBLIC_BASEMAP_STYLE_URL/);
  assert.match(map, /https:\/\/tiles\.openfreemap\.org\/styles\/dark/);
  assert.match(map, /NEXT_PUBLIC_BASEMAP_URL/);
  assert.match(map, /productionConfigurationMissing: true/);
  assert.doesNotMatch(
    mapCss,
    /maplibregl-canvas[^}]*filter:\s*(?:grayscale|invert)/s,
  );
  assert.doesNotMatch(mapCss, /portfolio-canvas|portfolio-map/);
});

test('a failed remote basemap falls back without suppressing Terrene evidence', () => {
  assert.match(map, /EVIDENCE_ONLY_DARK_STYLE/);
  assert.match(map, /m\.on\('style\.load', handleStyleLoad\)/);
  assert.match(
    map,
    /m\.setStyle\(EVIDENCE_ONLY_DARK_STYLE, \{ diff: false \}\)/,
  );
  assert.match(map, /setMissingStyleImageResolver/);
  assert.match(map, /data-basemap-state=\{basemapState\}/);
  assert.match(map, /Evidence geometry remains visible/);
  assert.match(map, /Initialising spatial evidence/);
  assert.match(
    mapCss,
    /\.mapNotice\s*\{[\s\S]*?width: min\(28rem, calc\(100% - 5rem\)\)[\s\S]*?pointer-events: none/,
  );
});

test('collapsed dossier access stays inside the Terrene toolbar', () => {
  assert.match(map, /<div className="map-toolbar">[\s\S]*?onOpenDossier/);
  assert.match(page, /openDossierButtonRef=\{reopenAnalysisButton\}/);
  assert.doesNotMatch(page, /operating-map-reopen|reopen-analysis/);
  assert.doesNotMatch(shellCss, /operating-map-reopen/);
});

test('scene status keeps missing, partial, and historical evidence explicit', () => {
  assert.match(map, /buildingHeightStateCounts\(mapScene\)/);
  assert.match(map, /buildingHeightStatus\(heightCounts\)/);
  assert.match(
    map,
    /Infrastructure evidence unavailable\. Missing data is not zero/,
  );
  assert.match(map, /Current objects were not substituted/);
  assert.match(map, /No persisted infrastructure evidence is stored/);
  assert.match(mapCss, /\.sceneStatus\[data-state='partial'\]/);
});

test('operator controls preserve 2D truth and mutually exclusive left surfaces', () => {
  assert.match(
    map,
    /\[perspectiveSceneId, setPerspectiveSceneId\] = useState<string \| null>\(null\)/,
  );
  assert.match(map, /perspectiveSceneId === mapScene\?\.snapshot\.id/);
  assert.match(map, /pitch: perspectiveActive \? 55 : 0/);
  assert.match(map, /!perspectiveActive/);
  assert.match(map, /heightAvailableCount > 0/);
  assert.match(map, /id="map-legend"/);
  assert.match(map, /Objects in this snapshot/);
  assert.match(map, /Repeated classifications/);
  assert.match(map, /Retrieved \{sourceDate\(source\.retrieved_at\)\}/);
  assert.match(map, /className: 'terrene-map-hover'/);
});

test('map orientation is available without reaching controls behind the dossier', () => {
  assert.match(map, /dragRotate: true/);
  assert.match(map, /pitchWithRotate: true/);
  assert.match(map, /touchPitch: true/);
  assert.match(map, /aria-label="Rotate map anticlockwise"/);
  assert.match(map, /aria-label="Reset map to north"/);
  assert.match(map, /aria-label="Rotate map clockwise"/);
  assert.match(
    shellCss,
    /entity-dossier:not\(\.dossier-collapsed\)\) \.map-toolbar[\s\S]*?max-width: calc\(52% - 1\.5rem\)[\s\S]*?flex-wrap: wrap/,
  );
});

test('opening the dossier re-centres the Site inside the visible map canvas', () => {
  assert.match(page, /dossierOpen=\{/);
  assert.match(map, /dossierOpenRef = useRef\(dossierOpen\)/);
  assert.match(map, /\.entity-dossier:not\(\.dossier-collapsed\)/);
  assert.match(map, /right: sideDockOverlap \+ 48/);
  assert.match(map, /\[dossierOpen, fit, ready\]/);
});

test('map footer context surfaces use one aligned height', () => {
  assert.match(map, /className="map-boundary-title"/);
  assert.match(
    mapCss,
    /\.operatingMap \.workflowPath\s*\{[\s\S]*?height:\s*4\.25rem/,
  );
  assert.match(
    mapCss,
    /\.operatingMap :global\(\.map-boundary-label\)\s*\{[\s\S]*?bottom:\s*1\.75rem[\s\S]*?height:\s*4\.25rem/,
  );
});

test('object roster distinguishes retained objects without a selected perimeter', () => {
  assert.match(map, /`\$\{label\} \$\{position\} of \$\{total\}`/);
  assert.match(
    mapCss,
    /\.legendObjects button\[aria-pressed='true'\][\s\S]*?border-color:\s*transparent/,
  );
});

test('perspective visibility is synchronized while the map camera is moving', () => {
  const visibilityEffect = map.match(
    /useEffect\(\(\) => \{\s+const currentMap = map\.current;\s+if \(!ready \|\| !currentMap\) return;[\s\S]*?NATIVE_LAYER_IDS\.buildingExtrusion,[\s\S]*?!perspectiveActive,[\s\S]*?\}, \[hiddenLayerSet, ready, projection, perspectiveActive\]\);/,
  );
  assert.ok(
    visibilityEffect,
    'expected the scene visibility synchronization effect',
  );
  assert.match(
    visibilityEffect[0],
    /if \(currentMap\.isStyleLoaded\(\)\) synchronizeVisibility\(\);\s+else currentMap\.once\('idle', synchronizeVisibility\);/,
  );
  assert.match(
    visibilityEffect[0],
    /return \(\) => \{\s+currentMap\.off\('idle', synchronizeVisibility\);\s+\};/,
  );
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
