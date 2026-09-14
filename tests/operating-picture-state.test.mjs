import test from 'node:test';
import assert from 'node:assert/strict';
import {
  changeOperatingMode,
  createLatestRequestFence,
  createOperatingPictureController,
  defaultOperatingPictureState,
  normalizeOperatingPictureState,
  parseOperatingPictureUrl,
  projectOperatingPictureState,
  reconcileOperatingPictureState,
  serializeOperatingPictureState,
  selectOperatingEntity,
} from '../app/operating-picture-state.ts';

function fakeHistory(initial = '/?mode=map') {
  const entries = [initial];
  let index = 0;
  const listeners = new Set();
  const emit = () => listeners.forEach((listener) => listener());
  return {
    adapter: {
      readUrl: () => entries[index],
      pushUrl(url) {
        entries.splice(index + 1);
        entries.push(url);
        index += 1;
      },
      replaceUrl(url) {
        entries[index] = url;
      },
      subscribe(listener) {
        listeners.add(listener);
        return () => listeners.delete(listener);
      },
    },
    back() {
      if (index > 0) index -= 1;
      emit();
    },
    forward() {
      if (index < entries.length - 1) index += 1;
      emit();
    },
    get entries() {
      return entries;
    },
  };
}

test('URL state round-trips a complete Site investigation deterministically', () => {
  const expected = normalizeOperatingPictureState({
    mode: 'site',
    selection: { kind: 'site', id: 'site-123' },
    artifact: { kind: 'site_assessment', id: 'assessment-456' },
    assetId: 'building:abc123',
    showRelated: true,
    section: 'evidence',
    dossierOpen: false,
    hiddenLayers: ['built:railways', 'environment:flood', 'built:railways'],
  });
  const url = serializeOperatingPictureState(expected, '/workspace#review');
  assert.equal(
    url,
    '/workspace?mode=site&entity=site&id=site-123&assessment=assessment-456&asset=building%3Aabc123&related=1&section=evidence&dossier=closed&hidden=built%3Arailways%2Cenvironment%3Aflood#review',
  );
  assert.deepEqual(parseOperatingPictureUrl(url), expected);
});

test('URL state round-trips Project Intelligence run and issue context', () => {
  const expected = {
    mode: 'project',
    selection: { kind: 'project_subject', id: 'subject-123' },
    artifact: { kind: 'project_intelligence_run', id: 'run:abc123' },
    assetId: null,
    showRelated: false,
    section: 'issues',
    dossierOpen: true,
    hiddenLayers: [],
  };
  assert.deepEqual(
    parseOperatingPictureUrl(serializeOperatingPictureState(expected)),
    expected,
  );
});

test('invalid and mutually inconsistent URL fields fail closed', () => {
  assert.deepEqual(
    parseOperatingPictureUrl(
      '/?mode=site&entity=project_subject&id=subject-1&run=run-1&section=issues',
    ),
    defaultOperatingPictureState,
  );
  assert.deepEqual(
    parseOperatingPictureUrl(
      '/?mode=project&entity=project_subject&id=subject-1&assessment=a-1&run=r-1&section=models',
    ),
    {
      ...defaultOperatingPictureState,
      mode: 'project',
      selection: { kind: 'project_subject', id: 'subject-1' },
    },
  );
  assert.deepEqual(
    parseOperatingPictureUrl('/?mode=unknown&entity=site&id=%3Cscript%3E'),
    defaultOperatingPictureState,
  );
  assert.deepEqual(
    parseOperatingPictureUrl(
      '/?mode=project&entity=project_subject&id=%3Cscript%3E',
    ),
    defaultOperatingPictureState,
  );
  assert.deepEqual(
    parseOperatingPictureUrl('/?mode=project&entity=site&id=site-1'),
    defaultOperatingPictureState,
  );
});

test('availability reconciliation treats deleted and unauthorized identities as absent', () => {
  const site = parseOperatingPictureUrl(
    '/?mode=site&entity=site&id=outside-tenant&assessment=old-assessment&section=history',
  );
  assert.deepEqual(
    reconcileOperatingPictureState(site, {
      siteIds: ['authorized-site'],
      siteAssessmentIds: ['authorized-assessment'],
    }),
    defaultOperatingPictureState,
  );

  const project = parseOperatingPictureUrl(
    '/?mode=project&entity=project_subject&id=subject-1&run=old-run&section=history',
  );
  assert.deepEqual(
    reconcileOperatingPictureState(project, {
      projectSubjectIds: ['subject-1'],
      projectIntelligenceRunIds: ['current-run'],
    }),
    {
      ...defaultOperatingPictureState,
      mode: 'project',
      selection: { kind: 'project_subject', id: 'subject-1' },
    },
  );
});

test('asset intelligence fails closed to the selected immutable scene', () => {
  const asset = parseOperatingPictureUrl(
    '/?mode=site&entity=site&id=site-1&assessment=assessment-1&asset=building:one&related=1',
  );
  assert.equal(asset.assetId, 'building:one');
  assert.equal(asset.showRelated, true);
  assert.deepEqual(
    reconcileOperatingPictureState(asset, { mapObjectIds: ['building:two'] }),
    {
      ...asset,
      assetId: null,
      showRelated: false,
    },
  );
  assert.deepEqual(
    parseOperatingPictureUrl(
      '/?mode=map&entity=site&id=site-1&asset=building:one&related=1',
    ),
    {
      ...defaultOperatingPictureState,
      selection: { kind: 'site', id: 'site-1' },
    },
  );
});

