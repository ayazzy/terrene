import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  infrastructureEntityLabel,
  linkedSiteDisplayAnchor,
  projectInfrastructureEntities,
  searchableInfrastructureEntities,
} from '../app/infrastructure-entities.ts';

const boundary = {
  type: 'Polygon',
  coordinates: [
    [
      [-1.3, 51.7],
      [-1.2, 51.7],
      [-1.2, 51.8],
      [-1.3, 51.7],
    ],
  ],
};
const sites = [
  {
    id: 'site-linked',
    name: 'North site',
    status: 'Investigate',
    version: 3,
    geometry: boundary,
    assessment: { state: 'completed' },
  },
  {
    id: 'site-only',
    name: 'South site',
    status: 'Hold',
    version: 1,
    geometry: boundary,
    assessment: null,
  },
];
const subjects = [
  {
    id: 'project-linked',
    org: 'org',
    name: 'Linked project',
    project_type: 'solar',
    site_id: 'site-linked',
    content_hash: 'a',
    created: '2026-01-01',
  },
  {
    id: 'beacon-fen',
    org: 'org',
    name: 'Beacon Fen Energy Park',
    project_type: 'solar',
    site_id: null,
    content_hash: 'b',
    created: '2026-01-01',
  },
  {
    id: 'broken-link',
    org: 'org',
    name: 'Unavailable linked site',
    project_type: 'rail',
    site_id: 'not-authorized',
    content_hash: 'c',
    created: '2026-01-01',
  },
];

test('Project Subjects receive geography only from an exact authorized Site relationship', () => {
  const entities = projectInfrastructureEntities(sites, subjects, {
    'project-linked': [{ id: 'run-1' }],
  });
  const linked = entities.find((entity) => entity.id === 'project-linked');
  const beacon = entities.find((entity) => entity.id === 'beacon-fen');
  const broken = entities.find((entity) => entity.id === 'broken-link');
  assert.equal(linked.locationState, 'site_linked');
  assert.equal(linked.geometry, boundary);
  assert.equal(linked.linkedSite.id, 'site-linked');
  assert.equal(linked.evidenceState, '1 intelligence run');
  assert.equal(beacon.locationState, 'unlocated');
  assert.equal(beacon.geometry, null);
  assert.equal(
    infrastructureEntityLabel(beacon),
    'Project Subject · No verified geography',
  );
  assert.equal(broken.locationState, 'linked_site_unavailable');
  assert.equal(broken.geometry, null);
});

test('entity search spans type, evidence and location state without geocoding names', () => {
  const entities = projectInfrastructureEntities(sites, subjects);
  assert.deepEqual(
    searchableInfrastructureEntities(entities, 'Beacon').map(
      (entity) => entity.id,
    ),
    ['beacon-fen'],
  );
  assert.deepEqual(
    searchableInfrastructureEntities(entities, 'No verified geography').map(
      (entity) => entity.id,
    ),
    ['beacon-fen'],
  );
  assert.equal(
    entities.find((entity) => entity.id === 'beacon-fen').geometry,
    null,
  );
  assert.deepEqual(linkedSiteDisplayAnchor(boundary), [-1.25, 51.75]);
  assert.equal(linkedSiteDisplayAnchor(null), null);
});

test('one primary map owns Sites, linked projects, unlocated roster and evidence layers', async () => {
  const [page, map] = await Promise.all([
    readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
    readFile(new URL('../app/map.tsx', import.meta.url), 'utf8'),
  ]);
  assert.doesNotMatch(page, /import\('\.\/portfolio-map'\)|<PortfolioMap/);
  assert.equal(
    (page.match(/<SiteMap/g) || []).length,
    2,
    'one primary map plus the isolated boundary editor',
  );
  assert.doesNotMatch(page, /key=\{assessment\?\.id \|\| current\.id\}/);
  assert.match(map, /data-primary-map="infrastructure-operating-picture"/);
  assert.match(
    map,
    /ResizeObserver[\s\S]*geometryRef\.current[\s\S]*fit\(geometryRef\.current\)/,
  );
  assert.match(map, /Unlocated intelligence/);
  assert.match(map, /project-subjects/);
  assert.match(map, /environment:/);
  assert.match(map, /built:/);
});

test('clicking a rendered Site opens its dossier instead of only selecting its outline', async () => {
  const page = await readFile(
    new URL('../app/page.tsx', import.meta.url),
    'utf8',
  );
  assert.match(
    page,
    /onSelectEntity=\{\(selection\) => \{[\s\S]*?openInfrastructureEntity\(entity\);[\s\S]*?\}\}/,
  );
  assert.doesNotMatch(
    page,
    /if \(view === 'workspace'\)[\s\S]*?operatingPicture\.selectEntity\(selection, 'map'\)/,
  );
});
