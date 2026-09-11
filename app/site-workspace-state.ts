'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  contextHeaders,
  contextPath,
  contextResponse,
  readScreeningContext,
  readScreeningMapFeatures,
  requestScreeningContext,
  screeningAssessmentKey,
  ScreeningContextRequestError,
  type ScreeningRun,
  type ScreeningMapFeature,
  type ScreeningMapFeatures,
} from './screening-context';
import {
  resolveWorkspaceAssessment,
  type WorkspaceAssessment as Assessment,
  type WorkspaceSite as Site,
} from './site-workspace-view-model';
import type { OverlayFinding } from './site-evidence';

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
export type MapInspection = OverlayFinding | ScreeningMapFeature;

export function useSiteWorkspaceState(
  site: Site | undefined,
  history: Assessment[],
) {
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<
    string | null
  >(null);
  const [tab, setTab] = useState<WorkspaceTab>('overview');
  const [wetlandSection, setWetlandSection] =
    useState<WetlandSection>('overview');
  const [panelOpen, setPanelOpen] = useState(true);
  const [mapFocus, setMapFocus] = useState<{
    key: string;
    request: number;
  } | null>(null);
  const [finding, setFinding] = useState<MapInspection | null>(null);
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
  const [contextMap, setContextMap] = useState<ScreeningMapFeatures | null>(
    null,
  );
  const [contextMapError, setContextMapError] = useState('');
  const requestGeneration = useRef(0);
  const mapRequestGeneration = useRef(0);

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
    setReportHtml('');
    setContextExportHtml('');
  }

  function resetForSite() {
    setSelectedAssessmentId(null);
    setTab('overview');
    setWetlandSection('overview');
    setPanelOpen(true);
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
    if (!contextRun || contextAssessmentKey !== assessmentKey) return;
    const abort = new AbortController();
    const generation = ++mapRequestGeneration.current;
    void readScreeningMapFeatures(contextRun, abort.signal)
      .then((map) => {
        if (abort.signal.aborted || generation !== mapRequestGeneration.current)
          return;
        setContextMap(map);
      })
      .catch((cause: Error) => {
        if (abort.signal.aborted || generation !== mapRequestGeneration.current)
          return;
        setContextMapError(cause.message);
      });
    return () => {
      mapRequestGeneration.current += 1;
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
    setTab('overview');
    setWetlandSection('overview');
    clearArtifactViews();
  }

  function returnToLatest() {
    setSelectedAssessmentId(null);
    setTab('overview');
    setWetlandSection('overview');
    clearArtifactViews();
  }

  function showOnMap(key: string) {
    setMapFocus((previous) => ({
      key,
      request: (previous?.request || 0) + 1,
    }));
  }

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
      map: contextMap?.run_id === contextRun?.id ? contextMap : null,
      mapError: contextMap?.run_id === contextRun?.id ? contextMapError : '',
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