test('controller makes push, replace, back, forward and reload deterministic', () => {
  const history = fakeHistory();
  const controller = createOperatingPictureController(history.adapter);
  const observed = [];
  controller.subscribe(() => observed.push(controller.getState()));

  controller.transition({
    ...defaultOperatingPictureState,
    mode: 'site',
    selection: { kind: 'site', id: 'site-1' },
    artifact: null,
  });
  controller.transition((current) => ({
    ...current,
    section: 'evidence',
  }));
  controller.transition(
    (current) => ({ ...current, hiddenLayers: ['environment:flood'] }),
    'replace',
  );
  assert.equal(history.entries.length, 3);
  assert.equal(controller.getState().section, 'evidence');

  history.back();
  assert.equal(controller.getState().section, 'overview');
  history.forward();
  assert.equal(controller.getState().section, 'evidence');
  assert.deepEqual(controller.getState().hiddenLayers, ['environment:flood']);

  const reloaded = createOperatingPictureController(history.adapter);
  assert.deepEqual(reloaded.getState(), controller.getState());
  reloaded.destroy();
  controller.destroy();
  assert.ok(observed.length >= 3);
});

test('history restores dossier visibility and exact historical artifact', () => {
  const history = fakeHistory(
    '/?mode=site&entity=site&id=site-1&assessment=assessment-1&section=history&dossier=closed',
  );
  const controller = createOperatingPictureController(history.adapter);

  controller.transition((current) => ({
    ...current,
    dossierOpen: true,
  }));
  controller.transition((current) =>
    selectOperatingEntity(
      current,
      { kind: 'project_subject', id: 'subject-1' },
      'project',
    ),
  );
  assert.deepEqual(controller.getState().artifact, null);
  assert.equal(controller.getState().section, 'overview');

  history.back();
  assert.equal(controller.getState().dossierOpen, true);
  assert.deepEqual(controller.getState().artifact, {
    kind: 'site_assessment',
    id: 'assessment-1',
  });
  history.back();
  assert.equal(controller.getState().dossierOpen, false);
  assert.equal(controller.getState().section, 'history');

  controller.destroy();
});

test('history restores portfolio, site diligence, and exact asset intelligence', () => {
  const history = fakeHistory('/?mode=map');
  const controller = createOperatingPictureController(history.adapter);
  controller.transition({
    ...defaultOperatingPictureState,
    mode: 'site',
    selection: { kind: 'site', id: 'site-1' },
  });
  controller.transition((current) => ({
    ...current,
    assetId: 'building:one',
  }));
  controller.transition((current) => ({
    ...current,
    showRelated: true,
  }));

  assert.equal(controller.getState().assetId, 'building:one');
  assert.equal(controller.getState().showRelated, true);
  history.back();
  assert.equal(controller.getState().showRelated, false);
  assert.equal(controller.getState().assetId, 'building:one');
  history.back();
  assert.equal(controller.getState().assetId, null);
  history.back();
  assert.equal(controller.getState().mode, 'map');
  history.forward();
  history.forward();
  assert.equal(controller.getState().assetId, 'building:one');

  const reloaded = createOperatingPictureController(history.adapter);
  assert.deepEqual(reloaded.getState(), controller.getState());
  reloaded.destroy();
  controller.destroy();
});

test('layer visibility is canonical, bounded and rejects unsafe values', () => {
  const layers = Array.from(
    { length: 70 },
    (_, index) => `built:layer-${index}`,
  );
  const canonical = normalizeOperatingPictureState({
    ...defaultOperatingPictureState,
    hiddenLayers: ['environment:flood', 'environment:flood', '<unsafe>'],
  });
  const state = normalizeOperatingPictureState({
    ...defaultOperatingPictureState,
    hiddenLayers: ['<unsafe>', ...layers],
  });

  assert.equal(state.hiddenLayers.length, 64);
  assert.equal(state.hiddenLayers.includes('<unsafe>'), false);
  assert.equal(
    canonical.hiddenLayers.filter((layer) => layer === 'environment:flood')
      .length,
    1,
  );
  assert.deepEqual(
    parseOperatingPictureUrl(serializeOperatingPictureState(state))
      .hiddenLayers,
    state.hiddenLayers,
  );
});

test('one selection projection cannot diverge between map and Site workspace', () => {
  const selected = selectOperatingEntity(
    defaultOperatingPictureState,
    { kind: 'site', id: 'site-1' },
    'map',
  );
  assert.deepEqual(projectOperatingPictureState(selected), {
    view: 'workspace',
    sitesView: 'map',
    activeSiteId: null,
    selectedMapSiteId: 'site-1',
    selectedProjectSubjectId: null,
    selectedProjectRunId: null,
  });

  const opened = changeOperatingMode(selected, 'site');
  assert.deepEqual(projectOperatingPictureState(opened), {
    view: 'site',
    sitesView: 'map',
    activeSiteId: 'site-1',
    selectedMapSiteId: 'site-1',
    selectedProjectSubjectId: null,
    selectedProjectRunId: null,
  });
  assert.equal(changeOperatingMode(opened, 'data').selection, null);
});

test('latest-request fence rejects late results after selection changes', async () => {
  const fence = createLatestRequestFence();
  const accepted = [];
  const first = fence.begin();
  const second = fence.begin();

  await Promise.resolve();
  if (fence.isCurrent(second)) accepted.push('new-selection');
  if (fence.isCurrent(first)) accepted.push('stale-selection');
  assert.deepEqual(accepted, ['new-selection']);

  fence.invalidate();
  assert.equal(fence.isCurrent(second), false);
});
