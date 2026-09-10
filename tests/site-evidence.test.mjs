import test from 'node:test';
import assert from 'node:assert/strict';
import {
  componentBand,
  observationState,
  observationValue,
  linkedFindings,
} from '../app/site-evidence.ts';

test('watercourse categorical evidence preserves yes, no and unknown', () => {
  const variable = 'hydrology.watercourse_intersection';
  assert.equal(observationValue({ variable, value: 'yes' }), 'Yes');
  assert.equal(observationValue({ variable, value: 'no' }), 'No');
  assert.equal(
    observationValue({ variable, value: null }),
    'Evidence unavailable',
  );
  assert.equal(observationValue({ variable, value: 'unknown' }), 'unknown');
});
test('a measured zero is available, never mistaken for missing evidence', () => {
  assert.equal(
    observationState({ value: 0, observed_or_derived: 'observed' }),
    'available',
  );
  assert.equal(observationValue({ value: 0, unit: 'fraction' }), '0%');
  assert.equal(
    observationState({ value: null, observed_or_derived: 'derived' }),
    'unavailable',
  );
});
test('partial derived evidence is not labelled complete', () => {
  assert.equal(
    observationState({
      value: 0.8,
      input_coverage: 0.7,
      observed_or_derived: 'derived',
    }),
    'partial',
  );
  assert.equal(
    observationState({
      value: 0.8,
      input_coverage: 1,
      observed_or_derived: 'derived',
    }),
    'modelled',
  );
});
test('display preserves supplied categories and never manufactures a category for null output', () => {
  assert.equal(componentBand({ score: 90, band: 'VERY_HIGH' }), 'very high');
  assert.equal(
    componentBand({ score: null, band: 'VERY_HIGH' }),
    'Insufficient evidence',
  );
  assert.equal(
    componentBand({ score: 90, band: 'INSUFFICIENT_DATA' }),
    'Insufficient evidence',
  );
  assert.equal(componentBand({ score: 10 }), 'Very low');
});
test('map links require exact pinned dataset lineage, including multiple parents', () => {
  const flood = { key: 'flood', dataset_version: 'flood-pinned' };
  const sssi = { key: 'sssi', dataset_version: 'sssi-pinned' };
  const nextFlood = { key: 'flood', dataset_version: 'flood-new' };
  assert.deepEqual(
    linkedFindings({ raw_source_ids: ['flood-pinned'] }, [
      nextFlood,
      flood,
      sssi,
    ]),
    [flood],
  );
  assert.deepEqual(
    linkedFindings({ raw_source_ids: ['flood-pinned', 'sssi-pinned'] }, [
      flood,
      sssi,
    ]),
    [flood, sssi],
  );
  assert.deepEqual(linkedFindings({ raw_source_ids: [] }, [flood]), []);
});
