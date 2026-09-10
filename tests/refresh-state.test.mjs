import test from 'node:test';
import assert from 'node:assert/strict';
import { readResource, criticalReadFailure } from '../app/refresh-state.ts';

test('optional fetch failures do not discard saved assessment reads', async () => {
  const saved = [
    { id: 'saved-site', assessment: { result: { area_ha: 167.15 } } },
  ];
  const [sites, datasets, health] = await Promise.all([
    readResource(async () => saved),
    readResource(async () => {
      throw new TypeError('Failed to fetch');
    }),
    readResource(async () => ({ mode: 'development' })),
  ]);
  assert.deepEqual(sites.data, saved);
  assert.equal(datasets.failure.message, 'Failed to fetch');
  assert.equal(health.data.mode, 'development');
  assert.equal(criticalReadFailure({ datasets: datasets.failure }, true), null);
});
test('failed initial site reads remain critical; cached sites permit contextual refresh reporting', () => {
  const failure = { message: 'Service offline', status: 503 };
  assert.equal(criticalReadFailure({ sites: failure }, false), failure);
  assert.equal(criticalReadFailure({ sites: failure }, true), null);
  assert.equal(criticalReadFailure({ history: failure }, true), null);
});
test('authentication and authorization failures remain critical even with saved evidence', async () => {
  for (const status of [401, 403]) {
    const read = await readResource(async () => {
      throw Object.assign(new Error('Access denied'), { status });
    });
    assert.equal(read.failure.status, status);
    assert.equal(
      criticalReadFailure({ history: read.failure }, true),
      read.failure,
    );
    assert.equal(
      criticalReadFailure({ datasets: read.failure }, true),
      read.failure,
    );
  }
});
test('successful retry clears its read failure and accepts an empty result', async () => {
  const failed = await readResource(async () => {
    throw new Error('Offline');
  });
  const retried = await readResource(async () => []);
  assert.ok(failed.failure);
  assert.equal(retried.failure, null);
  assert.deepEqual(retried.data, []);
  assert.equal(criticalReadFailure({ sites: retried.failure }, false), null);
});
