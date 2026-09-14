'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  contextHeaders,
  contextPath,
  contextResponse,
  readScreeningContext,
  requestScreeningContext,
  screeningAssessmentKey,
  ScreeningContextRequestError,
  type ScreeningRun,
} from './screening-context';
import {
  resolveWorkspaceAssessment,
  type WorkspaceAssessment as Assessment,
  type WorkspaceSite as Site,
} from './site-workspace-view-model';
import type { OverlayFinding } from './site-evidence';
import {
  readInfrastructureMapScene,
  type InfrastructureMapScene,
} from './infrastructure-map-scene';
import {
  readScreeningMapFeatures,
  type ScreeningMapFeatures,
} from './screening-map-features';

export type WorkspaceTab = 'overview' | 'evidence' | 'models' | 'history';
export type WetlandSection =
  | 'overview'
  | 'physical'
  | 'ecology'
  | 'constraints';
export type ContextState =
  | 'idle'
  | 'checking'
  | 'absent'
  | 'preparing'
  | 'available'
  | 'unsupported'
  | 'unauthorized'
  | 'failed';

export type SiteWorkspaceNavigation = {
  selectedAssessmentId: string | null;
  tab: WorkspaceTab;
  panelOpen: boolean;
  onAssessmentChange: (
    id: string | null,
    method: 'push' | 'replace',
  ) => void;
  onTabChange: (tab: WorkspaceTab, method: 'push' | 'replace') => void;
  onPanelOpenChange: (
    panelOpen: boolean,
    method: 'push' | 'replace',
  ) => void;
};

