export const operatingModes = [
  'map',
  'list',
  'site',
  'project',
  'compare',
  'data',
] as const;

export type OperatingMode = (typeof operatingModes)[number];

export type OperatingEntitySelection =
  | { kind: 'site'; id: string }
  | { kind: 'project_subject'; id: string }
  | null;

export type OperatingArtifactSelection =
  | { kind: 'site_assessment'; id: string }
  | { kind: 'project_intelligence_run'; id: string }
  | null;

export type OperatingDossierSection =
  | 'overview'
  | 'evidence'
  | 'models'
  | 'issues'
  | 'history';

export type OperatingPictureState = {
  mode: OperatingMode;
  selection: OperatingEntitySelection;
  artifact: OperatingArtifactSelection;
  assetId: string | null;
  showRelated: boolean;
  section: OperatingDossierSection;
  dossierOpen: boolean;
  hiddenLayers: string[];
};

export type OperatingPictureAvailability = {
  siteIds?: readonly string[];
  projectSubjectIds?: readonly string[];
  siteAssessmentIds?: readonly string[];
  projectIntelligenceRunIds?: readonly string[];
  mapObjectIds?: readonly string[];
};

export type OperatingPictureHistoryAdapter = {
  readUrl: () => string;
  pushUrl: (url: string) => void;
  replaceUrl: (url: string) => void;
  subscribe: (listener: () => void) => () => void;
};

export type OperatingPictureController = {
  getState: () => OperatingPictureState;
  subscribe: (listener: () => void) => () => void;
  transition: (
    next:
      | OperatingPictureState
      | ((current: OperatingPictureState) => OperatingPictureState),
    method?: 'push' | 'replace',
  ) => void;
  refreshFromUrl: () => void;
  destroy: () => void;
};

export type OperatingPictureProjection = {
  view: 'workspace' | 'site' | 'project-intelligence' | 'compare' | 'data';
  sitesView: 'map' | 'list';
  activeSiteId: string | null;
  selectedMapSiteId: string | null;
  selectedProjectSubjectId: string | null;
  selectedProjectRunId: string | null;
};

export const defaultOperatingPictureState: OperatingPictureState = {
  mode: 'map',
  selection: null,
  artifact: null,
  assetId: null,
  showRelated: false,
  section: 'overview',
  dossierOpen: true,
  hiddenLayers: [],
};

const identifierPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,239}$/;
const layerPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$/;
const siteSections = new Set<OperatingDossierSection>([
  'overview',
  'evidence',
  'models',
  'history',
]);
const projectSections = new Set<OperatingDossierSection>([
  'overview',
  'evidence',
  'issues',
  'history',
]);

function validIdentifier(value: string | null): value is string {
  return !!value && identifierPattern.test(value);
}

function normalizeHiddenLayers(values: readonly string[]) {
  return [...new Set(values.filter((value) => layerPattern.test(value)))]
    .sort()
    .slice(0, 64);
}

function sectionForSelection(
  section: OperatingDossierSection,
  selection: OperatingEntitySelection,
) {
  if (selection?.kind === 'site' && siteSections.has(section)) return section;
  if (selection?.kind === 'project_subject' && projectSections.has(section))
    return section;
  return 'overview';
}

function artifactForSelection(
  artifact: OperatingArtifactSelection,
  selection: OperatingEntitySelection,
) {
  if (selection?.kind === 'site' && artifact?.kind === 'site_assessment')
    return artifact;
  if (
    selection?.kind === 'project_subject' &&
    artifact?.kind === 'project_intelligence_run'
  )
    return artifact;
  return null;
}

export function normalizeOperatingPictureState(
  value: OperatingPictureState,
): OperatingPictureState {
  let mode: OperatingMode = operatingModes.includes(value.mode)
    ? value.mode
    : 'map';
  let selection = value.selection;

  if (!selection || !validIdentifier(selection.id)) selection = null;
  if (mode === 'site' && selection?.kind !== 'site') {
    selection = null;
    mode = 'map';
  }
  if (mode === 'project' && selection?.kind === 'site') {
    selection = null;
    mode = 'map';
  }
  if (mode === 'compare' || mode === 'data') selection = null;
  const assetId =
    mode === 'site' &&
    selection?.kind === 'site' &&
    validIdentifier(value.assetId)
      ? value.assetId
      : null;

  return {
    mode: mode === 'site' && !selection ? 'map' : mode,
    selection,
    artifact: artifactForSelection(value.artifact, selection),
    assetId,
    showRelated: !!value.showRelated && !!assetId,
    section: sectionForSelection(value.section, selection),
    dossierOpen: !!value.dossierOpen,
    hiddenLayers: normalizeHiddenLayers(value.hiddenLayers),
  };
}

