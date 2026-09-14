import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  buildingHeightStateCounts,
  buildingHeightStatus,
  infrastructureMapScenePath,
  mapLayerStatus,
  mapRelationshipSummary,
  readInfrastructureMapScene,
} from '../app/infrastructure-map-scene.ts';

const run = {
  id: 'screening-run-1',
  site_id: 'site-1',
  boundary_version: 2,
  evidence_snapshot_id: 'snapshot/immutable',
  result: {
    evidence_content_hash: 'content-hash',
    boundary_geometry_fingerprint: 'boundary-hash',
  },
};

function scene(overrides = {}) {
  return {
    type: 'FeatureCollection',
    contract_version: 'infrastructure_map_scene_v1',
    snapshot: {
      id: run.evidence_snapshot_id,
      schema_version: 'land_evidence_v1',
      registry_version: 'land_evidence_registry_v4',
      content_hash: run.result.evidence_content_hash,
      created: '2026-09-14T10:00:00Z',
    },
    site: { id: run.site_id, name: 'Oxford Station', geography: 'England' },
    boundary: {
      version: run.boundary_version,
      reference: 'site-1/boundary/2',
      geometry_fingerprint: run.result.boundary_geometry_fingerprint,
      authoritative_crs: 'EPSG:27700',
    },
    evidence_as_of: '2026-09-14T10:00:00Z',
    presentation_crs: 'EPSG:4326',
    authoritative_geometry_crs: 'EPSG:27700',
    sources: [],
    layers: [],
    capabilities: [],
    features: [],
    limitations: [],
    ...overrides,
  };
}

function mockRequest(t, value) {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    calls.push({ path, options });
    return Response.json(value);
  });
  const prior = globalThis.sessionStorage;
  globalThis.sessionStorage = { getItem: () => 'scene-token' };
  t.after(() => {
    if (prior) globalThis.sessionStorage = prior;
    else delete globalThis.sessionStorage;
  });
  return calls;
}

test('native scene is read by immutable snapshot identity and fails closed', async (t) => {
  const calls = mockRequest(t, scene());
  const result = await readInfrastructureMapScene(run);
  assert.equal(result.snapshot.id, run.evidence_snapshot_id);
  assert.equal(
    calls[0].path,
    '/api/land-evidence-snapshots/snapshot%2Fimmutable/map-scene',
  );
  assert.equal(calls[0].options.headers.Authorization, 'Bearer scene-token');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(
    infrastructureMapScenePath(run.evidence_snapshot_id),
    calls[0].path,
  );

  t.mock.method(globalThis, 'fetch', async () =>
    Response.json(
      scene({
        snapshot: { ...scene().snapshot, content_hash: 'changed' },
      }),
    ),
  );
  await assert.rejects(
    readInfrastructureMapScene(run),
    /does not match the selected immutable evidence snapshot/,
  );
});

test('native scene helpers preserve layer and relationship semantics', () => {
  const layer = { feature_count: 2 };
  assert.equal(
    mapLayerStatus({ ...layer, state: 'available' }),
    '2 mapped objects',
  );
  assert.match(
    mapLayerStatus({ ...layer, feature_count: 0, state: 'mapped_zero' }),
    /Mapped zero · source-bounded/,
  );
  assert.match(
    mapRelationshipSummary({
      predicate: 'contained_within',
      measurements: {
        overlap_area_m2: 100,
        parcel_overlap_fraction: 0.25,
        object_overlap_fraction: 1,
        length_within_m: null,
        minimum_distance_m: null,
      },
    }),
    /Contained within the parcel · 100 m² overlap · 25% of parcel · 100% of object/,
  );
});

test('height presentation distinguishes partial, missing, and historical evidence', () => {
  const heightScene = scene({
    features: [
      { properties: { layer_id: 'buildings', height: { state: 'available' } } },
      { properties: { layer_id: 'buildings', height: { state: 'partial' } } },
      { properties: { layer_id: 'buildings', height: { state: 'gap' } } },
      {
        properties: { layer_id: 'buildings', height: { state: 'unsupported' } },
      },
      { properties: { layer_id: 'buildings', height: null } },
      { properties: { layer_id: 'railway_tracks', height: null } },
    ],
  });
  const counts = buildingHeightStateCounts(heightScene);
  assert.deepEqual(counts, {
    available: 1,
    partial: 1,
    gap: 1,
    unsupported: 1,
    unrecorded: 1,
  });
  assert.equal(
    buildingHeightStatus(counts),
    'Partial height coverage · 2 evidence-backed · 3 flat',
  );
  assert.equal(
    buildingHeightStatus({
      available: 4,
      partial: 1,
      gap: 0,
      unsupported: 0,
      unrecorded: 0,
    }),
    'Partial evidence · 1 of 5 building estimates has a partial state',
  );
  assert.match(
    buildingHeightStatus({
      available: 0,
      partial: 0,
      gap: 0,
      unsupported: 3,
      unrecorded: 0,
    }),
    /Historical snapshot · 3 buildings remain flat.*unsupported/,
  );
  assert.match(
    buildingHeightStatus({
      available: 0,
      partial: 0,
      gap: 2,
      unsupported: 0,
      unrecorded: 0,
    }),
    /Height unavailable.*missing evidence is not zero/,
  );
  assert.equal(
    buildingHeightStatus({
      available: 2,
      partial: 0,
      gap: 0,
      unsupported: 0,
      unrecorded: 0,
    }),
    null,
  );
});

test('primary map consumes the scene while screening keeps its legacy read contract', () => {
  const state = readFileSync(
    new URL('../app/site-workspace-state.ts', import.meta.url),
    'utf8',
  );
  const page = readFileSync(
    new URL('../app/page.tsx', import.meta.url),
    'utf8',
  );
  assert.match(
    state,
    /readInfrastructureMapScene\(contextRun, abort\.signal\)/,
  );
  assert.match(state, /readScreeningMapFeatures\(contextRun, abort\.signal\)/);
  assert.match(
    state,
    /mapScene\?\.snapshot\.id === contextRun\.evidence_snapshot_id/,
  );
  assert.match(state, /sceneRequestGeneration\.current/);
  assert.match(
    state,
    /sceneRequestGeneration\.current \+= 1;\s+abort\.abort\(\)/,
  );
  assert.match(
    state,
    /mapSceneAssessmentKey === assessmentKey &&[\s\S]*?mapSceneState === 'failed'/,
  );
  assert.match(
    page,
    /mapScene=\{view === 'site' \? mapEvidence\.scene : null\}/,
  );
});