export function useSiteWorkspaceState(
  site: Site | undefined,
  history: Assessment[],
  navigation?: SiteWorkspaceNavigation,
) {
  const [localSelectedAssessmentId, setLocalSelectedAssessmentId] = useState<
    string | null
  >(null);
  const [localTab, setLocalTab] = useState<WorkspaceTab>('overview');
  const [wetlandSection, setWetlandSection] =
    useState<WetlandSection>('overview');
  const [localPanelOpen, setLocalPanelOpen] = useState(true);
  const [mapFocus, setMapFocus] = useState<{
    key: string;
    request: number;
  } | null>(null);
  const [finding, setFinding] = useState<OverlayFinding | null>(null);
  const [reportHtml, setReportHtml] = useState('');
  const [reportUrl, setReportUrl] = useState('');
  const [contextRun, setContextRun] = useState<ScreeningRun | null>(null);
  const [contextAssessmentKey, setContextAssessmentKey] = useState('');
  const [contextState, setContextState] = useState<ContextState>('idle');
  const [contextError, setContextError] = useState('');
  const [contextRetry, setContextRetry] = useState(0);
  const [contextRetryOperation, setContextRetryOperation] = useState<
    'read' | 'prepare'
  >('read');
  const [contextExporting, setContextExporting] = useState(false);
  const [contextExportHtml, setContextExportHtml] = useState('');
  const [contextExportUrl, setContextExportUrl] = useState('');
  const requestGeneration = useRef(0);
  const mapRequestGeneration = useRef(0);
  const sceneRequestGeneration = useRef(0);
  const [mapFeatures, setMapFeatures] = useState<ScreeningMapFeatures | null>(
    null,
  );
  const [mapFeaturesAssessmentKey, setMapFeaturesAssessmentKey] = useState('');
  const [mapFeaturesState, setMapFeaturesState] = useState<
    'idle' | 'loading' | 'available' | 'failed'
  >('idle');
  const [mapFeaturesError, setMapFeaturesError] = useState('');
  const [mapScene, setMapScene] = useState<InfrastructureMapScene | null>(null);
  const [mapSceneAssessmentKey, setMapSceneAssessmentKey] = useState('');
  const [mapSceneState, setMapSceneState] = useState<
    'idle' | 'loading' | 'available' | 'failed'
  >('idle');
  const [mapSceneError, setMapSceneError] = useState('');
  const [selectedMapObjectId, setSelectedMapObjectId] = useState<string | null>(
    null,
  );
  const [mapObjectFocusRequest, setMapObjectFocusRequest] = useState(0);
  const selectedAssessmentId = navigation
    ? navigation.selectedAssessmentId
    : localSelectedAssessmentId;
  const tab = navigation ? navigation.tab : localTab;
  const panelOpen = navigation ? navigation.panelOpen : localPanelOpen;
  const setSelectedAssessmentId = (
    id: string | null,
    method: 'push' | 'replace' = 'push',
  ) => {
    if (navigation) navigation.onAssessmentChange(id, method);
    else setLocalSelectedAssessmentId(id);
  };
  const setTab = (
    next: WorkspaceTab,
    method: 'push' | 'replace' = 'push',
  ) => {
    if (navigation) navigation.onTabChange(next, method);
    else setLocalTab(next);
  };
  const setPanelOpen = (
    next: boolean,
    method: 'push' | 'replace' = 'push',
  ) => {
    if (navigation) navigation.onPanelOpenChange(next, method);
    else setLocalPanelOpen(next);
  };

  const assessment = useMemo(
    () => resolveWorkspaceAssessment(site, history, selectedAssessmentId),
    [site, history, selectedAssessmentId],
  );
  const assessmentKey = assessment ? screeningAssessmentKey(assessment) : '';
  const assessmentId = assessment?.id;
  const assessmentSiteId = assessment?.site_id;
  const assessmentVersion = assessment?.version;

  function clearArtifactViews() {
    setFinding(null);
    setMapFocus(null);
    setSelectedMapObjectId(null);
    setMapObjectFocusRequest(0);
    setReportHtml('');
    setContextExportHtml('');
  }

  function resetForSite() {
    setSelectedAssessmentId(null, 'replace');
    setTab('overview', 'replace');
    setWetlandSection('overview');
    setPanelOpen(true, 'replace');
    clearArtifactViews();
  }

  useEffect(
    () => () => {
      if (reportUrl) URL.revokeObjectURL(reportUrl);
    },
    [reportUrl],
  );
  useEffect(
    () => () => {
      if (contextExportUrl) URL.revokeObjectURL(contextExportUrl);
    },
    [contextExportUrl],
  );

  useEffect(() => {
    if (!assessmentId || !assessmentSiteId || assessmentVersion === undefined)
      return;
    const abort = new AbortController();
    const generation = ++requestGeneration.current;
    void readScreeningContext(
      {
        id: assessmentId,
        site_id: assessmentSiteId,
        version: assessmentVersion,
      },
      abort.signal,
    )
      .then((next) => {
        if (abort.signal.aborted || generation !== requestGeneration.current)
          return;
        setContextRun(next.run);
        setContextError(next.error);
        setContextState(next.state);
        setContextAssessmentKey(assessmentKey);
        setContextRetryOperation('read');
      })
      .catch((cause: Error) => {
        if (abort.signal.aborted || generation !== requestGeneration.current)
          return;
        setContextRun(null);
        setContextError(cause.message);
        setContextState('failed');
        setContextAssessmentKey(assessmentKey);
        setContextRetryOperation('read');
      });
    return () => {
      requestGeneration.current += 1;
      abort.abort();
    };
  }, [
    assessmentId,
    assessmentKey,
    assessmentSiteId,
    assessmentVersion,
    contextRetry,
  ]);

  useEffect(() => {
    if (contextAssessmentKey !== assessmentKey || !contextRun) return;
    const abort = new AbortController();
    const generation = ++mapRequestGeneration.current;
    void readScreeningMapFeatures(contextRun, abort.signal)
      .then((next) => {
        if (abort.signal.aborted || generation !== mapRequestGeneration.current)
          return;
        setMapFeatures(next);
        setMapFeaturesAssessmentKey(assessmentKey);
        setMapFeaturesState('available');
        setMapFeaturesError('');
        setSelectedMapObjectId(null);
      })
      .catch((cause: Error) => {
        if (abort.signal.aborted || generation !== mapRequestGeneration.current)
          return;
        setMapFeatures(null);
        setMapFeaturesAssessmentKey(assessmentKey);
        setMapFeaturesState('failed');
        setMapFeaturesError(cause.message);
        setSelectedMapObjectId(null);
      });
    return () => {
      mapRequestGeneration.current += 1;
      abort.abort();
    };
  }, [assessmentKey, contextAssessmentKey, contextRun]);

  useEffect(() => {
    if (contextAssessmentKey !== assessmentKey || !contextRun) return;
    const abort = new AbortController();
    const generation = ++sceneRequestGeneration.current;
    void readInfrastructureMapScene(contextRun, abort.signal)
      .then((next) => {
        if (abort.signal.aborted || generation !== sceneRequestGeneration.current)
          return;
        setMapScene(next);
        setMapSceneAssessmentKey(assessmentKey);
        setMapSceneState('available');
        setMapSceneError('');
        setSelectedMapObjectId(null);
      })
      .catch((cause: Error) => {
        if (abort.signal.aborted || generation !== sceneRequestGeneration.current)
          return;
        setMapScene(null);
        setMapSceneAssessmentKey(assessmentKey);
        setMapSceneState('failed');
        setMapSceneError(cause.message);
        setSelectedMapObjectId(null);
      });
    return () => {
      sceneRequestGeneration.current += 1;
      abort.abort();
    };
  }, [assessmentKey, contextAssessmentKey, contextRun]);

  function applyContextFailure(cause: unknown, operation: 'read' | 'prepare') {
    const status =
      cause instanceof ScreeningContextRequestError ? cause.status : undefined;
    setContextRun(null);
    setContextError(
      cause instanceof Error
        ? cause.message
        : 'Screening Context preparation failed.',
    );
    setContextState(
      status === 409
        ? 'unsupported'
        : status === 401 || status === 403
          ? 'unauthorized'
          : 'failed',
    );
    setContextAssessmentKey(assessmentKey);
    setContextRetryOperation(operation);
  }

  async function prepareContext() {
    if (!assessment) return;
    setContextState('preparing');
    setContextError('');
    try {
      const value = await requestScreeningContext(assessment, 'POST');
      setContextRun(value);
      setContextState('available');
      setContextAssessmentKey(assessmentKey);
    } catch (cause) {
      applyContextFailure(cause, 'prepare');
    }
  }

  function retryContext() {
    setContextError('');
    if (contextRetryOperation === 'prepare') void prepareContext();
    else {
      setContextState('checking');
      setContextRetry((value) => value + 1);
    }
  }

  async function exportContext() {
    if (!assessment) return;
    setContextExporting(true);
    setContextError('');
    try {
      const response = await contextResponse(
        await fetch(contextPath(assessment.id) + '/report', {
          headers: contextHeaders(),
          cache: 'no-store',
        }),
      );
      const html = await response.text();
      if (contextExportUrl) URL.revokeObjectURL(contextExportUrl);
      setContextExportHtml(html);
      setContextExportUrl(
        URL.createObjectURL(new Blob([html], { type: 'text/html' })),
      );
    } catch (cause) {
      setContextError(
        cause instanceof Error
          ? cause.message
          : 'Screening Context export failed.',
      );
    } finally {
      setContextExporting(false);
    }
  }

  async function exportWetlandReport(load: () => Promise<string>) {
    const html = await load();
    if (reportUrl) URL.revokeObjectURL(reportUrl);
    setReportHtml(html);
    setReportUrl(URL.createObjectURL(new Blob([html], { type: 'text/html' })));
  }

  function selectAssessment(id: string) {
    setSelectedAssessmentId(id);
    setTab('overview', 'replace');
    setWetlandSection('overview');
    clearArtifactViews();
  }

  function returnToLatest() {
    setSelectedAssessmentId(null);
    setTab('overview', 'replace');
    setWetlandSection('overview');
    clearArtifactViews();
  }

  function showOnMap(key: string) {
    setSelectedMapObjectId(null);
    setMapFocus((previous) => ({
      key,
      request: (previous?.request || 0) + 1,
    }));
  }

  const scopedMapFeatures =
    contextAssessmentKey === assessmentKey &&
    contextState === 'available' &&
    contextRun &&
    mapFeaturesAssessmentKey === assessmentKey &&
    mapFeatures?.run_id === contextRun.id
      ? mapFeatures
      : null;

  const scopedMapScene =
    contextAssessmentKey === assessmentKey &&
    contextState === 'available' &&
    contextRun &&
    mapSceneAssessmentKey === assessmentKey &&
    mapScene?.snapshot.id === contextRun.evidence_snapshot_id
      ? mapScene
      : null;

  function selectMapObject(id: string) {
    if (!scopedMapScene?.features.some((feature) => feature.id === id))
      return;
    setFinding(null);
    setMapFocus(null);
    setPanelOpen(true);
    setSelectedMapObjectId(id);
  }

  function locateMapObject(id: string) {
    selectMapObject(id);
    setMapObjectFocusRequest((request) => request + 1);
  }

  const selectedMapObject =
    scopedMapScene?.features.find(
      (feature) => feature.id === selectedMapObjectId,
    ) || null;
  const effectiveMapFeaturesState =
    contextAssessmentKey === assessmentKey && contextState === 'unsupported'
        ? ('unsupported' as const)
        : contextAssessmentKey === assessmentKey && contextState === 'absent'
          ? ('unavailable' as const)
          : contextAssessmentKey !== assessmentKey ||
              contextState === 'checking' ||
              contextState === 'preparing'
            ? ('loading' as const)
            : contextState === 'failed' || contextState === 'unauthorized'
              ? ('failed' as const)
              : scopedMapFeatures
                ? ('available' as const)
                : mapFeaturesAssessmentKey === assessmentKey &&
                    contextRun &&
                    mapFeatures?.run_id === contextRun.id &&
                    mapFeaturesState === 'failed'
                  ? ('failed' as const)
                  : contextRun
                    ? ('loading' as const)
                    : ('idle' as const);
  const effectiveMapSceneState =
    contextAssessmentKey === assessmentKey && contextState === 'unsupported'
      ? ('unsupported' as const)
      : contextAssessmentKey === assessmentKey && contextState === 'absent'
        ? ('unavailable' as const)
        : contextAssessmentKey !== assessmentKey ||
            contextState === 'checking' ||
            contextState === 'preparing'
          ? ('loading' as const)
          : contextState === 'failed' || contextState === 'unauthorized'
            ? ('failed' as const)
            : scopedMapScene
              ? ('available' as const)
              : mapSceneAssessmentKey === assessmentKey &&
                  contextRun &&
                  mapSceneState === 'failed'
                ? ('failed' as const)
                : contextRun
                  ? ('loading' as const)
                  : ('idle' as const);

  return {
    assessment,
    selectedAssessmentId:
      selectedAssessmentId &&
      history.some(
        (item) => item.id === selectedAssessmentId && item.site_id === site?.id,
      )
        ? selectedAssessmentId
        : null,
    tab,
    setTab,
    wetlandSection,
    setWetlandSection,
    panelOpen,
    setPanelOpen,
    mapFocus,
    finding,
    setFinding,
    showOnMap,
    mapEvidence: {
      features: scopedMapFeatures,
      state: effectiveMapFeaturesState,
      error: mapFeaturesError,
      scene: scopedMapScene,
      sceneState: effectiveMapSceneState,
      sceneError: mapSceneError,
      selectedObjectId: selectedMapObjectId,
      selectedObject: selectedMapObject,
      focusRequest: mapObjectFocusRequest,
      selectObject: selectMapObject,
      locateObject: locateMapObject,
      clearSelection: () => setSelectedMapObjectId(null),
    },
    selectAssessment,
    returnToLatest,
    resetForSite,
    reportHtml,
    reportUrl,
    closeWetlandReport: () => {
      setReportHtml('');
      if (reportUrl) URL.revokeObjectURL(reportUrl);
      setReportUrl('');
    },
    exportWetlandReport,
    context: {
      run: contextAssessmentKey === assessmentKey ? contextRun : null,
      state: !assessment
        ? ('idle' as const)
        : contextAssessmentKey === assessmentKey
          ? contextState
          : ('checking' as const),
      error: contextAssessmentKey === assessmentKey ? contextError : '',
      exporting: contextExporting,
      exportHtml: contextExportHtml,
      exportUrl: contextExportUrl,
      prepare: prepareContext,
      retry: retryContext,
      exportReport: exportContext,
      closeExport: () => {
        setContextExportHtml('');
        if (contextExportUrl) URL.revokeObjectURL(contextExportUrl);
        setContextExportUrl('');
      },
    },
  };
}

export type SiteWorkspaceState = ReturnType<typeof useSiteWorkspaceState>;