export function projectOperatingPictureState(
  value: OperatingPictureState,
): OperatingPictureProjection {
  const state = normalizeOperatingPictureState(value);
  const siteId = state.selection?.kind === 'site' ? state.selection.id : null;
  return {
    view:
      state.mode === 'site'
        ? 'site'
        : state.mode === 'project'
          ? 'project-intelligence'
          : state.mode === 'compare'
            ? 'compare'
            : state.mode === 'data'
              ? 'data'
              : 'workspace',
    sitesView: state.mode === 'list' ? 'list' : 'map',
    activeSiteId: state.mode === 'site' ? siteId : null,
    selectedMapSiteId: siteId,
    selectedProjectSubjectId:
      state.selection?.kind === 'project_subject' ? state.selection.id : null,
    selectedProjectRunId:
      state.artifact?.kind === 'project_intelligence_run'
        ? state.artifact.id
        : null,
  };
}

export function changeOperatingMode(
  value: OperatingPictureState,
  mode: OperatingMode,
) {
  const current = normalizeOperatingPictureState(value);
  const selection =
    mode === 'compare' || mode === 'data'
      ? null
      : mode === 'site' && current.selection?.kind !== 'site'
        ? null
        : mode === 'project' && current.selection?.kind !== 'project_subject'
          ? null
          : current.selection;
  return normalizeOperatingPictureState({
    ...current,
    mode,
    selection,
    artifact: selection ? current.artifact : null,
    assetId: null,
    showRelated: false,
    section: selection ? current.section : 'overview',
  });
}

export function selectOperatingEntity(
  value: OperatingPictureState,
  selection: OperatingEntitySelection,
  mode?: OperatingMode,
) {
  const current = normalizeOperatingPictureState(value);
  return normalizeOperatingPictureState({
    ...current,
    mode: mode ?? current.mode,
    selection,
    artifact: null,
    assetId: null,
    showRelated: false,
    section: 'overview',
    dossierOpen: true,
  });
}

function parseSelection(parameters: URLSearchParams): OperatingEntitySelection {
  const kind = parameters.get('entity');
  const id = parameters.get('id');
  if (!validIdentifier(id)) return null;
  if (kind === 'site' || kind === 'project_subject') return { kind, id };
  return null;
}

function parseArtifact(
  parameters: URLSearchParams,
): OperatingArtifactSelection {
  const assessmentId = parameters.get('assessment');
  const runId = parameters.get('run');
  if (assessmentId && runId) return null;
  if (validIdentifier(assessmentId))
    return { kind: 'site_assessment', id: assessmentId };
  if (validIdentifier(runId))
    return { kind: 'project_intelligence_run', id: runId };
  return null;
}

export function parseOperatingPictureUrl(input: string): OperatingPictureState {
  const url = new URL(input, 'http://terrene.local');
  const requestedMode = url.searchParams.get('mode');
  const mode = operatingModes.includes(requestedMode as OperatingMode)
    ? (requestedMode as OperatingMode)
    : 'map';
  const requestedSection = url.searchParams.get('section');
  const section = [
    'overview',
    'evidence',
    'models',
    'issues',
    'history',
  ].includes(requestedSection || '')
    ? (requestedSection as OperatingDossierSection)
    : 'overview';
  const selection = parseSelection(url.searchParams);
  const selectionWasRequested =
    url.searchParams.has('entity') || url.searchParams.has('id');

  return normalizeOperatingPictureState({
    mode: selectionWasRequested && !selection ? 'map' : mode,
    selection,
    artifact: parseArtifact(url.searchParams),
    assetId: validIdentifier(url.searchParams.get('asset'))
      ? url.searchParams.get('asset')
      : null,
    showRelated: url.searchParams.get('related') === '1',
    section,
    dossierOpen: url.searchParams.get('dossier') !== 'closed',
    hiddenLayers: (url.searchParams.get('hidden') || '')
      .split(',')
      .filter(Boolean),
  });
}

