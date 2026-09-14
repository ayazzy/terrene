import test from 'node:test';
import assert from 'node:assert/strict';
import {
  evidenceAvailabilityLabel,
  evidenceFactLabel,
  evidenceGapReasonLabel,
  evidenceGapStateLabel,
  gapLabel,
  prioritizeFacts,
  prioritizeGaps,
  prioritizeQuestions,
  siteBriefValue,
  siteBriefLabel,
  sitePictureFacts,
} from '../app/site-brief.ts';

const refs = {
  observation_ids: [],
  gap_ids: [],
  object_ids: [],
  relationship_ids: [],
  source_feature_reference_ids: [],
  source_reference_ids: [],
  raw_reference_ids: [],
  capability_ids: [],
};
const fact = (definition_id, value = 0.2, known_zero = false) => ({
  id: definition_id,
  definition_id,
  label: definition_id,
  dimensions: {},
  value: { kind: 'number', value },
  unit: 'fraction',
  availability: 'available',
  known_zero,
  support: {
    coverage_status: 'full',
    coverage_basis: 'test',
    thematic_completeness: 'test',
  },
  limitations: '',
  references: refs,
});
const gap = (id, definition_id) => ({
  id,
  definition_id,
  legacy_variable: null,
  state: 'unavailable',
  reason_code: 'source_not_connected',
  reason: `${definition_id} is unavailable`,
  source_reference_ids: [],
  raw_reference_ids: [],
});
const result = {
  groups: [
    {
      id: 'physical_hydrological',
      label: 'Physical',
      facts: [
        fact('physical.elevation.maximum', 68),
        fact('physical.slope.mean', 2),
        fact('physical.watercourse.intersects', 1),
        fact('physical.flood.mapped_extent_fraction', 0.4),
      ],
      gaps: [
        gap('soil', 'soil.drainage.class'),
        gap('ground', 'physical.groundwater.depth'),
      ],
    },
    {
      id: 'ecology_designations',
      label: 'Ecology',
      facts: [
        fact('ecology.priority_habitat.any_mapped_overlap_fraction', 0, true),
        fact('designations.overlap_fraction', 0.5),
      ],
      gaps: [gap('condition', 'ecology.habitat_condition')],
    },
    {
      id: 'built_transport',
      label: 'Built',
      facts: [
        fact('built.mapped_built_up_fraction', 0.9),
        fact('built.building.mapped_overlap_fraction', 0.43),
        fact('transport.railway_track.mapped_length_within', 280),
      ],
      gaps: [],
    },
  ],
  review_questions: [
    {
      id: 'capability-question:a',
      label: 'a',
      text: 'Capability?',
      references: { ...refs, capability_ids: ['a'] },
    },
    {
      id: 'gap-question:condition',
      label: 'condition',
      text: 'Condition?',
      references: { ...refs, gap_ids: ['condition'] },
    },
    {
      id: 'gap-question:ground',
      label: 'ground',
      text: '  condition.  ',
      references: { ...refs, gap_ids: ['ground'] },
    },
    {
      id: 'question:built_semantics',
      label: 'built',
      text: 'Which built source?',
      references: { ...refs, observation_ids: ['built'] },
    },
  ],
};

test('site brief prioritizes high-signal context ahead of terrain extrema', () => {
  const chosen = prioritizeFacts(result);
  assert.deepEqual(
    chosen.slice(0, 3).map((item) => item.definition_id),
    [
      'built.mapped_built_up_fraction',
      'built.building.mapped_overlap_fraction',
      'ecology.priority_habitat.any_mapped_overlap_fraction',
    ],
  );
  assert.ok(
    !chosen.some((item) => item.definition_id === 'physical.elevation.maximum'),
  );
  assert.equal(
    chosen.find((item) => item.definition_id.includes('building'))?.mapKey,
    'context:buildings',
  );
  assert.equal(chosen[0].briefLabel, 'Mapped built-up land');
  assert.equal(
    siteBriefValue(fact('built.mapped_built_up_fraction', 0.92941)),
    '92.9%',
  );
  assert.equal(
    siteBriefLabel(
      chosen.find((item) => item.definition_id.includes('building')),
      {
        layers: [{ id: 'buildings', feature_count: 13 }],
        features: [],
      },
    ),
    '13 mapped buildings',
  );
});

test('site picture spans distinct useful domains and unknowns stay concise', () => {
  assert.deepEqual(
    sitePictureFacts(result).map((item) => item.category),
    ['Built context', 'Water', 'Transport'],
  );
  assert.deepEqual(
    prioritizeGaps(result).map((item) => item.id),
    ['soil', 'ground', 'condition'],
  );
  assert.deepEqual(
    prioritizeQuestions(result).map((item) => item.id),
    [
      'question:built_semantics',
      'gap-question:condition',
      'capability-question:a',
    ],
  );
  assert.equal(
    prioritizeQuestions(result, result.review_questions.length).length,
    3,
  );
});

test('evidence labels translate registry language without changing values', () => {
  assert.equal(
    evidenceFactLabel(fact('physical.elevation.maximum', 68)),
    'Highest ground elevation',
  );
  assert.equal(
    evidenceFactLabel(fact('built.building.mapped_overlap_fraction', 0.43), {
      layers: [{ id: 'buildings', feature_count: 5 }],
      features: [],
    }),
    '5 mapped buildings',
  );
  assert.equal(
    evidenceAvailabilityLabel(fact('designations.overlap_fraction', 0, true)),
    'No overlap mapped in retained source',
  );
  assert.equal(
    evidenceAvailabilityLabel({
      ...fact('physical.flood.mapped_extent_fraction'),
      availability: 'partial',
    }),
    'Partial source coverage',
  );
  assert.equal(
    evidenceAvailabilityLabel({
      ...fact('transport.railway_track.distance_min', 0, true),
      unit: 'm',
    }),
    'Zero mapped distance in retained source',
  );
});

test('gap labels explain coverage while preserving the exact gap record', () => {
  const missingSource = {
    ...gap('soil', 'soil.drainage.class'),
    state: 'source_not_connected',
    reason_code: 'source_unconnected',
  };
  assert.equal(
    evidenceGapReasonLabel(missingSource),
    'Required source is not connected',
  );
  assert.equal(evidenceGapStateLabel(missingSource), 'Source not connected');
  assert.equal(
    gapLabel({
      ...missingSource,
      definition_id: 'physical.flood.mapped_extent_fraction',
    }),
    'Flood-zone evidence',
  );
  assert.equal(
    gapLabel({
      ...missingSource,
      definition_id: 'built.infrastructure.complete_footprint_fraction',
    }),
    'Complete infrastructure footprint',
  );
  assert.equal(
    evidenceGapReasonLabel({
      ...missingSource,
      reason_code: 'future_reason_code',
    }),
    'Future reason code',
  );
});
