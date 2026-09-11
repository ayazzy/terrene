'use client';
import { useEffect, useState, useCallback, useRef } from 'react';
import dynamic from 'next/dynamic';
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
import { useSiteWorkspaceState } from './site-workspace-state';
import type { OverlayFinding } from './site-evidence';
import SiteMap from './map';
import {
  EvidenceBadge,
  WorkspaceLoading,
  WorkspaceState,
} from './status-primitives';
import {
  Plus,
  Orbit,
  ArrowUpRight,
  ArrowLeft,
  MapPin,
  Download,
  Play,
  Upload,
  PenLine,
  Search,
  PanelLeft,
  GitCompareArrows,
  Check,
  Info,
  RefreshCw,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  Database,
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
const PortfolioMap = dynamic(() => import('./portfolio-map'), {
  ssr: false,
  loading: () => (
    <div className="portfolio-map portfolio-loading">
      Loading saved-site map…
    </div>
  ),
});
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
  const [sites, setSites] = useState<any[]>([]),
    [datasets, setDatasets] = useState<any[]>([]),
    [active, setActive] = useState<string | null>(null),
    [view, setView] = useState('workspace'),
    [sitesView, setSitesView] = useState('map'),
    [selectedMapSite, setSelectedMapSite] = useState<string | null>(null),
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
    [editing, setEditing] = useState(false),
    [query, setQuery] = useState(''),
    [filter, setFilter] = useState('all'),
    [compare, setCompare] = useState<string[]>([]),
    [history, setHistory] = useState<any[]>([]),
    [mode, setMode] = useState(''),
    [email, setEmail] = useState(''),
    [password, setPassword] = useState(''),
    [rawGeometry, setRawGeometry] = useState<any>(null),
    [navigationCompact, setNavigationCompact] = useState(false),
    [mobileNavigation, setMobileNavigation] = useState(false);
  const current = sites.find((s) => s.id === active);
  const workspace = useSiteWorkspaceState(current, history);
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
  } = workspace;
  const result = assessment?.result,
    viewingHistorical =
      !!assessment && assessment.id !== current?.assessment?.id,
    stale = current && assessment && current.version !== assessment.version,
    newerData =
      result &&
      !readErrors.datasets &&
      datasets.some((d) => !assessment.dataset_ids?.includes(d.id));
  const screeningFinding = finding && 'properties' in finding ? finding : null;
  const overlayFinding = finding && !('properties' in finding) ? finding : null;
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
    { label: 'Live service status', failure: readErrors.health },
    { label: 'Assessment history', failure: historyFailure },
  ].filter((item) => item.failure);
  const showRefreshNotice = refreshFailures.length > 0 && !criticalRead;
  useEffect(() => {
    analysisPanel.current?.scrollTo({ top: 0 });
  }, [tab, assessment?.id]);
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
    if (!healthRead.failure && 'data' in healthRead)
      setMode(healthRead.data.mode);
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
    if (!active) return;
    let cancelled = false;
    void readResource(() => api('/sites/' + active + '/assessments')).then(
      (read) => {
        if (cancelled) return;
        if (!read.failure && 'data' in read) setHistory(read.data);
        setHistoryRead({
          siteId: active,
          failure: read.failure,
          loaded: !read.failure,
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [active, sites, historyRetry]);
  function retryReads() {
    setHistoryRetry((value) => value + 1);
    void reload();
  }
  const refreshNotice = showRefreshNotice && (
    <section className="refresh-notice" aria-label="Live refresh availability">
      <div className="refresh-notice-heading">
        <p role="status">
          <strong>Live refresh unavailable</strong>
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
          Values already loaded are retained. Live changes could not be checked.
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
    setActive(s.id);
    setHistory([]);
    setView('site');
  }
  function startNew() {
    setEditing(false);
    setName('');
    setNotes('');
    setGeometry(null);
    setRawGeometry(null);
    setNewSite(true);
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
      setNewSite(false);
      setDrawing(false);
      setActive(s.id);
      setView('site');
      workspace.resetForSite();
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
  return (
    <main
      className={`crc-shell${navigationCompact ? ' nav-compact' : ''}${mobileNavigation ? ' nav-mobile-open' : ''}`}
    >
      <aside id="primary-navigation" aria-label="Primary navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Orbit />
          </span>
          <span className="brand-wordmark">Terrene</span>
          <button
            className="sidebar-toggle"
            aria-label={
              navigationCompact ? 'Expand sidebar' : 'Collapse sidebar'
            }
            title={navigationCompact ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-controls="primary-navigation"
            aria-expanded={!navigationCompact}
            onClick={() => setNavigationCompact((value) => !value)}
          >
            {navigationCompact ? <PanelLeftOpen /> : <PanelLeftClose />}
          </button>
        </div>
        <p className="brand-descriptor">EARTH INTELLIGENCE</p>
        <nav>
          <span className="nav-section">Workspace</span>
          <button
            className={view === 'workspace' ? 'nav-active' : ''}
            onClick={() => {
              setView('workspace');
              setMobileNavigation(false);
            }}
            title="Sites"
          >
            <PanelLeft size={18} /> <span className="nav-text">Sites</span>{' '}
            <span className="nav-count">{sites.length}</span>
          </button>
          <button
            className={view === 'compare' ? 'nav-active' : ''}
            onClick={() => {
              setView('compare');
              setMobileNavigation(false);
            }}
            title="Compare sites"
          >
            <GitCompareArrows size={18} />
            <span className="nav-text">Compare sites</span>
          </button>
          <span className="nav-section">Evidence</span>
          <button
            className={view === 'data' ? 'nav-active' : ''}
            onClick={() => {
              setView('data');
              setMobileNavigation(false);
            }}
            title="Data sources"
          >
            <Database size={18} />
            <span className="nav-text">Data sources</span>
          </button>
        </nav>
        <div className="sidebar-note">
          <span className="sidebar-note-label">
            <span className="live-dot" /> SYSTEM STATUS
          </span>
          <div className="sidebar-status-row">
            <span>Evidence services</span>
            <strong>{readErrors.health ? 'Unavailable' : 'Operational'}</strong>
          </div>
          <div className="sidebar-status-row">
            <span>Workspace</span>
            <strong>
              {mode
                ? mode === 'development'
                  ? 'Local'
                  : 'Organisation'
                : 'Unknown'}
            </strong>
          </div>
        </div>
        <footer>
          <div className="workspace-avatar">OX</div>
          <div className="workspace-identity">
            <strong>Oxfordshire pilot</strong>
            <span>England · Terrene workspace</span>
          </div>
        </footer>
      </aside>
      <section
        className={`main${view === 'site' ? ' analysis-main' : ''}${view === 'workspace' && sitesView === 'map' ? ' portfolio-main' : ''}`}
      >
        <header>
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobileNavigation((value) => !value)}
          >
            <Menu />
          </button>
          <span className="breadcrumb">
            Terrene <span>/</span>{' '}
            {view === 'site'
              ? current?.name
              : view === 'data'
                ? 'Data sources'
                : view === 'compare'
                  ? 'Compare'
                  : 'Land opportunities'}
          </span>
          <span className="pilot">
            <span className="environment-status">
              <span
                className={`live-dot${refreshFailures.length ? ' is-unavailable' : ''}`}
              />{' '}
              {refreshFailures.length ? 'Refresh unavailable' : 'Live evidence'}
            </span>
            <b>OX</b>
          </span>
        </header>
        {criticalError && (
          <div role="alert" className="alert error">
            {criticalError}
            {criticalRead && (
              <button disabled={refreshing} onClick={retryReads}>
                <RefreshCw size={14} /> Retry
              </button>
            )}
          </div>
        )}
        {view !== 'site' && refreshNotice}
        {view === 'workspace' && (
          <Tabs
            className="sites-views"
            value={sitesView}
            onValueChange={(value) => setSitesView(String(value))}
          >
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
                <Plus size={18} /> New site
              </button>
            </div>
            <TabsContent value="map" className="sites-map-panel">
              <PortfolioMap
                sites={sites}
                selected={selectedMapSite}
                onSelect={setSelectedMapSite}
                onOpen={openSite}
                loading={loading}
                unavailable={!hasLoadedSites && !!readErrors.sites}
              />
            </TabsContent>
            <TabsContent value="list">
              <div className="heading">
                <div>
                  <p className="eyebrow">LAND OPPORTUNITIES</p>
                  <h1>Your workspace</h1>
                  <p>Identify what deserves a closer look.</p>
                </div>
              </div>
              <div className="workspace-content">
                <div className="workspace-summary">
                  <div>
                    <b>{sites.length.toString().padStart(2, '0')}</b>
                    <span>Saved sites</span>
                  </div>
                  <div>
                    <b>
                      {sites
                        .filter((s) => s.status === 'Investigate')
                        .length.toString()
                        .padStart(2, '0')}
                    </b>
                    <span>To investigate</span>
                  </div>
                  <div>
                    <b>
                      {datasets.filter((d) => d.state === 'available').length} /{' '}
                      {datasets.length}
                    </b>
                    <span>Reference layers available</span>
                  </div>
                  <p>
                    <Info size={18} /> Screening guides further assessment.
                    <br />
                    Wetland model v0.1 shows potential, evidence and
                    uncertainty.
                  </p>
                </div>
                <div className="toolbar">
                  <div className="search">
                    <Search size={17} />
                    <input
                      aria-label="Search sites"
                      placeholder="Search sites…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
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
                  <button
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
                        : 'No land sites saved'
                    }
                    description="Draw a boundary or upload GeoJSON to create a site for evidence screening."
                    action={
                      <button onClick={startNew}>
                        Create a site <ArrowUpRight size={16} />
                      </button>
                    }
                  />
                ) : (
                  <div className="site-table">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="check-cell" />
                          <TableHead>Site / boundary</TableHead>
                          <TableHead>Area</TableHead>
                          <TableHead>Screening</TableHead>
                          <TableHead>Data coverage</TableHead>
                          <TableHead>Review decision</TableHead>
                          <TableHead />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filtered.map((s) => (
                          <TableRow key={s.id}>
                            <TableCell>
                              <Checkbox
                                aria-label={'Compare ' + s.name}
                                checked={compare.includes(s.id)}
                                disabled={
                                  !compare.includes(s.id) && compare.length >= 3
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
                                onClick={() => openSite(s)}
                              >
                                <span className="site-icon">
                                  <MapPin size={18} />
                                </span>
                                <span>
                                  <strong>{s.name}</strong>
                                  <small>Boundary v{s.version} · England</small>
                                </span>
                              </button>
                            </TableCell>
                            <TableCell>
                              {s.assessment?.result &&
                              s.assessment.version === s.version
                                ? fmt(s.assessment.result.area_ha) + ' ha'
                                : '—'}
                            </TableCell>
                            <TableCell>
                              <EvidenceBadge
                                state={
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
                                            : 'missing'
                                }
                              >
                                {s.assessment
                                  ? s.assessment.version !== s.version
                                    ? 'Previous boundary'
                                    : s.assessment.state
                                  : 'Not screened'}
                              </EvidenceBadge>
                            </TableCell>
                            <TableCell>
                              {s.assessment?.result &&
                              s.assessment.version === s.version
                                ? s.assessment.result.completeness +
                                  ' / ' +
                                  s.assessment.result.dataset_count +
                                  ' layers'
                                : 'Unknown'}
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
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
                <p className="fineprint">
                  Review decisions belong to your team. Screening results
                  describe geographic observations and provisional wetland model
                  outputs.
                </p>
              </div>
            </TabsContent>
          </Tabs>
        )}
        {view === 'site' && current && (
          <section
            className="site-workspace"
            aria-label="Site analysis workspace"
          >
            <div className="heading site-heading">
              <div className="site-context">
                <button className="back" onClick={() => setView('workspace')}>
                  <ArrowLeft size={14} /> All sites
                </button>
                <h1>{current.name}</h1>
                <div className="site-meta-line">
                  <span>
                    <MapPin size={13} /> England
                  </span>
                  <span>
                    Boundary v{stale ? assessment.version : current.version}
                  </span>
                  {result && <span>{fmt(result.area_ha)} ha</span>}
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
                    {assessment
                      ? `Assessment ${assessment.state}`
                      : 'Not assessed'}
                  </EvidenceBadge>
                  {assessment && (
                    <span className="context-date">
                      {new Date(assessment.created).toLocaleString('en-GB', {
                        dateStyle: 'medium',
                      })}
                    </span>
                  )}
                </div>
              </div>
              <div className="site-heading-controls">
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
              </div>
            </div>
            {stale && (
              <div className="alert">
                Viewing saved boundary v{assessment.version}; current site is v
                {current.version}. Create a new assessment to evaluate the
                current boundary.
              </div>
            )}
            {assessment &&
              selectedAssessment &&
              selectedAssessment !== current.assessment?.id && (
                <div className="assessment-snapshot">
                  Historical assessment ·{' '}
                  {new Date(assessment.created).toLocaleString('en-GB')}
                  <button
                    className="text-btn"
                    onClick={workspace.returnToLatest}
                  >
                    Return to latest
                  </button>
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
              <div className="analysis-map">
                <SiteMap
                  key={assessment?.id || current.id}
                  geometry={
                    viewingHistorical ? assessment.geometry : current.geometry
                  }
                  findings={result?.findings}
                  screeningMap={workspace.context.map}
                  selected={mapFocus?.key}
                  focusRequest={mapFocus?.request}
                  boundaryLabel={`Boundary v${viewingHistorical ? assessment.version : current.version}${viewingHistorical ? ' · historical assessment' : ''}`}
                  onInspect={(f) => {
                    showOnMap(
                      'properties' in f
                        ? `context:${f.properties.layer_id}`
                        : f.key,
                    );
                    setFinding(f);
                  }}
                />
                {!panelOpen && (
                  <button
                    className="reopen-analysis"
                    onClick={() => setPanelOpen(true)}
                  >
                    <PanelLeftOpen size={16} /> Open analysis
                  </button>
                )}
              </div>
              <div
                className="findings-panel"
                ref={analysisPanel}
                hidden={!panelOpen}
              >
                <div className="analysis-panel-heading">
                  <span>
                    <strong>Site Analysis Workspace</strong>
                    <small>
                      Earth evidence · reasoning modules · team review
                    </small>
                  </span>
                  <button
                    className="icon-btn"
                    aria-label="Collapse analysis panel"
                    onClick={() => setPanelOpen(false)}
                  >
                    <PanelLeftClose size={17} />
                  </button>
                </div>
                {refreshNotice}
                <Tabs value={tab} onValueChange={setTab}>
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
                        onEvidence={() => setTab('evidence')}
                        onMap={(key) => {
                          setPanelOpen(true);
                          showOnMap(key);
                        }}
                        mapTargets={[
                          ...(result?.findings || [])
                            .filter((item: OverlayFinding) => !!item.geometry)
                            .map((item: OverlayFinding) => item.key),
                          ...(workspace.context.map?.layers || [])
                            .filter((layer) => layer.feature_count > 0)
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
                        onEvidence={() => setTab('evidence')}
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
                        onSection={() => setTab('models')}
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
                                if (next === 'evidence') setTab('evidence');
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
                          onClick={() => workspace.selectAssessment(a.id)}
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
          </section>
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
                  setView('workspace');
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
                  description="Use the checkboxes in Sites to choose the land opportunities you want to compare."
                  action={
                    <button
                      onClick={() => {
                        setSitesView('list');
                        setView('workspace');
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
      </section>
      <Dialog
        open={newSite}
        onOpenChange={(v) => {
          setNewSite(v);
          if (!v) setDrawing(false);
        }}
      >
        <DialogContent className="site-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit site' : 'Create a site'}</DialogTitle>
            <DialogDescription>
              {editing
                ? 'Boundary changes preserve prior assessments as history.'
                : 'Start with a name and an exact land boundary.'}
            </DialogDescription>
          </DialogHeader>
          <label>
            Site name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lower Windrush meadow"
              maxLength={160}
            />
          </label>
          <label>
            Notes <span className="optional">optional</span>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ownership, current use, questions to investigate…"
              maxLength={5000}
            />
          </label>
          <div className="boundary-tools">
            <button
              onClick={() => {
                setNewSite(false);
                setDrawing(true);
              }}
            >
              <PenLine size={16} /> Draw boundary
            </button>
            <label className="upload-btn">
              <Upload size={16} /> Upload GeoJSON
              <input
                type="file"
                accept=".json,.geojson,application/geo+json,application/json"
                onChange={(e) => upload(e.target.files?.[0])}
              />
            </label>
          </div>
          {geometry && (
            <div className="boundary-ready">
              <Check size={16} /> {geometry.type} boundary ready for validation
            </div>
          )}
          {error && <div className="alert error">{error}</div>}
          <p className="fineprint">
            WGS84 Polygon or MultiPolygon, up to 500 KB. Boundaries are
            validated on save and never silently repaired.
          </p>
          <button
            className="primary"
            disabled={busy || !name.trim() || (!geometry && !editing)}
            onClick={save}
          >
            {busy ? 'Saving…' : 'Save site'}
          </button>
        </DialogContent>
      </Dialog>
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
      {drawing && (
        <div className="draw-screen">
          <div className="draw-heading">
            <div>
              <h2>Draw site boundary</h2>
              <p>
                Zoom to the land, click each corner, then finish the boundary.
              </p>
            </div>
            <button
              onClick={() => {
                setDrawing(false);
                setNewSite(true);
              }}
            >
              Cancel drawing
            </button>
          </div>
          <SiteMap
            geometry={geometry || (editing ? current?.geometry : null)}
            boundaryLabel={
              geometry
                ? 'Staged boundary'
                : editing
                  ? `Reference boundary v${current?.version}`
                  : 'Draft boundary'
            }
            draw
            onDraw={(g) => {
              setRawGeometry(null);
              setGeometry(g);
              setDrawing(false);
              setNewSite(true);
            }}
          />
        </div>
      )}
      <Sheet open={!!finding} onOpenChange={(v) => !v && setFinding(null)}>
        <SheetContent className="evidence-sheet">
          <SheetHeader>
            <SheetTitle>
              {screeningFinding
                ? screeningFinding.properties.name ||
                  screeningFinding.properties.classification ||
                  screeningFinding.properties.object_type.replaceAll('_', ' ')
                : overlayFinding?.dataset}
            </SheetTitle>
            <SheetDescription>
              {screeningFinding
                ? 'Mapped object · retained Screening Context evidence'
                : `Evidence detail · boundary v${overlayFinding?.boundary_version}`}
            </SheetDescription>
          </SheetHeader>
          {screeningFinding && (
            <div className="evidence-body">
              <p className="eyebrow">MAPPED OBJECT</p>
              <h2>
                {screeningFinding.properties.object_type.replaceAll('_', ' ')}
              </h2>
              <p>
                {screeningFinding.properties.classification ||
                  'No additional source classification recorded.'}
              </p>
              <dl>
                <dt>Source</dt>
                <dd>
                  {screeningFinding.properties.source.provider} ·{' '}
                  {screeningFinding.properties.source.dataset}
                </dd>
                <dt>Release</dt>
                <dd>{screeningFinding.properties.source_release}</dd>
                <dt>Relationship to parcel</dt>
                <dd>
                  {screeningFinding.properties.relationships.length
                    ? screeningFinding.properties.relationships
                        .map((item) => item.predicate.replaceAll('_', ' '))
                        .join(' · ')
                    : 'No parcel relationship retained for this object'}
                </dd>
                <dt>Authoritative geometry</dt>
                <dd>
                  {screeningFinding.properties.authoritative_geometry_crs}
                </dd>
              </dl>
              <button
                onClick={() => {
                  showOnMap(`context:${screeningFinding.properties.layer_id}`);
                  setFinding(null);
                }}
              >
                <MapPin size={14} /> Locate object layer on map
              </button>
              <button
                onClick={() => {
                  setTab('evidence');
                  setPanelOpen(true);
                  setFinding(null);
                }}
              >
                Open evidence register <ArrowUpRight size={14} />
              </button>
              <p className="fineprint">
                Map geometry is a WGS84 presentation. Persisted EPSG:27700
                geometry and measurements remain authoritative.
              </p>
            </div>
          )}
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
                      setTab('evidence');
                      setPanelOpen(true);
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