export function serializeOperatingPictureState(
  value: OperatingPictureState,
  currentUrl = '/',
) {
  const state = normalizeOperatingPictureState(value);
  const current = new URL(currentUrl, 'http://terrene.local');
  const parameters = new URLSearchParams();
  parameters.set('mode', state.mode);
  if (state.selection) {
    parameters.set('entity', state.selection.kind);
    parameters.set('id', state.selection.id);
  }
  if (state.artifact?.kind === 'site_assessment')
    parameters.set('assessment', state.artifact.id);
  if (state.artifact?.kind === 'project_intelligence_run')
    parameters.set('run', state.artifact.id);
  if (state.assetId) parameters.set('asset', state.assetId);
  if (state.showRelated) parameters.set('related', '1');
  if (state.section !== 'overview') parameters.set('section', state.section);
  if (!state.dossierOpen) parameters.set('dossier', 'closed');
  if (state.hiddenLayers.length)
    parameters.set('hidden', state.hiddenLayers.join(','));
  const query = parameters.toString();
  return `${current.pathname}${query ? `?${query}` : ''}${current.hash}`;
}

function unavailable(id: string, available: readonly string[] | undefined) {
  return available !== undefined && !available.includes(id);
}

export function reconcileOperatingPictureState(
  value: OperatingPictureState,
  availability: OperatingPictureAvailability,
): OperatingPictureState {
  const state = normalizeOperatingPictureState(value);
  let selection = state.selection;
  let artifact = state.artifact;
  let section = state.section;

  if (
    selection?.kind === 'site' &&
    unavailable(selection.id, availability.siteIds)
  )
    selection = null;
  if (
    selection?.kind === 'project_subject' &&
    unavailable(selection.id, availability.projectSubjectIds)
  )
    selection = null;

  if (!selection) {
    artifact = null;
    section = 'overview';
  }
  let assetId = state.assetId;
  let showRelated = state.showRelated;
  if (
    artifact?.kind === 'site_assessment' &&
    unavailable(artifact.id, availability.siteAssessmentIds)
  ) {
    artifact = null;
    section = 'overview';
  }
  if (
    artifact?.kind === 'project_intelligence_run' &&
    unavailable(artifact.id, availability.projectIntelligenceRunIds)
  ) {
    artifact = null;
    section = 'overview';
  }
  if (assetId && unavailable(assetId, availability.mapObjectIds)) {
    assetId = null;
    showRelated = false;
  }

  return normalizeOperatingPictureState({
    ...state,
    selection,
    artifact,
    assetId,
    showRelated,
    section,
  });
}

export function operatingPictureStatesEqual(
  left: OperatingPictureState,
  right: OperatingPictureState,
) {
  return (
    left.mode === right.mode &&
    left.selection?.kind === right.selection?.kind &&
    left.selection?.id === right.selection?.id &&
    left.artifact?.kind === right.artifact?.kind &&
    left.artifact?.id === right.artifact?.id &&
    left.assetId === right.assetId &&
    left.showRelated === right.showRelated &&
    left.section === right.section &&
    left.dossierOpen === right.dossierOpen &&
    left.hiddenLayers.length === right.hiddenLayers.length &&
    left.hiddenLayers.every((item, index) => item === right.hiddenLayers[index])
  );
}

export function createOperatingPictureController(
  adapter: OperatingPictureHistoryAdapter,
): OperatingPictureController {
  let state = parseOperatingPictureUrl(adapter.readUrl());
  const listeners = new Set<() => void>();
  const notify = () => listeners.forEach((listener) => listener());
  const read = () => {
    const next = parseOperatingPictureUrl(adapter.readUrl());
    if (!operatingPictureStatesEqual(state, next)) {
      state = next;
      notify();
    }
  };
  const unsubscribe = adapter.subscribe(read);

  return {
    getState: () => state,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    transition(next, method = 'push') {
      const candidate = normalizeOperatingPictureState(
        typeof next === 'function' ? next(state) : next,
      );
      if (operatingPictureStatesEqual(state, candidate)) return;
      state = candidate;
      const url = serializeOperatingPictureState(state, adapter.readUrl());
      if (method === 'replace') adapter.replaceUrl(url);
      else adapter.pushUrl(url);
      notify();
    },
    refreshFromUrl: read,
    destroy() {
      unsubscribe();
      listeners.clear();
    },
  };
}

export function createBrowserOperatingPictureAdapter(): OperatingPictureHistoryAdapter {
  return {
    readUrl: () => window.location.href,
    pushUrl: (url) => window.history.pushState(null, '', url),
    replaceUrl: (url) => window.history.replaceState(null, '', url),
    subscribe(listener) {
      window.addEventListener('popstate', listener);
      return () => window.removeEventListener('popstate', listener);
    },
  };
}

export type LatestRequestFence = {
  begin: () => number;
  invalidate: () => void;
  isCurrent: (token: number) => boolean;
};

export function createLatestRequestFence(): LatestRequestFence {
  let generation = 0;
  return {
    begin: () => ++generation,
    invalidate: () => {
      generation += 1;
    },
    isCurrent: (token) => token === generation,
  };
}
