import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  assessmentCreatedLabel,
  assessmentStateClass,
  assessmentStateLabel,
} from '../app/assessment-timeline-format.ts';

const [page, timeline, css] = await Promise.all([
  readFile(new URL('../app/page.tsx', import.meta.url), 'utf8'),
  readFile(
    new URL('../app/site-assessment-timeline.tsx', import.meta.url),
    'utf8',
  ),
  readFile(new URL('../app/globals.css', import.meta.url), 'utf8'),
]);

test('History presents retained assessments without changing selection behavior', () => {
  assert.match(
    page,
    /<TabsContent value="history">[\s\S]*?<SiteAssessmentTimeline/,
  );
  assert.match(page, /selectedAssessmentId=\{assessment\?\.id\}/);
  assert.match(page, /latestAssessmentId=\{current\.assessment\?\.id\}/);
  assert.match(page, /currentBoundaryVersion=\{current\.version\}/);
  assert.match(page, /onSelect=\{selectSiteAssessment\}/);
  assert.match(timeline, /aria-current=\{isSelected \? 'step' : undefined\}/);
});

test('timeline separates creation, status, boundary identity and source retention', () => {
  assert.equal(assessmentStateLabel('partial'), 'Partial evidence');
  assert.equal(assessmentStateLabel('needs_review'), 'Needs review');
  assert.equal(assessmentStateClass('Needs Review'), 'needs-review');
  assert.equal(
    assessmentCreatedLabel('not-a-date'),
    'Creation date unavailable',
  );
  assert.match(
    assessmentCreatedLabel('2026-09-10T12:00:00Z'),
    /^Created 10 Sept 2026 at /,
  );
  assert.match(timeline, /Matches current Site boundary/);
  assert.match(timeline, /Historical boundary · current Site is v/);
  assert.match(timeline, /sourceCount != null && sourceCount > 0/);
  assert.match(
    timeline,
    /source version\{sourceCount === 1 \? '' : 's'\} retained/,
  );
  assert.match(timeline, /Latest assessment/);
});

test('timeline language and styling preserve evidence interpretation boundaries', () => {
  assert.match(
    timeline,
    /Read entries as retained states, not causes of change\./,
  );
  assert.match(
    timeline,
    /A newer assessment does not by itself establish that the site or its[\s\S]*?conditions changed\./,
  );
  assert.doesNotMatch(timeline, /evidence retained at/i);
  assert.match(
    css,
    /\.assessment-timeline-entry \{[\s\S]*?border-radius: var\(--radius-panel\)/,
  );
  assert.match(
    css,
    /\.assessment-timeline-entry\.is-selected \{[\s\S]*?box-shadow: 2px 0 0 var\(--action-primary\) inset/,
  );
  assert.match(css, /\.assessment-state\.state-completed/);
  assert.match(
    css,
    /@media \(max-width: 760px\) \{[\s\S]*?\.assessment-entry-heading/,
  );
});
