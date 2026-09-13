import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  formatMappedMeasurement,
  mapLayerStatus,
  mapRelationshipSummary,
  readScreeningMapFeatures,
  screeningMapFeaturePath,
} from '../app/screening-map-features.ts';

const run = {
  id: 'run/historical',
  site_id: 'site-1',
  boundary_version: 2,
  evidence_snapshot_id: 'snapshot-1',
  result: {
    evidence_content_hash: 'evidence-hash',
    boundary_geometry_fingerprint: 'boundary-hash',
  },
};

function collection(overrides = {}) {
  return {
    type: 'FeatureCollection',
    contract_version: 'screening_context_map_features_v1',
    run_id: run.id,
    site_id: run.site_id,
    boundary_version: run.boundary_version,
    evidence_snapshot_id: run.evidence_snapshot_id,
    evidence_content_hash: run.result.evidence_content_hash,
    boundary_geometry_fingerprint:
      run.result.boundary_geometry_fingerprint,
    presentation_crs: 'EPSG:4326',
    authoritative_geometry_crs: 'EPSG:27700',
    layers: [],
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
  const previous = globalThis.sessionStorage;
  globalThis.sessionStorage = { getItem: () => 'map-token' };
  t.after(() => {
    if (previous) globalThis.sessionStorage = previous;
    else delete globalThis.sessionStorage;
  });
  return calls;
}

test('map features are read from the selected run and checked against its immutable envelope', async (t) => {
  const calls = mockRequest(t, collection());
  const result = await readScreeningMapFeatures(run);
  assert.equal(result.run_id, run.id);
  assert.equal(
    calls[0].path,
    '/api/screening-context-runs/run%2Fhistorical/map-features',
  );
  assert.equal(calls[0].options.headers.Authorization, 'Bearer map-token');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(screeningMapFeaturePath(run.id), calls[0].path);

  t.mock.method(globalThis, 'fetch', async () =>
    Response.json(collection({ boundary_version: 3 })),
  );
  await assert.rejects(
    readScreeningMapFeatures(run),
    /does not match the selected Screening Context run/,
  );
});

test('layer labels preserve available, mapped-zero, unavailable, partial, and unsupported semantics', () => {
  const layer = { feature_count: 2 };
  assert.equal(
    mapLayerStatus({ ...layer, state: 'available' }),
    '2 mapped objects',
  );
  assert.match(
    mapLayerStatus({ ...layer, feature_count: 0, state: 'mapped_zero' }),
    /Mapped zero · source-bounded/,
  );
  assert.equal(
    mapLayerStatus({ ...layer, feature_count: 0, state: 'unavailable' }),
    'Unavailable',
  );
  assert.match(
    mapLayerStatus({ ...layer, feature_count: 0, state: 'partial' }),
    /no complete zero claim/,
  );
  assert.equal(
    mapLayerStatus({ ...layer, feature_count: 0, state: 'unsupported' }),
    'Unsupported historical evidence',
  );
});

test('source measurements retain acceptance precision and parcel relationship meaning', () => {
  assert.equal(formatMappedMeasurement(0.433473, 'fraction'), '43.3473%');
  assert.equal(formatMappedMeasurement(279.31, 'm'), '279.31 m');
  assert.match(
    mapRelationshipSummary({
      predicate: 'crosses',
      measurements: {
        overlap_area_m2: null,
        parcel_overlap_fraction: null,
        object_overlap_fraction: null,
        length_within_m: 279.31,
        minimum_distance_m: null,
      },
    }),
    /Crosses the parcel · 279.31 m within parcel/,
  );
});

test('workspace integration shares selection and never auto-focuses an off-site object on selection', () => {
  const state = readFileSync(
    new URL('../app/site-workspace-state.ts', import.meta.url),
    'utf8',
  );
  const map = readFileSync(new URL('../app/map.tsx', import.meta.url), 'utf8');
  const page = readFileSync(new URL('../app/page.tsx', import.meta.url), 'utf8');
  const inspector = readFileSync(
    new URL('../app/map-feature-inspector.tsx', import.meta.url),
    'utf8',
  );
  assert.match(state, /setSelectedMapObjectId\(null\)/);
  assert.match(state, /mapFeaturesAssessmentKey === assessmentKey/);
  assert.match(state, /function selectMapObject/);
  assert.match(state, /function locateMapObject/);
  assert.match(map, /if \(!ready \|\| !mapObjectFocusRequest\) return/);
  assert.match(map, /onClearMapObject\?\.\(\)/);
  assert.match(page, /<MapFeatureInspector/);
  assert.match(page, /tab, assessment\?\.id, mapEvidence\.selectedObjectId/);
  assert.match(inspector, /Advanced provenance/);
  assert.match(inspector, /not surveyed,[\s\S]*cadastral,[\s\S]*legal or engineering/);
});
