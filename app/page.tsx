'use client';
import { useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import NaturePanel from './nature-panel';
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
  Layers,
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
const SiteMap = dynamic(() => import('./map'), {
  ssr: false,
  loading: () => <div className="map-wrap loading">Loading map…</div>,
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
    const e: any = await r.json();
    throw new Error(
      typeof e.detail === 'string' ? e.detail : JSON.stringify(e.detail),
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
  const [sites, setSites] = useState<any[]>([]),
    [datasets, setDatasets] = useState<any[]>([]),
    [active, setActive] = useState<string | null>(null),
    [view, setView] = useState('workspace'),
    [error, setError] = useState(''),
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
    [selectedAssessment, setSelectedAssessment] = useState<string | null>(null),
    [finding, setFinding] = useState<any>(null),
    [tab, setTab] = useState('nature'),
    [mode, setMode] = useState(''),
    [email, setEmail] = useState(''),
    [password, setPassword] = useState(''),
    [rawGeometry, setRawGeometry] = useState<any>(null),
    [reportHtml, setReportHtml] = useState(''),
    [reportUrl, setReportUrl] = useState(''),
    [navigationCompact, setNavigationCompact] = useState(false),
    [mobileNavigation, setMobileNavigation] = useState(false);
  const current = sites.find((s) => s.id === active),
    assessment =
      history.find((a) => a.id === selectedAssessment) || current?.assessment,
    result = assessment?.result,
    stale = current && assessment && current.version !== assessment.version,
    newerData =
      result && datasets.some((d) => !assessment.dataset_ids?.includes(d.id));
  const reload = useCallback(async () => {
    try {
      const [s, d, h] = await Promise.all([
        api('/sites'),
        api('/datasets'),
        api('/health'),
      ]);
      setSites(s);
      setDatasets(d);
      setMode(h.mode);
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    reload();
  }, [reload]);
  useEffect(() => {
    if (!active) return;
    api('/sites/' + active + '/assessments')
      .then(setHistory)
      .catch((e) => setError(e.message));
  }, [active, sites]);
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
            'Read saved CRC sites and review decisions in the current organization.',
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
    setActive(s.id);
    setView('site');
    setSelectedAssessment(null);
    setFinding(null);
    setTab('nature');
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
      setSelectedAssessment(null);
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
    await act(async () => {
      const r = await fetch('/api/assessments/' + assessment.id + '/report', {
        headers: sessionStorage.getItem('crc-token')
          ? { Authorization: 'Bearer ' + sessionStorage.getItem('crc-token') }
          : {},
      });
      if (!r.ok) throw new Error('Report is unavailable');
      const html = await r.text();
      if (reportUrl) URL.revokeObjectURL(reportUrl);
      setReportHtml(html);
      setReportUrl(
        URL.createObjectURL(new Blob([html], { type: 'text/html' })),
      );
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
      <aside aria-label="Primary navigation">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Orbit />
          </span>
          <span className="brand-wordmark">CRC</span>
          <button
            className="sidebar-toggle"
            aria-label={
              navigationCompact ? 'Expand navigation' : 'Collapse navigation'
            }
            title={
              navigationCompact ? 'Expand navigation' : 'Collapse navigation'
            }
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
            <strong>Operational</strong>
          </div>
          <div className="sidebar-status-row">
            <span>Workspace</span>
            <strong>{mode === 'development' ? 'Local' : 'Organisation'}</strong>
          </div>
        </div>
        <footer>
          <div className="workspace-avatar">OX</div>
          <div className="workspace-identity">
            <strong>Oxfordshire pilot</strong>
            <span>England · CRC workspace</span>
          </div>
        </footer>
      </aside>
      <section className="main">
        <header>
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            onClick={() => setMobileNavigation((value) => !value)}
          >
            <Menu />
          </button>
          <span className="breadcrumb">
            CRC <span>/</span>{' '}
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
              <span className="live-dot" /> Live evidence
            </span>
            <b>OX</b>
          </span>
        </header>
        {error && (
          <div role="alert" className="alert error">
            {error}
            <button onClick={reload}>
              <RefreshCw size={14} /> Retry
            </button>
          </div>
        )}
        {view === 'workspace' && (
          <>
            <div className="heading">
              <div>
                <p className="eyebrow">LAND OPPORTUNITIES</p>
                <h1>Your workspace</h1>
                <p>Identify what deserves a closer look.</p>
              </div>
              <button className="primary" onClick={startNew}>
                <Plus size={18} /> New site
              </button>
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
                  Wetland model v0.1 shows potential, evidence and uncertainty.
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
                <Select value={filter} onValueChange={(v) => v && setFilter(v)}>
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
                Review decisions belong to your team. Screening results describe
                geographic observations and provisional wetland model outputs.
              </p>
            </div>
          </>
        )}
        {view === 'site' && current && (
          <>
            <div className="heading site-heading">
              <div>
                <button className="back" onClick={() => setView('workspace')}>
                  <ArrowLeft size={14} /> All sites
                </button>
                <h1>{current.name}</h1>
                <p>
                  <MapPin size={14} /> England · Boundary v{current.version}{' '}
                  {result && !stale && ' · ' + fmt(result.area_ha) + ' ha'}
                </p>
              </div>
              <div className="actions">
                <button disabled={!result || busy} onClick={report}>
                  <Download size={16} /> Export report
                </button>
                <button
                  className="primary"
                  disabled={
                    busy ||
                    ['queued', 'running'].includes(current.assessment?.state)
                  }
                  onClick={() =>
                    act(async () => {
                      await api('/sites/' + active + '/assessments', 'POST');
                      setSelectedAssessment(null);
                    })
                  }
                >
                  <Play size={15} />
                  {['queued', 'running'].includes(current.assessment?.state)
                    ? current.assessment.state + '…'
                    : 'Run screening'}
                </button>
              </div>
            </div>
            <div className="reviewbar">
              <span>
                Review decision{' '}
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
              <span>
                Boundary v{current.version}
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
                  <PenLine size={14} /> Edit site
                </button>
              </span>
            </div>
            {stale && (
              <div className="alert">
                Historical results · boundary v{assessment.version}. Run a new
                screening for boundary v{current.version}.
              </div>
            )}
            {newerData && (
              <div className="alert">
                Newer reference data is available. These saved findings retain
                their original sources; run screening to use the latest imports.
              </div>
            )}
            <div className="investigation">
              <SiteMap
                geometry={stale ? assessment.geometry : current.geometry}
                findings={result?.findings}
                selected={finding?.key}
              />
              <div className="findings-panel">
                <Tabs value={tab} onValueChange={setTab}>
                  <TabsList className="panel-tabs">
                    <TabsTrigger value="nature">Wetland model</TabsTrigger>
                    <TabsTrigger value="findings">Findings</TabsTrigger>
                    <TabsTrigger value="history">History</TabsTrigger>
                    <TabsTrigger value="notes">Site notes</TabsTrigger>
                  </TabsList>
                  <TabsContent value="nature">
                    <NaturePanel
                      key={assessment?.id || current.id}
                      model={result?.wetland_model}
                      earth={result?.environmental_state}
                      assessmentState={assessment?.state}
                      hasResult={!!result}
                      error={assessment?.error}
                    />
                  </TabsContent>
                  <TabsContent value="findings">
                    <div className="panel-heading">
                      <p className="eyebrow">SCREENING EVIDENCE</p>
                      <h2>
                        {result
                          ? 'What the data tells us'
                          : 'Ready for a closer look'}
                      </h2>
                      <p>
                        {result
                          ? result.completeness +
                            ' of ' +
                            result.dataset_count +
                            ' layers covered · ' +
                            assessment.state
                          : 'Run screening to measure overlaps against imported reference layers.'}
                      </p>
                    </div>
                    {assessment?.error && (
                      <div className="alert error">{assessment.error}</div>
                    )}
                    {!result && (
                      <div className="panel-empty">
                        <Layers size={28} />
                        <p>
                          {assessment?.state === 'failed'
                            ? 'Assessment failed after bounded retries. Review the API logs and rerun imports before submitting again.'
                            : assessment
                              ? `Assessment ${assessment.state}. Results will appear here.`
                              : 'Your boundary is saved. No assessment has been run.'}
                        </p>
                      </div>
                    )}
                    {result && (
                      <>
                        <div className="measurement">
                          <span>Site area</span>
                          <b>
                            {fmt(result.area_ha)} <small>ha</small>
                          </b>
                          <small>
                            Measured in British National Grid · EPSG:27700
                          </small>
                        </div>
                        {result.findings.map((f: any) => (
                          <button
                            key={f.key}
                            className={'finding ' + f.category}
                            onClick={() => setFinding(f)}
                          >
                            <span className="finding-top">
                              <span>
                                {f.category === 'missing'
                                  ? 'MISSING DATA'
                                  : f.category === 'constraint'
                                    ? 'MAPPED OVERLAP'
                                    : 'OBSERVATION'}
                              </span>
                              <ArrowUpRight size={15} />
                            </span>
                            <strong>{f.dataset}</strong>
                            <span className="finding-value">
                              {f.measured === null
                                ? 'Unknown'
                                : fmt(f.measured) + ' ha overlap'}
                              {f.percent !== undefined && (
                                <small> · {f.percent}% of site</small>
                              )}
                            </span>
                            <span className="finding-note">
                              {f.measured === null
                                ? 'Coverage or source unavailable. Investigate the gap.'
                                : f.measured > 0
                                  ? f.key === 'flood'
                                    ? 'Review flood context with a flood-risk specialist.'
                                    : 'Review implications with an ecologist.'
                                  : f.key === 'flood'
                                    ? 'No mapped overlap. Other flood risk may exist.'
                                    : 'No overlap in this layer. Other constraints may exist.'}
                            </span>
                          </button>
                        ))}
                        <div className="next-steps">
                          <h3>Further investigation</h3>
                          {result.next_steps.map((n: string, i: number) => (
                            <p key={n}>
                              <span>{i + 1}</span>
                              {n}
                            </p>
                          ))}
                        </div>
                      </>
                    )}
                  </TabsContent>
                  <TabsContent value="history">
                    <div className="panel-heading">
                      <h2>Assessment history</h2>
                      <p>Every run retains its boundary and source versions.</p>
                    </div>
                    {history.length ? (
                      history.map((a) => (
                        <button
                          className="history-row"
                          key={a.id}
                          onClick={() => {
                            setSelectedAssessment(a.id);
                            setTab('nature');
                            setFinding(null);
                          }}
                        >
                          <b>
                            Boundary v{a.version} · {a.state}
                          </b>
                          <small>
                            {new Date(a.created).toLocaleString('en-GB')}
                          </small>
                        </button>
                      ))
                    ) : (
                      <p className="pad">No assessments yet.</p>
                    )}
                  </TabsContent>
                  <TabsContent value="notes">
                    <div className="panel-heading">
                      <h2>Site notes</h2>
                      <p>{current.notes || 'No notes added.'}</p>
                      <button
                        onClick={() => {
                          setEditing(true);
                          setName(current.name);
                          setNotes(current.notes);
                          setGeometry(null);
                          setRawGeometry(null);
                          setNewSite(true);
                        }}
                      >
                        Edit notes
                      </button>
                    </div>
                  </TabsContent>
                </Tabs>
              </div>
            </div>
          </>
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
              <button onClick={() => setView('workspace')}>Choose sites</button>
            </div>
            <div className="workspace-content">
              {compare.length < 2 ? (
                <WorkspaceState
                  kind="empty"
                  title="Select two or three sites"
                  description="Use the checkboxes in Sites to choose the land opportunities you want to compare."
                  action={
                    <button onClick={() => setView('workspace')}>
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
        open={!!reportHtml}
        onOpenChange={(v) => {
          if (!v) {
            setReportHtml('');
            if (reportUrl) URL.revokeObjectURL(reportUrl);
            setReportUrl('');
          }
        }}
      >
        <DialogContent className="report-dialog">
          <DialogHeader>
            <DialogTitle>Screening report</DialogTitle>
            <DialogDescription>
              Saved assessment evidence, with the review decision at export.
            </DialogDescription>
          </DialogHeader>
          <div className="actions">
            <a
              className="download-link"
              href={reportUrl}
              download="CRC-screening-report.html"
            >
              Download HTML
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
            srcDoc={reportHtml}
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
            geometry={geometry}
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
            <SheetTitle>{finding?.dataset}</SheetTitle>
            <SheetDescription>
              Evidence detail · boundary v{finding?.boundary_version}
            </SheetDescription>
          </SheetHeader>
          {finding && (
            <div className="evidence-body">
              <p className="eyebrow">MEASURED OBSERVATION</p>
              <h2>
                {finding.measured === null
                  ? 'Unknown'
                  : fmt(finding.measured) + ' ha overlap'}
              </h2>
              <p>{finding.interpretation}</p>
              <dl>
                <dt>Coverage</dt>
                <dd>{finding.coverage}</dd>
                {finding.import_bbox && (
                  <>
                    <dt>Imported extent (W, S, E, N)</dt>
                    <dd>{finding.import_bbox.join(', ')}°</dd>
                  </>
                )}
                {finding.import_method && (
                  <>
                    <dt>Import method</dt>
                    <dd>{finding.import_method}</dd>
                  </>
                )}
                <dt>Method</dt>
                <dd>{finding.method}</dd>
                <dt>Rule version</dt>
                <dd>{finding.rule_version}</dd>
                <dt>Retrieved</dt>
                <dd>{finding.retrieved}</dd>
                <dt>Dataset version</dt>
                <dd>{finding.dataset_version}</dd>
              </dl>
              <a href={finding.source_url} target="_blank" rel="noreferrer">
                View authoritative source ↗
              </a>
              <h3>Limitations & uncertainty</h3>
              <p>{finding.limitations}</p>
              <p>{result?.limitations}</p>
              <small>{finding.attribution}</small>
              <p className="fineprint">
                {finding.geometry
                  ? 'The overlap geometry is highlighted on the map.'
                  : 'No overlap geometry is available for this finding.'}
              </p>
            </div>
          )}
        </SheetContent>
      </Sheet>
      {(error.includes('Sign in') ||
        error.includes('session') ||
        error.includes('Sign-in')) && (
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
