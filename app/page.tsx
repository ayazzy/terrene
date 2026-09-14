'use client';
import { useEffect, useState, useCallback, useRef } from 'react';
import {
  readResource,
  criticalReadFailure,
  isAccessFailure,
  type ReadFailure,
} from './refresh-state';
import NaturePanel, { type Observation } from './nature-panel';
import {
  linkedFindings,
  variableLabel,
  observationValue,
} from './site-evidence';
import OverlayFindings from './overlay-findings';
import ScreeningContextPanel from './screening-context-panel';
import MapFeatureInspector from './map-feature-inspector';
import SiteEditorPanel from './site-editor-panel';
import {
  useSiteWorkspaceState,
  type WorkspaceTab,
} from './site-workspace-state';
import ProjectIntelligenceWorkspace from './project-intelligence-workspace';
import EntityDossier from './entity-dossier';
import {
  OperatingCommandBar,
  OperatingRail,
  type ShellSearchResult,
} from './operating-shell';
import shellStyles from './operating-shell.module.css';
import { useOperatingPictureState } from './use-operating-picture-state';
import {
  createLatestRequestFence,
  operatingPictureStatesEqual,
  projectOperatingPictureState,
  reconcileOperatingPictureState,
} from './operating-picture-state';
import type { OverlayFinding } from './site-evidence';
import SiteMap, { type BoundaryDrawingControls } from './map';
import {
  projectInfrastructureEntities,
  searchableInfrastructureEntities,
  infrastructureEntityLabel,
  type InfrastructureEntity,
} from './infrastructure-entities';
import { useInfrastructureEntities } from './use-infrastructure-entities';
import { mapFeatureName } from './infrastructure-map-scene';
import {
  EvidenceBadge,
  WorkspaceLoading,
  WorkspaceState,
} from './status-primitives';
import {
  Plus,
  ArrowUpRight,
  ArrowLeft,
  MapPin,
  Download,
  Play,
  PenLine,
  Info,
  RefreshCw,
  FileText,
  Map as MapIcon,
  List,
  MoreHorizontal,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
const statuses = ['Unreviewed', 'Investigate', 'Hold', 'Archived'];
async function api(path: string, method = 'GET', body?: any): Promise<any> {
  const r = await fetch('/api' + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(sessionStorage.getItem('crc-token')
        ? { Authorization: 'Bearer ' + sessionStorage.getItem('crc-token') }
        : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const e: any = await r
      .json()
      .catch(() => ({ detail: `Request failed (${r.status})` }));
    throw Object.assign(
      new Error(
        typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail),
      ),
      { status: r.status },
    );
  }
  return r.json();
}
const fmt = (n: number) =>
  n.toLocaleString('en-GB', { maximumFractionDigits: 2 });
function Status({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Select value={value} onValueChange={(v) => v && onChange(v)}>
      <SelectTrigger className={'status ' + value.toLowerCase()}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {statuses.map((s) => (
          <SelectItem key={s} value={s}>
            {s}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
export default function Home() {
  const analysisPanel = useRef<HTMLDivElement>(null);
  const analysisCloseButton = useRef<HTMLButtonElement>(null);
  const reopenAnalysisButton = useRef<HTMLButtonElement>(null);
  const siteNameInput = useRef<HTMLInputElement>(null);
  const boundaryDrawingControls = useRef<BoundaryDrawingControls | null>(null);
  const dossierFocusIntent = useRef<'close' | 'reopen' | null>(null);
  const previousAssetId = useRef<string | null>(null);
  const assetReturnFocusIntent = useRef(false);
  const siteReturnPosition = useRef<{
    siteId: string;
    assessmentId: string | null;
    tab: WorkspaceTab;
    top: number;
  } | null>(null);
  const historyRequestFence = useRef(createLatestRequestFence());
  const operatingPicture = useOperatingPictureState();
  const projectEntityIndex = useInfrastructureEntities();
  const operatingState = operatingPicture.state;
  const [sites, setSites] = useState<any[]>([]),
    [datasets, setDatasets] = useState<any[]>([]),
    [error, setError] = useState(''),
    [readErrors, setReadErrors] = useState<{
      sites?: ReadFailure | null;
      datasets?: ReadFailure | null;
      health?: ReadFailure | null;
    }>({}),
    [hasLoadedSites, setHasLoadedSites] = useState(false),
    [refreshing, setRefreshing] = useState(false),
    [historyRead, setHistoryRead] = useState<{
      siteId: string | null;
      failure: ReadFailure | null;
      loaded: boolean;
    }>({ siteId: null, failure: null, loaded: false }),
    [historyRetry, setHistoryRetry] = useState(0),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [newSite, setNewSite] = useState(false),
    [name, setName] = useState(''),
    [notes, setNotes] = useState(''),
    [geometry, setGeometry] = useState<any>(null),
    [drawing, setDrawing] = useState(false),
    [drawSession, setDrawSession] = useState(0),
    [drawPointCount, setDrawPointCount] = useState(0),
    [editing, setEditing] = useState(false),
    [query, setQuery] = useState(''),
    [filter, setFilter] = useState('all'),
    [compare, setCompare] = useState<string[]>([]),
    [history, setHistory] = useState<any[]>([]),
    [email, setEmail] = useState(''),
    [password, setPassword] = useState(''),
    [rawGeometry, setRawGeometry] = useState<any>(null),
    [navigationCompact, setNavigationCompact] = useState(true),
    [mobileNavigation, setMobileNavigation] = useState(false),
    [mapLayersOpen, setMapLayersOpen] = useState(false);
  const operatingProjection = projectOperatingPictureState(operatingState);
  const { view, sitesView, activeSiteId: active } = operatingProjection;
  function setView(next: string) {
    if (next === 'workspace') {
      operatingPicture.transition((currentState) => ({
        ...currentState,
        mode: 'map',
        artifact: null,
        section: 'overview',
        dossierOpen: true,
      }));
    } else if (next === 'project-intelligence') {
      operatingPicture.setMode('project');
    } else if (next === 'compare' || next === 'data') {
      operatingPicture.setMode(next);
    }
  }
  function setSitesView(next: string) {
    if (next === 'map' || next === 'list')
      operatingPicture.transition((currentState) => ({
        ...currentState,
        mode: next,
        artifact: null,
        section: 'overview',
      }));
  }
  const closeMobileNavigation = useCallback(
    () => setMobileNavigation(false),
    [],
  );
  const requestedSiteAssessmentId =
    operatingState.artifact?.kind === 'site_assessment'
      ? operatingState.artifact.id
      : null;
  const requestedProjectSubjectId =
    operatingProjection.selectedProjectSubjectId;
  const requestedProjectRunId = operatingProjection.selectedProjectRunId;
  const requestedSiteSection = (
    ['overview', 'evidence', 'models', 'history'] as const
  ).includes(
    operatingState.section as 'overview' | 'evidence' | 'models' | 'history',
  )
    ? (operatingState.section as 'overview' | 'evidence' | 'models' | 'history')
    : 'overview';
  const current = sites.find((s) => s.id === active);
  const infrastructureEntities = projectInfrastructureEntities(
    sites,
    projectEntityIndex.subjects,
    projectEntityIndex.runs,
  );
  const workspace = useSiteWorkspaceState(current, history, {
    selectedAssessmentId: requestedSiteAssessmentId,
    selectedMapObjectId: operatingState.assetId,
    tab: requestedSiteSection,
    panelOpen: operatingState.dossierOpen,
    onAssessmentChange: (id, method) =>
      operatingPicture.transition(
        (currentState) => ({
          ...currentState,
          artifact: id ? { kind: 'site_assessment', id } : null,
          assetId: null,
          showRelated: false,
        }),
        method,
      ),
    onTabChange: (section, method) =>
      operatingPicture.transition({ section }, method),
    onPanelOpenChange: (dossierOpen, method) =>
      operatingPicture.transition({ dossierOpen }, method),
    onMapObjectChange: (assetId, method) =>
      operatingPicture.transition(
        (currentState) => ({
          ...currentState,
          assetId,
          showRelated: false,
          dossierOpen: assetId ? true : currentState.dossierOpen,
        }),
        method,
      ),
  });
  const {
    assessment,
    selectedAssessmentId: selectedAssessment,
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
    mapEvidence,
  } = workspace;
  const result = assessment?.result,
    viewingHistorical =
      !!assessment && assessment.id !== current?.assessment?.id,
    stale = current && assessment && current.version !== assessment.version,
    newerData =
      result &&
      !readErrors.datasets &&
      datasets.some((d) => !assessment.dataset_ids?.includes(d.id));
  function changeSiteSection(next: WorkspaceTab) {
    setTab(next);
  }
  function changeSitePanel(next: boolean) {
    setPanelOpen(next);
  }
  function collapseSitePanel() {
    dossierFocusIntent.current = 'reopen';
    setPanelOpen(false);
  }
  function reopenSitePanel() {
    dossierFocusIntent.current = 'close';
    setPanelOpen(true);
  }
  function returnToSiteDiligence() {
    assetReturnFocusIntent.current = true;
    mapEvidence.clearSelection();
  }
  function selectSiteAssessment(id: string | null) {
    if (id) workspace.selectAssessment(id);
    else workspace.returnToLatest();
  }
  const overlayFinding = finding;
  const historyFailure =
    historyRead.siteId === active ? historyRead.failure : null;
  const criticalRead = criticalReadFailure(
    { ...readErrors, history: historyFailure },
    hasLoadedSites,
  );
  const criticalError =
    error ||
    (criticalRead
      ? isAccessFailure(criticalRead)
        ? `Sign-in or access required: ${criticalRead.message}`
        : `Saved sites unavailable: ${criticalRead.message}`
      : '');
  const refreshFailures = [
    {
      label: 'Latest site details and assessment status',
      failure: readErrors.sites,
    },
    { label: 'Reference dataset updates', failure: readErrors.datasets },
    { label: 'Application service status', failure: readErrors.health },
    { label: 'Assessment history', failure: historyFailure },
  ].filter((item) => item.failure);
  const showRefreshNotice = refreshFailures.length > 0 && !criticalRead;
  useEffect(() => {
    if (mapEvidence.selectedObjectId) return;
    analysisPanel.current?.scrollTo({ top: 0 });
  }, [tab, assessment?.id, current?.id, mapEvidence.selectedObjectId]);
  useEffect(() => {
    const nextAssetId = mapEvidence.selectedObjectId;
    const priorAssetId = previousAssetId.current;
    let animation = 0;
    if (!priorAssetId && nextAssetId) {
      siteReturnPosition.current = current
        ? {
            siteId: current.id,
            assessmentId: assessment?.id || null,
            tab,
            top: analysisPanel.current?.scrollTop || 0,
          }
        : null;
      analysisPanel.current?.scrollTo({ top: 0 });
    } else if (priorAssetId && !nextAssetId) {
      const returnPosition = siteReturnPosition.current;
      const shouldRestore =
        !!returnPosition &&
        !!current &&
        returnPosition.siteId === current.id &&
        returnPosition.assessmentId === (assessment?.id || null) &&
        returnPosition.tab === tab;
      const returnTop =
        shouldRestore && returnPosition ? returnPosition.top : 0;
      animation = requestAnimationFrame(() => {
        analysisPanel.current?.scrollTo({ top: returnTop });
        if (assetReturnFocusIntent.current) {
          analysisPanel.current
            ?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')
            ?.focus();
          assetReturnFocusIntent.current = false;
        }
      });
      siteReturnPosition.current = null;
    } else if (priorAssetId && nextAssetId && priorAssetId !== nextAssetId) {
      analysisPanel.current?.scrollTo({ top: 0 });
    }
    previousAssetId.current = nextAssetId;
    return () => cancelAnimationFrame(animation);
  }, [assessment?.id, current, mapEvidence.selectedObjectId, tab]);
  useEffect(() => {
    const intent = dossierFocusIntent.current;
    if (!intent) return;
    dossierFocusIntent.current = null;
    const animation = requestAnimationFrame(() => {
      if (intent === 'close') analysisCloseButton.current?.focus();
      else reopenAnalysisButton.current?.focus();
    });
    return () => cancelAnimationFrame(animation);
  }, [panelOpen]);
  const reload = useCallback(async () => {
    setRefreshing(true);
    const [siteRead, datasetRead, healthRead] = await Promise.all([
      readResource(() => api('/sites')),
      readResource(() => api('/datasets')),
      readResource(() => api('/health')),
    ]);
    if (!siteRead.failure && 'data' in siteRead) {
      setSites(siteRead.data);
      setHasLoadedSites(true);
    }
    if (!datasetRead.failure && 'data' in datasetRead)
      setDatasets(datasetRead.data);
    setReadErrors({
      sites: siteRead.failure,
      datasets: datasetRead.failure,
      health: healthRead.failure,
    });
    setLoading(false);
    setRefreshing(false);
  }, []);
  useEffect(() => {
    void reload();
  }, [reload]);
  useEffect(() => {
    const requestFence = historyRequestFence.current;
    const request = requestFence.begin();
    if (!active) return;
    void readResource(() => api('/sites/' + active + '/assessments')).then(
      (read) => {
        if (!requestFence.isCurrent(request)) return;
        if (!read.failure && 'data' in read) setHistory(read.data);
        setHistoryRead({
          siteId: active,
          failure: read.failure,
          loaded: !read.failure,
        });
      },
    );
    return () => {
      requestFence.invalidate();
    };
  }, [active, sites, historyRetry]);
  useEffect(() => {
    if (!hasLoadedSites || !operatingState.selection) return;
    const availability = {
      siteIds: sites.map((site) => String(site.id)),
      ...(historyRead.siteId === active && historyRead.loaded
        ? {
            siteAssessmentIds: history.map((item) => String(item.id)),
          }
        : {}),
      ...(mapEvidence.sceneState === 'available' && mapEvidence.scene
        ? {
            mapObjectIds: mapEvidence.scene.features.map((item) => item.id),
          }
        : ['failed', 'unavailable', 'unsupported'].includes(
              mapEvidence.sceneState,
            )
          ? { mapObjectIds: [] }
          : {}),
    };
    const reconciled = reconcileOperatingPictureState(
      operatingState,
      availability,
    );
    if (!operatingPictureStatesEqual(operatingState, reconciled))
      operatingPicture.transition(reconciled, 'replace');
  }, [
    active,
    hasLoadedSites,
    history,
    historyRead.loaded,
    historyRead.siteId,
    mapEvidence.scene,
    mapEvidence.sceneState,
    operatingPicture,
    operatingState,
    sites,
  ]);
  function retryReads() {
    setHistoryRetry((value) => value + 1);
    void reload();
  }
  const refreshNotice = showRefreshNotice && (
    <section
      className="refresh-notice"
      aria-label="Source refresh availability"
    >
      <div className="refresh-notice-heading">
        <p role="status">
          <strong>Source refresh unavailable</strong>
          <span>
            {result
              ? 'Saved assessment evidence remains available.'
              : 'Showing the site data already loaded.'}
          </span>
        </p>
        <button className="text-btn" disabled={refreshing} onClick={retryReads}>
          <RefreshCw size={13} />
          {refreshing ? 'Retrying…' : 'Retry'}
        </button>
      </div>
      <details>
        <summary>Unavailable data · {refreshFailures.length}</summary>
        <ul>
          {refreshFailures.map(({ label, failure }) => (
            <li key={label}>
              <strong>{label}</strong>
              <span>{failure?.message}</span>
            </li>
          ))}
        </ul>
        <p>
          Values already loaded are retained. Current source changes could not
          be checked.
        </p>
      </details>
    </section>
  );
  useEffect(() => {
    if (!sites.some((s) => ['queued', 'running'].includes(s.assessment?.state)))
      return;
    const timer = setInterval(reload, 1800);
    return () => clearInterval(timer);
  }, [sites, reload]);
  useEffect(() => {
    const ctx = (document as any).modelContext;
    if (!ctx) return;
    const life = new AbortController();
    Promise.resolve(
      ctx.registerTool(
        {
          name: 'list_crc_sites',
          description:
            'Read saved Terrene sites and review decisions in the current organization.',
          inputSchema: {
            type: 'object',
            properties: {},
            additionalProperties: false,
          },
          annotations: { readOnlyHint: true, untrustedContentHint: true },
          execute: async (input: any) => {
            if (input && Object.keys(input).length)
              throw new Error('No arguments accepted');
            return (await api('/sites')).map((s: any) => ({
              id: s.id,
              name: s.name,
              status: s.status,
              boundary_version: s.version,
            }));
          },
        },
        { signal: life.signal },
      ),
    ).catch(() => {});
    return () => life.abort();
  }, []);
  async function act(fn: () => Promise<any>) {
    setBusy(true);
    setError('');
    try {
      await fn();
      await reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  function openSite(s: any) {
    workspace.resetForSite();
    setHistory([]);
    operatingPicture.selectEntity({ kind: 'site', id: s.id }, 'site');
  }
  function startNew() {
    setEditing(false);
    setName('');
    setNotes('');
    setGeometry(null);
    setRawGeometry(null);
    setDrawing(false);
    setDrawPointCount(0);
    setError('');
    operatingPicture.transition(
      (currentState) => ({
        ...currentState,
        mode: 'map',
        selection: null,
        artifact: null,
        assetId: null,
        showRelated: false,
        section: 'overview',
        dossierOpen: true,
      }),
      'push',
    );
    setNewSite(true);
  }
  function closeSiteEditor() {
    setNewSite(false);
    setDrawing(false);
    setDrawPointCount(0);
    setEditing(false);
    setGeometry(null);
    setRawGeometry(null);
    setError('');
  }
  async function save() {
    await act(async () => {
      const s = await api(
        editing ? '/sites/' + active : '/sites',
        editing ? 'PATCH' : 'POST',
        {
          name,
          notes,
          ...(geometry ? { geometry: rawGeometry || geometry } : {}),
          ...(editing ? { expected_version: current.version } : {}),
        },
      );
      closeSiteEditor();
      workspace.resetForSite();
      operatingPicture.selectEntity({ kind: 'site', id: s.id }, 'site');
    });
  }
  async function upload(file?: File) {
    if (!file) return;
    try {
      if (file.size > 500000) throw new Error('Maximum file size is 500 KB');
      const v = JSON.parse(await file.text());
      if (v.crs || v.geometry?.crs)
        throw new Error('Use WGS84 GeoJSON with no CRS member.');
      const g =
        v.type === 'FeatureCollection'
          ? v.features.length === 1
            ? v.features[0].geometry
            : null
          : v.type === 'Feature'
            ? v.geometry
            : v;
      if (!g || !['Polygon', 'MultiPolygon'].includes(g.type))
        throw new Error('Upload one Polygon or MultiPolygon feature.');
      setGeometry(g);
      setRawGeometry(v);
      setError('');
    } catch (e: any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    if (!newSite) return;
    const frame = requestAnimationFrame(() => siteNameInput.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [newSite]);
  async function report() {
    if (!assessment) return;
    await act(async () => {
      const r = await fetch('/api/assessments/' + assessment.id + '/report', {
        headers: sessionStorage.getItem('crc-token')
          ? { Authorization: 'Bearer ' + sessionStorage.getItem('crc-token') }
          : {},
      });
      if (!r.ok) throw new Error('Report is unavailable');
      await workspace.exportWetlandReport(() => r.text());
    });
  }
  async function createAssessment() {
    await act(async () => {
      await api('/sites/' + active + '/assessments', 'POST');
      workspace.resetForSite();
    });
  }
  const filtered = sites.filter(
    (s) =>
      s.name.toLowerCase().includes(query.toLowerCase()) &&
      (filter === 'all' || s.status === filter),
  );
  const availableSourceCount = datasets.filter(
    (dataset) => dataset.state === 'available',
  ).length;
  const retainedSceneSources =
    view === 'site' ? mapEvidence.scene?.sources || [] : [];
  const sourceTimes = (
    retainedSceneSources.length
      ? retainedSceneSources.map((source) => source.retrieved_at)
      : datasets.map((dataset) => dataset.retrieved)
  )
    .map((retrieved) => Date.parse(retrieved))
    .filter(Number.isFinite);
  const latestSourceTime = sourceTimes.length ? Math.max(...sourceTimes) : null;
  const sourceAsOf = latestSourceTime
    ? `As of ${new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      }).format(new Date(latestSourceTime))}`
    : loading
      ? 'Dates loading'
      : 'Dates unavailable';
  const sourceState = retainedSceneSources.length
    ? 'available'
    : view === 'site' && mapEvidence.sceneState === 'loading'
      ? 'loading'
      : loading && !datasets.length
        ? 'loading'
        : !datasets.length
          ? 'unavailable'
          : readErrors.datasets || availableSourceCount < datasets.length
            ? 'partial'
            : 'available';
  const sourceStatus = retainedSceneSources.length
    ? `${retainedSceneSources.length} retained`
    : view === 'site' && mapEvidence.sceneState === 'loading'
      ? 'Loading'
      : loading && !datasets.length
        ? 'Loading'
        : !datasets.length
          ? readErrors.datasets
            ? 'Unavailable'
            : 'No sources recorded'
          : `${availableSourceCount} / ${datasets.length} available`;
  const commandSearchResults: ShellSearchResult[] =
    searchableInfrastructureEntities(infrastructureEntities, query, 8).map(
      (entity) => ({
        id: entity.id,
        name: entity.name,
        kind: entity.kind,
        detail: infrastructureEntityLabel(entity),
        evidenceState: entity.evidenceState,
      }),
    );
  const selectedInfrastructureEntity = infrastructureEntities.find(
    (entity) =>
      entity.kind === operatingState.selection?.kind &&
      entity.id === operatingState.selection.id,
  );
  const spatialView =
    newSite ||
    (view === 'workspace' && sitesView === 'map') ||
    view === 'site' ||
    view === 'project-intelligence';
  const selectedMapGeometry =
    view === 'site' && current
      ? viewingHistorical
        ? assessment?.geometry || null
        : current.geometry
      : selectedInfrastructureEntity?.geometry || null;
  const editorMapGeometry = newSite
    ? geometry || (editing ? current?.geometry || null : null)
    : selectedMapGeometry;
  function openInfrastructureEntity(entity: InfrastructureEntity) {
    setQuery('');
    if (entity.kind === 'site') openSite(entity.site);
    else
      operatingPicture.transition({
        mode: 'project',
        selection: { kind: 'project_subject', id: entity.id },
        artifact: null,
        section: 'overview',
        dossierOpen: true,
      });
  }
  function openSearchResult(result: ShellSearchResult) {
    const entity = infrastructureEntities.find(
      (item) => item.kind === result.kind && item.id === result.id,
    );
    if (entity) openInfrastructureEntity(entity);
  }
  const viewLabel =
    view === 'site'
      ? current?.name || 'Site investigation'
      : view === 'project-intelligence'
        ? 'Project intelligence'
        : view === 'data'
          ? 'Source register'
          : view === 'compare'
            ? 'Site comparison'
            : sitesView === 'list'
              ? 'Site roster'
              : 'Geographic overview';
  return (
    <main className={`crc-shell ${shellStyles.shell}`}>
      <OperatingRail
        view={view}
        siteCount={sites.length}
        compact={navigationCompact}
        mobileOpen={mobileNavigation}
        onViewChange={(next) => {
          setView(next);
          setMobileNavigation(false);
        }}
        onCompactChange={() => setNavigationCompact((value) => !value)}
        onMobileClose={closeMobileNavigation}
      />
      <section
        className={`main${spatialView ? ' spatial-main' : ''}${view === 'site' ? ' analysis-main' : ''}${view === 'workspace' && sitesView === 'map' ? ' portfolio-main' : ''}${view === 'workspace' && sitesView === 'list' ? ' portfolio-list-main' : ''}`}
      >
        <OperatingCommandBar
          viewLabel={viewLabel}
          query={query}
          searchResults={commandSearchResults}
          onQueryChange={setQuery}
          onOpenEntity={openSearchResult}
          onMobileMenu={() => setMobileNavigation((value) => !value)}
          mobileNavigationOpen={mobileNavigation}
          sourceStatus={sourceStatus}
          sourceAsOf={sourceAsOf}
          sourceState={sourceState}
          refreshing={refreshing}
          onRefresh={retryReads}
        />
        {criticalError && view !== 'project-intelligence' && (
          <div role="alert" className="alert error">
            {criticalError}
            {criticalRead && (
              <button disabled={refreshing} onClick={retryReads}>
                <RefreshCw size={14} /> Retry
              </button>
            )}
          </div>
        )}
        {view !== 'site' && view !== 'project-intelligence' && refreshNotice}
        {spatialView && (
          <div className="operating-spatial-map">
            <SiteMap
              geometry={editorMapGeometry}
              findings={view === 'site' ? result?.findings : []}
              selected={view === 'site' ? mapFocus?.key : undefined}
              focusRequest={view === 'site' ? mapFocus?.request : undefined}
              boundaryLabel={
                newSite
                  ? geometry
                    ? 'Staged Site boundary'
                    : editing
                      ? `Reference boundary v${current?.version}`
                      : 'New Site boundary'
                  : view === 'site' && current
                    ? `Boundary v${viewingHistorical ? assessment?.version : current.version}${viewingHistorical ? ' · historical assessment' : ''}`
                    : 'Current saved Site boundaries'
              }
              draw={newSite && drawing}
              drawSession={drawSession}
              drawControlsRef={boundaryDrawingControls}
              onDrawProgress={setDrawPointCount}
              boundaryEditing={newSite}
              onDraw={(nextGeometry) => {
                setRawGeometry(null);
                setGeometry(nextGeometry);
                setDrawing(false);
                setDrawPointCount(0);
              }}
              onInspect={(finding) => {
                if (view !== 'site') return;
                showOnMap(finding.key);
                setFinding(finding);
              }}
              mapScene={view === 'site' ? mapEvidence.scene : null}
              mapSceneState={view === 'site' ? mapEvidence.sceneState : 'idle'}
              mapSceneError={view === 'site' ? mapEvidence.sceneError : ''}
              selectedMapObject={
                view === 'site' ? mapEvidence.selectedObjectId : null
              }
              showRelatedObjects={view === 'site' && operatingState.showRelated}
              mapObjectFocusRequest={
                view === 'site' ? mapEvidence.focusRequest : 0
              }
              onInspectMapObject={(id) => {
                if (view !== 'site') return;
                mapEvidence.selectObject(id);
              }}
              onClearMapObject={mapEvidence.clearSelection}
              hiddenLayerIds={operatingState.hiddenLayers}
              onHiddenLayerIdsChange={operatingPicture.setHiddenLayers}
              layersOpen={mapLayersOpen}
              onLayersOpenChange={setMapLayersOpen}
              entities={infrastructureEntities}
              selectedEntity={operatingState.selection}
              onSelectEntity={(selection) => {
                if (!selection) {
                  operatingPicture.selectEntity(null, 'map');
                  return;
                }
                const entity = infrastructureEntities.find(
                  (item) =>
                    item.kind === selection.kind && item.id === selection.id,
                );
                if (!entity) return;
                openInfrastructureEntity(entity);
              }}
              onOpenEntity={openInfrastructureEntity}
              entityLoading={loading || projectEntityIndex.loading}
              entityUnavailable={
                (!hasLoadedSites && !!readErrors.sites) ||
                (!!projectEntityIndex.error &&
                  !projectEntityIndex.subjects.length)
              }
              workflowLevel={
                view === 'site'
                  ? mapEvidence.selectedObject
                    ? 'asset'
                    : 'site'
                  : 'portfolio'
              }
              workflowAssetLabel={
                mapEvidence.selectedObject
                  ? mapFeatureName(mapEvidence.selectedObject)
                  : undefined
              }
              portfolioView={
                view === 'workspace' && !newSite ? sitesView : undefined
              }
              onPortfolioViewChange={
                view === 'workspace' && !newSite ? setSitesView : undefined
              }
              onAddSite={
                view === 'workspace' && !newSite ? startNew : undefined
              }
              onOpenPortfolio={() => setView('workspace')}
              onOpenSiteDiligence={() => mapEvidence.clearSelection()}
              onOpenDossier={
                (view === 'site' || view === 'project-intelligence') &&
                !panelOpen
                  ? reopenSitePanel
                  : undefined
              }
              dossierOpen={
                newSite ||
                ((view === 'site' || view === 'project-intelligence') &&
                  panelOpen)
              }
              openDossierButtonRef={reopenAnalysisButton}
            />
          </div>
        )}
        <ProjectIntelligenceWorkspace
          enabled={view === 'project-intelligence'}
          selectedSubjectId={requestedProjectSubjectId}
          selectedRunId={requestedProjectRunId}
          section={operatingState.section}
          dossierOpen={operatingState.dossierOpen}
          locationLabel={
            selectedInfrastructureEntity
              ? infrastructureEntityLabel(selectedInfrastructureEntity)
              : 'Project Subject · geography not established'
          }
          closeButtonRef={analysisCloseButton}
          onCollapse={collapseSitePanel}
          layersOpen={mapLayersOpen}
          onOpenLayers={() => setMapLayersOpen((open) => !open)}
          onSubjectChange={(id, method) =>
            operatingPicture.transition(
              (currentState) => ({
                ...currentState,
                mode: 'project',
                selection: id ? { kind: 'project_subject', id } : null,
                artifact: null,
                section: 'overview',
                dossierOpen: true,
              }),
              method,
            )
          }
          onRunChange={(id, method) =>
            operatingPicture.transition(
              (currentState) => ({
                ...currentState,
                artifact: id ? { kind: 'project_intelligence_run', id } : null,
                section: id ? currentState.section : 'overview',
              }),
              method,
            )
          }
          onSectionChange={operatingPicture.setSection}
        />
        {view === 'workspace' && (
          <Tabs
            className="sites-views"
            value={sitesView}
            onValueChange={(value) => setSitesView(String(value))}
          >
            {sitesView === 'list' && (
              <div className="sites-view-bar">
                <TabsList aria-label="Sites view">
                  <TabsTrigger value="map">
                    <MapIcon size={16} /> Map
                  </TabsTrigger>
                  <TabsTrigger value="list">
                    <List size={16} /> List
                  </TabsTrigger>
                </TabsList>
                <button className="primary" onClick={startNew}>
                  <Plus size={16} /> Add site
                </button>
              </div>
            )}
            <TabsContent value="map" className="sites-map-panel">
              <p className="sr-only">
                The persistent infrastructure map contains the Site and Project
                Subject entity index.
              </p>
            </TabsContent>
            <TabsContent value="list" className="portfolio-list-panel">
              <div className="portfolio-status-strip">
                <div>
                  <h1>Infrastructure site roster</h1>
                  <p>
                    Evidence coverage, screening state and team review remain
                    separate.
                  </p>
                </div>
                <span>
                  {filtered.length.toString().padStart(2, '0')} visible of{' '}
                  {sites.length.toString().padStart(2, '0')} retained sites
                </span>
              </div>
              <div className="workspace-content portfolio-ledger">
                <section
                  className="workspace-summary portfolio-summary"
                  aria-label="Portfolio summary"
                >
                  <div className="portfolio-metric">
                    <span className="portfolio-metric-index">01</span>
                    <b>{sites.length.toString().padStart(2, '0')}</b>
                    <span>Retained sites</span>
                  </div>
                  <div className="portfolio-metric">
                    <span className="portfolio-metric-index">02</span>
                    <b>
                      {sites
                        .filter((s) => s.status === 'Investigate')
                        .length.toString()
                        .padStart(2, '0')}
                    </b>
                    <span>Active investigations</span>
                  </div>
                  <div className="portfolio-metric">
                    <span className="portfolio-metric-index">03</span>
                    <b>
                      {datasets.filter((d) => d.state === 'available').length} /{' '}
                      {datasets.length}
                    </b>
                    <span>Reference layers online</span>
                  </div>
                  <div className="portfolio-protocol">
                    <Info size={16} />
                    <span>
                      <b>Screening protocol</b>
                      Wetland model v0.1 · decision support only
                    </span>
                  </div>
                </section>
                <div className="toolbar portfolio-toolbar">
                  <Select
                    value={filter}
                    onValueChange={(v) => v && setFilter(v)}
                  >
                    <SelectTrigger>
                      <SelectValue>
                        {filter === 'all' ? 'All review statuses' : filter}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All review statuses</SelectItem>
                      {statuses.map((s) => (
                        <SelectItem value={s} key={s}>
                          {s}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="portfolio-result-count">
                    {filtered.length.toString().padStart(2, '0')} /{' '}
                    {sites.length.toString().padStart(2, '0')} sites
                  </span>
                  <button
                    className="portfolio-compare"
                    disabled={compare.length < 2}
                    onClick={() => setView('compare')}
                  >
                    Compare selected ({compare.length}/3)
                  </button>
                </div>
                {loading ? (
                  <WorkspaceLoading />
                ) : !hasLoadedSites && readErrors.sites ? (
                  <WorkspaceState
                    kind="error"
                    title="Saved sites could not be loaded"
                    description="Retry the request above to load your workspace."
                  />
                ) : !filtered.length ? (
                  <WorkspaceState
                    kind="empty"
                    title={
                      sites.length
                        ? 'No sites match these filters'
                        : 'No infrastructure sites saved'
                    }
                    description="Draw a boundary or upload GeoJSON to create a site for evidence screening."
                    action={
                      <button onClick={startNew}>
                        Create a site <ArrowUpRight size={16} />
                      </button>
                    }
                  />
                ) : (
                  <div className="site-table portfolio-site-table">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="check-cell" />
                          <TableHead>Site intelligence</TableHead>
                          <TableHead>Area</TableHead>
                          <TableHead>Evidence coverage</TableHead>
                          <TableHead>Screening state</TableHead>
                          <TableHead>Team review</TableHead>
                          <TableHead>
                            <span className="sr-only">Open site</span>
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filtered.map((s, index) => {
                          const hasCurrentAssessment =
                            !!s.assessment?.result &&
                            s.assessment.version === s.version;
                          const completeness = hasCurrentAssessment
                            ? s.assessment.result.completeness
                            : null;
                          const datasetCount = hasCurrentAssessment
                            ? s.assessment.result.dataset_count
                            : null;
                          const coveragePercent =
                            completeness !== null && datasetCount
                              ? Math.min(
                                  100,
                                  Math.round(
                                    (completeness / datasetCount) * 100,
                                  ),
                                )
                              : 0;
                          const screeningState =
                            s.assessment?.version !== s.version
                              ? 'partial'
                              : s.assessment?.state === 'completed'
                                ? 'available'
                                : s.assessment?.state === 'partial'
                                  ? 'partial'
                                  : s.assessment?.state === 'failed'
                                    ? 'warning'
                                    : s.assessment
                                      ? 'modelled'
                                      : 'missing';
                          return (
                            <TableRow
                              key={s.id}
                              data-selected={compare.includes(s.id)}
                            >
                              <TableCell>
                                <Checkbox
                                  aria-label={'Compare ' + s.name}
                                  checked={compare.includes(s.id)}
                                  disabled={
                                    !compare.includes(s.id) &&
                                    compare.length >= 3
                                  }
                                  onCheckedChange={(v) =>
                                    setCompare(
                                      v
                                        ? [...compare, s.id]
                                        : compare.filter((id) => id !== s.id),
                                    )
                                  }
                                />
                              </TableCell>
                              <TableCell>
                                <button
                                  className="site-link"
                                  title={s.name}
                                  onClick={() => openSite(s)}
                                >
                                  <span
                                    className="site-locator"
                                    aria-hidden="true"
                                  >
                                    <span className="site-sequence">
                                      {String(index + 1).padStart(2, '0')}
                                    </span>
                                    <MapPin size={16} />
                                  </span>
                                  <span>
                                    <strong>{s.name}</strong>
                                    <small>
                                      SITE {s.id.slice(-8).toUpperCase()} · BND
                                      V{s.version} · ENGLAND
                                    </small>
                                  </span>
                                </button>
                              </TableCell>
                              <TableCell className="portfolio-area">
                                {hasCurrentAssessment
                                  ? fmt(s.assessment.result.area_ha) + ' ha'
                                  : '—'}
                              </TableCell>
                              <TableCell>
                                <div
                                  className={`coverage-readout${hasCurrentAssessment ? '' : ' is-unknown'}`}
                                  aria-label={
                                    hasCurrentAssessment
                                      ? `${completeness} of ${datasetCount} reference layers available`
                                      : 'Reference-layer coverage unknown'
                                  }
                                >
                                  <span className="coverage-value">
                                    {hasCurrentAssessment
                                      ? `${completeness} / ${datasetCount}`
                                      : 'UNKNOWN'}
                                  </span>
                                  <span
                                    className="coverage-track"
                                    aria-hidden="true"
                                  >
                                    <span
                                      style={{ width: `${coveragePercent}%` }}
                                    />
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <EvidenceBadge state={screeningState}>
                                  {s.assessment
                                    ? s.assessment.version !== s.version
                                      ? 'Previous boundary'
                                      : s.assessment.state
                                    : 'Not screened'}
                                </EvidenceBadge>
                              </TableCell>
                              <TableCell>
                                <Status
                                  value={s.status}
                                  onChange={(status) =>
                                    act(() =>
                                      api('/sites/' + s.id, 'PATCH', {
                                        status,
                                        expected_version: s.version,
                                      }),
                                    )
                                  }
                                />
                              </TableCell>
                              <TableCell>
                                <button
                                  aria-label={'Open ' + s.name}
                                  className="icon-btn"
                                  onClick={() => openSite(s)}
                                >
                                  <ArrowUpRight size={18} />
                                </button>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                )}
                <p className="fineprint portfolio-fineprint">
                  <span>OPERATING NOTE</span>
                  Screening states describe geographic observations and
                  provisional wetland model outputs. Review decisions remain
                  team-owned.
                </p>
              </div>
            </TabsContent>
          </Tabs>
        )}
        {view === 'site' && current && (
          <EntityDossier
            className="site-workspace"
            open={panelOpen}
            ariaLabel="Site intelligence dossier"
            entityKind="SITE"
            title={current.name}
            location={`England · Saved boundary v${stale ? assessment.version : current.version}${result ? ` · ${fmt(result.area_ha)} ha` : ''}`}
            artifact={assessment ? 'Saved assessment' : 'No saved assessment'}
            evidenceAsOf={
              assessment
                ? `Evidence retained ${new Date(assessment.created).toLocaleDateString('en-GB')}`
                : undefined
            }
            status={
              <EvidenceBadge
                state={
                  assessment?.state === 'completed'
                    ? 'available'
                    : assessment?.state === 'failed'
                      ? 'warning'
                      : assessment
                        ? 'partial'
                        : 'missing'
                }
              >
                {assessment ? assessment.state : 'Not assessed'}
              </EvidenceBadge>
            }
            actions={
              <>
                <button className="back" onClick={() => setView('workspace')}>
                  <ArrowLeft size={14} /> All sites
                </button>
                <span className="compact-team-review">
                  <small>Team review</small>
                  <Status
                    value={current.status}
                    onChange={(status) =>
                      act(() =>
                        api('/sites/' + active, 'PATCH', {
                          status,
                          expected_version: current.version,
                        }),
                      )
                    }
                  />
                </span>
                <button
                  className="assessment-action"
                  disabled={
                    busy ||
                    ['queued', 'running'].includes(current.assessment?.state)
                  }
                  onClick={() => void createAssessment()}
                >
                  <Play size={15} />
                  {['queued', 'running'].includes(current.assessment?.state)
                    ? current.assessment.state + '…'
                    : 'New assessment'}
                </button>
                <details className="site-actions-menu">
                  <summary>
                    <MoreHorizontal size={16} />
                    <span className="sr-only">Site actions</span>
                  </summary>
                  <div>
                    <button
                      className="text-btn"
                      onClick={() => {
                        setEditing(true);
                        setName(current.name);
                        setNotes(current.notes);
                        setGeometry(null);
                        setRawGeometry(null);
                        setNewSite(true);
                      }}
                    >
                      <PenLine size={14} /> Edit boundary / site
                    </button>
                  </div>
                </details>
              </>
            }
            historyState={
              assessment &&
              selectedAssessment &&
              selectedAssessment !== current.assessment?.id
                ? {
                    label: `Boundary v${assessment.version} · ${new Date(assessment.created).toLocaleString('en-GB')}`,
                    onReturnLatest: () => selectSiteAssessment(null),
                  }
                : undefined
            }
            closeButtonRef={analysisCloseButton}
            onCollapse={collapseSitePanel}
            layersOpen={mapLayersOpen}
            onOpenLayers={() => setMapLayersOpen((open) => !open)}
          >
            {stale && (
              <div className="alert">
                Viewing saved boundary v{assessment.version}; current site is v
                {current.version}. Create a new assessment to evaluate the
                current boundary.
              </div>
            )}
            {newerData && (
              <details className="data-update-note">
                <summary>Newer reference data available</summary>
                <p>
                  Saved findings retain their original sources. Create a new
                  assessment to use the latest imports.
                </p>
              </details>
            )}
            <div
              className={`investigation${panelOpen ? '' : ' panel-collapsed'}`}
            >
              <div
                className="findings-panel"
                ref={analysisPanel}
                hidden={!panelOpen}
              >
                {refreshNotice}
                {mapEvidence.selectedObjectId && (
                  <div className="asset-intelligence-view">
                    {mapEvidence.selectedObject && mapEvidence.scene ? (
                      <MapFeatureInspector
                        feature={mapEvidence.selectedObject}
                        layer={mapEvidence.scene.layers.find(
                          (layer) =>
                            layer.id ===
                            mapEvidence.selectedObject?.properties.layer_id,
                        )}
                        sources={mapEvidence.scene.sources}
                        limitations={mapEvidence.scene.limitations}
                        siteName={current.name}
                        relatedVisible={operatingState.showRelated}
                        onToggleRelated={() =>
                          operatingPicture.transition((currentState) => ({
                            ...currentState,
                            showRelated: !currentState.showRelated,
                          }))
                        }
                        onLocate={() =>
                          mapEvidence.locateObject(
                            mapEvidence.selectedObject!.id,
                          )
                        }
                        onReturnToSite={returnToSiteDiligence}
                      />
                    ) : (
                      <WorkspaceLoading />
                    )}
                  </div>
                )}
                <div
                  className="analysis-panel-heading"
                  hidden={!!mapEvidence.selectedObjectId}
                >
                  <span>
                    <strong>Site evidence and reasoning</strong>
                    <small>
                      Earth evidence · reasoning modules · team review
                    </small>
                  </span>
                </div>
                <Tabs
                  hidden={!!mapEvidence.selectedObjectId}
                  value={tab}
                  onValueChange={(value) =>
                    changeSiteSection(value as WorkspaceTab)
                  }
                >
                  <TabsList
                    className="panel-tabs analysis-tabs"
                    aria-label="Site analysis sections"
                  >
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="evidence">Evidence</TabsTrigger>
                    <TabsTrigger value="models">Models</TabsTrigger>
                    <TabsTrigger value="history">History</TabsTrigger>
                  </TabsList>
                  <TabsContent value="overview">
                    {assessment ? (
                      <ScreeningContextPanel
                        key={assessment.id + ':overview'}
                        assessment={assessment}
                        hasResult={!!result}
                        mode="overview"
                        context={workspace.context}
                        mapEvidence={mapEvidence}
                        onEvidence={() => changeSiteSection('evidence')}
                        onMap={(key) => {
                          changeSitePanel(true);
                          showOnMap(key);
                        }}
                        mapTargets={[
                          ...(result?.findings || [])
                            .filter((item: OverlayFinding) => !!item.geometry)
                            .map((item: OverlayFinding) => item.key),
                          ...(mapEvidence.features?.layers || [])
                            .filter(
                              (layer) =>
                                layer.feature_count > 0 &&
                                ['available', 'partial'].includes(layer.state),
                            )
                            .map((layer) => `context:${layer.id}`),
                        ]}
                        site={{
                          name: current.name,
                          areaHa: result?.area_ha,
                        }}
                      />
                    ) : (
                      <section className="screening-context screening-overview useful-empty">
                        <div className="screening-heading">
                          <span>
                            <FileText size={18} />
                            <span>
                              <p className="eyebrow">TERRENE EARTH</p>
                              <h2>Site brief</h2>
                            </span>
                          </span>
                          <output>No saved assessment</output>
                        </div>
                        <section className="site-picture is-basic">
                          <p className="context-kind">Site picture</p>
                          <h3>{current.name}</h3>
                          <dl className="site-picture-basics">
                            <div>
                              <dt>Location</dt>
                              <dd>England</dd>
                            </div>
                            <div>
                              <dt>Boundary</dt>
                              <dd>Version {current.version}</dd>
                            </div>
                            <div>
                              <dt>Assessment</dt>
                              <dd>Not yet created</dd>
                            </div>
                          </dl>
                        </section>
                        <section className="context-preparation-note">
                          <h3>Establish saved evidence</h3>
                          <p>
                            Create an assessment to retain the current boundary
                            and available source evidence. Screening Context can
                            then prepare the concise brief without changing the
                            original assessment.
                          </p>
                          <button
                            onClick={() => void createAssessment()}
                            disabled={busy}
                          >
                            <Play size={14} /> Create assessment
                          </button>
                        </section>
                      </section>
                    )}
                    <div className="team-review">
                      <p>
                        <strong>Team decision</strong> · kept separate from
                        Earth facts and model interpretations.
                      </p>
                      <details>
                        <summary>Site notes</summary>
                        <p>
                          {current.notes ||
                            'No notes added. Use Edit boundary / site to add notes.'}
                        </p>
                      </details>
                    </div>
                  </TabsContent>
                  <TabsContent value="evidence">
                    {assessment && (
                      <ScreeningContextPanel
                        key={assessment.id + ':evidence'}
                        assessment={assessment}
                        hasResult={!!result}
                        mode="evidence"
                        context={workspace.context}
                        mapEvidence={mapEvidence}
                        onEvidence={() => changeSiteSection('evidence')}
                        site={{
                          name: current.name,
                          areaHa: result?.area_ha,
                        }}
                      />
                    )}
                    <details className="module-evidence">
                      <summary>Wetland module input evidence</summary>
                      <NaturePanel
                        key={(assessment?.id || current.id) + ':evidence'}
                        section="evidence"
                        onSection={() => changeSiteSection('models')}
                        model={result?.wetland_model}
                        earth={result?.environmental_state}
                        assessmentState={assessment?.state}
                        hasResult={!!result}
                        error={assessment?.error}
                        findings={result?.findings}
                        onMapEvidence={showOnMap}
                        onInspect={() =>
                          analysisPanel.current?.scrollTo({ top: 0 })
                        }
                      />
                      <OverlayFindings
                        findings={result?.findings || []}
                        onInspect={(f) => {
                          if (f.geometry) showOnMap(f.key);
                          setFinding(f);
                        }}
                        onMap={showOnMap}
                      />
                    </details>
                  </TabsContent>
                  <TabsContent value="models">
                    <div className="model-module-heading">
                      <span>
                        <p className="eyebrow">TERRENE REASONING · MODULE</p>
                        <h2>Wetland assessment</h2>
                        <p>
                          Versioned reasoning over the selected assessment’s
                          retained evidence. Model interpretations are not Earth
                          facts or team decisions.
                        </p>
                      </span>
                      <button disabled={!result || busy} onClick={report}>
                        <Download size={15} /> Export report
                      </button>
                    </div>
                    <Tabs
                      className="model-module"
                      value={wetlandSection}
                      onValueChange={(value) =>
                        setWetlandSection(value as typeof wetlandSection)
                      }
                    >
                      <TabsList
                        className="model-tabs"
                        variant="line"
                        aria-label="Wetland assessment sections"
                      >
                        <TabsTrigger value="overview">Summary</TabsTrigger>
                        <TabsTrigger value="physical">Physical</TabsTrigger>
                        <TabsTrigger value="ecology">Ecology</TabsTrigger>
                        <TabsTrigger value="constraints">
                          Constraints
                        </TabsTrigger>
                      </TabsList>
                      {['overview', 'physical', 'ecology', 'constraints'].map(
                        (section) => (
                          <TabsContent value={section} key={section}>
                            <NaturePanel
                              key={(assessment?.id || current.id) + section}
                              section={section}
                              onSection={(next) => {
                                if (next === 'evidence')
                                  changeSiteSection('evidence');
                                else
                                  setWetlandSection(
                                    next as typeof wetlandSection,
                                  );
                              }}
                              model={result?.wetland_model}
                              earth={result?.environmental_state}
                              assessmentState={assessment?.state}
                              hasResult={!!result}
                              error={assessment?.error}
                              findings={result?.findings}
                              onMapEvidence={showOnMap}
                              onInspect={() =>
                                analysisPanel.current?.scrollTo({ top: 0 })
                              }
                            />
                            {section !== 'overview' && (
                              <details className="model-reference-layers">
                                <summary>
                                  Mapped reference layers ·{' '}
                                  {
                                    (result?.findings || []).filter(
                                      (f: OverlayFinding) =>
                                        section === 'physical'
                                          ? f.key === 'flood'
                                          : f.key !== 'flood',
                                    ).length
                                  }
                                </summary>
                                <OverlayFindings
                                  findings={(result?.findings || []).filter(
                                    (f: OverlayFinding) =>
                                      section === 'physical'
                                        ? f.key === 'flood'
                                        : f.key !== 'flood',
                                  )}
                                  onInspect={(f) => {
                                    if (f.geometry) showOnMap(f.key);
                                    setFinding(f);
                                  }}
                                  onMap={showOnMap}
                                />
                              </details>
                            )}
                          </TabsContent>
                        ),
                      )}
                    </Tabs>
                  </TabsContent>
                  <TabsContent value="history">
                    <div className="panel-heading">
                      <h2>Assessment history</h2>
                      <p>
                        Each run retains its exact boundary, observations and
                        source versions. Selecting a run updates both map and
                        analysis.
                      </p>
                    </div>
                    {history.length ? (
                      history.map((a) => (
                        <button
                          className={`history-row${a.id === assessment?.id ? ' is-selected' : ''}`}
                          aria-pressed={a.id === assessment?.id}
                          key={a.id}
                          onClick={() => selectSiteAssessment(a.id)}
                        >
                          <b>
                            Boundary v{a.version} · {a.state}
                          </b>
                          <small>
                            {new Date(a.created).toLocaleString('en-GB')}
                            {a.id === assessment?.id ? ' · Viewing' : ''}
                          </small>
                        </button>
                      ))
                    ) : (
                      <p className="pad">
                        {historyFailure
                          ? 'Assessment history could not be loaded. Retry live refresh above.'
                          : historyRead.siteId !== active || !historyRead.loaded
                            ? 'Loading assessment history…'
                            : 'No assessments yet.'}
                      </p>
                    )}
                  </TabsContent>
                </Tabs>
              </div>
            </div>
          </EntityDossier>
        )}
        {view === 'data' && (
          <>
            <div className="heading">
              <div>
                <p className="eyebrow">REFERENCE LIBRARY</p>
                <h1>Data sources</h1>
                <p>
                  Imported once per version. Evidence retained with every
                  assessment.
                </p>
              </div>
            </div>
            <div className="workspace-content">
              <div className="alert">
                The Oxfordshire pilot has source-specific coverage. Flood data
                covers the smaller Oxford corridor. Outside a source’s imported
                extent, its result stays unknown.
              </div>
              {datasets.map((d) => (
                <article className="dataset" key={d.id}>
                  <div>
                    <EvidenceBadge
                      state={d.state === 'available' ? 'available' : 'partial'}
                    >
                      {d.state}
                    </EvidenceBadge>
                    <h2>{d.metadata.name}</h2>
                    <p>{d.metadata.limitations}</p>
                    <p>
                      Imported extent (west, south, east, north):{' '}
                      {d.metadata.bbox?.join(', ')}°
                    </p>
                    {d.metadata.zone_counts && (
                      <p>
                        Source features: {d.metadata.zone_counts.FZ2} in Zone 2
                        · {d.metadata.zone_counts.FZ3} in Zone 3. Screening
                        measures their combined union.
                      </p>
                    )}
                    {d.metadata.error && (
                      <p className="warning-text">{d.metadata.error}</p>
                    )}
                    <a href={d.metadata.url} target="_blank" rel="noreferrer">
                      Authoritative source ↗
                    </a>
                  </div>
                  <div className="dataset-meta">
                    <b>{d.metadata.count ?? '—'} features</b>
                    <small>
                      Retrieved{' '}
                      {new Date(d.retrieved).toLocaleDateString('en-GB')}
                    </small>
                    <small>
                      {d.metadata.synthetic
                        ? 'SYNTHETIC FIXTURE'
                        : 'Real source data'}
                    </small>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
        {view === 'compare' && (
          <>
            <div className="heading">
              <div>
                <p className="eyebrow">SIDE-BY-SIDE REVIEW</p>
                <h1>Compare sites</h1>
                <p>Explicit findings, coverage and your team’s decisions.</p>
              </div>
              <button
                onClick={() => {
                  setSitesView('list');
                }}
              >
                Choose sites
              </button>
            </div>
            <div className="workspace-content">
              {compare.length < 2 ? (
                <WorkspaceState
                  kind="empty"
                  title="Select two or three sites"
                  description="Use the checkboxes in Sites to choose the infrastructure sites you want to compare."
                  action={
                    <button
                      onClick={() => {
                        setSitesView('list');
                      }}
                    >
                      Back to sites
                    </button>
                  }
                />
              ) : (
                <div className="comparison">
                  {sites
                    .filter((s) => compare.includes(s.id))
                    .map((s) => {
                      const r =
                        s.assessment?.version === s.version
                          ? s.assessment?.result
                          : null;
                      return (
                        <article key={s.id}>
                          <h2>{s.name}</h2>
                          <Status
                            value={s.status}
                            onChange={(status) =>
                              act(() =>
                                api('/sites/' + s.id, 'PATCH', {
                                  status,
                                  expected_version: s.version,
                                }),
                              )
                            }
                          />
                          <dl>
                            <dt>Area</dt>
                            <dd>{r ? fmt(r.area_ha) + ' ha' : 'Unknown'}</dd>
                            <dt>Reference coverage</dt>
                            <dd>
                              {r
                                ? r.completeness + ' / ' + r.dataset_count
                                : 'Not screened for current boundary'}
                            </dd>
                            {r?.findings.map((f: any) => (
                              <div key={f.key}>
                                <dt>{f.dataset}</dt>
                                <dd>
                                  {f.measured === null
                                    ? 'Unknown'
                                    : fmt(f.measured) + ' ha overlap'}
                                </dd>
                              </div>
                            ))}
                          </dl>
                          <button onClick={() => openSite(s)}>
                            Investigate <ArrowUpRight size={15} />
                          </button>
                        </article>
                      );
                    })}
                </div>
              )}
            </div>
          </>
        )}
        {newSite && (
          <SiteEditorPanel
            editing={editing}
            name={name}
            notes={notes}
            stagedGeometry={geometry}
            existingBoundaryLabel={
              editing && current
                ? `Saved boundary v${current.version}`
                : undefined
            }
            drawing={drawing}
            drawPointCount={drawPointCount}
            busy={busy}
            error={error}
            nameInputRef={siteNameInput}
            onNameChange={setName}
            onNotesChange={setNotes}
            onStartDrawing={() => {
              setDrawSession((session) => session + 1);
              setDrawPointCount(0);
              setDrawing(true);
            }}
            onUndoDrawing={() => boundaryDrawingControls.current?.undo()}
            onFinishDrawing={() => boundaryDrawingControls.current?.finish()}
            onUpload={(file) => void upload(file)}
            onCancel={closeSiteEditor}
            onSave={() => void save()}
          />
        )}
      </section>
      <Dialog
        open={!!workspace.reportHtml}
        onOpenChange={(v) => {
          if (!v) workspace.closeWetlandReport();
        }}
      >
        <DialogContent className="report-dialog">
          <DialogHeader>
            <DialogTitle>Wetland model report</DialogTitle>
            <DialogDescription>
              Saved wetland reasoning and supporting assessment evidence, with
              the team review status labelled separately.
            </DialogDescription>
          </DialogHeader>
          <div className="actions">
            <a
              className="download-link"
              href={workspace.reportUrl}
              download="terrene-wetland-model-report.html"
            >
              Download wetland model HTML
            </a>
            <button
              onClick={() => {
                const frame = document.getElementById(
                  'report-frame',
                ) as HTMLIFrameElement;
                frame.contentWindow?.print();
              }}
            >
              Print / Save as PDF
            </button>
          </div>
          <iframe
            id="report-frame"
            title="Printable screening report"
            srcDoc={workspace.reportHtml}
          />
        </DialogContent>
      </Dialog>
      <Sheet open={!!finding} onOpenChange={(v) => !v && setFinding(null)}>
        <SheetContent className="evidence-sheet">
          <SheetHeader>
            <SheetTitle>{overlayFinding?.dataset}</SheetTitle>
            <SheetDescription>
              Evidence detail · boundary v{overlayFinding?.boundary_version}
            </SheetDescription>
          </SheetHeader>
          {overlayFinding && (
            <div className="evidence-body">
              <p className="eyebrow">MEASURED OBSERVATION</p>
              <h2>
                {overlayFinding.measured === null
                  ? 'Unknown'
                  : fmt(overlayFinding.measured) + ' ha overlap'}
              </h2>
              <p>{overlayFinding.interpretation}</p>
              <dl>
                <dt>Coverage</dt>
                <dd>{overlayFinding.coverage}</dd>
                {overlayFinding.import_bbox && (
                  <>
                    <dt>Imported extent (W, S, E, N)</dt>
                    <dd>{overlayFinding.import_bbox.join(', ')}°</dd>
                  </>
                )}
                {overlayFinding.import_method && (
                  <>
                    <dt>Import method</dt>
                    <dd>{overlayFinding.import_method}</dd>
                  </>
                )}
                <dt>Method</dt>
                <dd>{overlayFinding.method}</dd>
                <dt>Rule version</dt>
                <dd>{overlayFinding.rule_version}</dd>
                <dt>Retrieved</dt>
                <dd>{overlayFinding.retrieved}</dd>
                <dt>Dataset version</dt>
                <dd>{overlayFinding.dataset_version}</dd>
              </dl>
              <a
                href={overlayFinding.source_url}
                target="_blank"
                rel="noreferrer"
              >
                View authoritative source ↗
              </a>
              {result?.environmental_state && (
                <>
                  <h3>Derived observations using this source</h3>
                  <ul className="source-dependencies">
                    {(
                      Object.values(
                        result.environmental_state.derived,
                      ) as Observation[]
                    )
                      .filter(
                        (o) => linkedFindings(o, [overlayFinding]).length > 0,
                      )
                      .map((o) => (
                        <li key={o.id}>
                          {variableLabel(o.variable)}
                          <small>{observationValue(o)}</small>
                        </li>
                      ))}
                  </ul>
                  <button
                    onClick={() => {
                      changeSiteSection('evidence');
                      changeSitePanel(true);
                      setFinding(null);
                    }}
                  >
                    Open evidence register <ArrowUpRight size={14} />
                  </button>
                </>
              )}
              <h3>Limitations & uncertainty</h3>
              <p>{overlayFinding.limitations}</p>
              <p>{result?.limitations}</p>
              <small>{overlayFinding.attribution}</small>
              {overlayFinding.geometry && (
                <button
                  onClick={() => {
                    showOnMap(overlayFinding.key);
                    setFinding(null);
                  }}
                >
                  <MapPin size={14} /> Inspect footprint on map
                </button>
              )}
              <p className="fineprint">
                {overlayFinding.geometry
                  ? 'The overlap geometry is highlighted on the map.'
                  : 'No overlap geometry is available for this finding.'}
              </p>
            </div>
          )}
        </SheetContent>
      </Sheet>
      {(criticalError.includes('Sign in') ||
        criticalError.includes('session') ||
        criticalError.includes('Sign-in')) && (
        <div className="auth-box">
          <h2>Sign in to your organization</h2>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              act(async () => {
                const data = await api('/auth/sign-in', 'POST', {
                  email,
                  password,
                });
                sessionStorage.setItem('crc-token', data.access_token);
                setPassword('');
              })
            }
          >
            Sign in
          </button>
        </div>
      )}
    </main>
  );
}
