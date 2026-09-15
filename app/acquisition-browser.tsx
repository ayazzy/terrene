'use client';

import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type SyntheticEvent,
} from 'react';
import { ArrowRight, Database, RefreshCw, Search, X } from 'lucide-react';
import {
  acquisitionSources,
  defaultCaptureQuery,
  captureBounds,
  evidenceDateLabel,
  readCaptureCatalogue,
  readCaptureDetail,
  type Capture,
  type CaptureQuery,
} from './acquisitions';
import { createCaptureBrowser } from './acquisition-browser-state';
import styles from './acquisition-browser.module.css';

const locations = [
  ['any', 'Any retained location', ''],
  ['uk', 'UK extent', '-8.7,49.8,2,61'],
  ['oxford', 'Oxford area', '-1.4,51.6,-1.1,51.9'],
  ['edinburgh', 'Edinburgh area', '-3.4,55.8,-3,56.1'],
  ['cardiff', 'Cardiff area', '-3.4,51.3,-3,51.7'],
  ['belfast', 'Belfast area', '-6.2,54.4,-5.7,54.8'],
  ['custom', 'Custom bounds', ''],
] as const;
const families = {
  vector: 'Designations',
  raster: 'Elevation',
  satellite: 'Satellite imagery',
  weather_timeseries: 'Historical weather',
};
const seriesLabels: Record<string, string> = {
  mapped_features: 'Mapped features / components',
  elevation: 'Elevation',
  blue: 'Blue',
  green: 'Green',
  red: 'Red',
  nir: 'Near infrared',
  scl: 'Scene classification',
  T2M: 'Mean temperature',
  T2M_MIN: 'Minimum temperature',
  T2M_MAX: 'Maximum temperature',
  PRECTOTCORR: 'Precipitation',
  WS10M: 'Wind speed',
  RH2M: 'Relative humidity',
};
const number = (value: number) => value.toLocaleString('en-GB');
const captured = (value: string) =>
  new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(value)) + ' UTC';
const bytes = (value: number) =>
  value >= 1e6
    ? `${(value / 1e6).toFixed(1)} MB`
    : `${number(Math.round(value / 1000))} kB`;
function locationLabel(entry: Capture) {
  const bounds = captureBounds(entry.requested_geometry);
  return entry.requested_geometry.type === 'Point'
    ? `${bounds[0].toFixed(5)}°, ${bounds[1].toFixed(5)}° (longitude, latitude)`
    : bounds.map((n) => n.toFixed(5) + '°').join(', ');
}

export default function AcquisitionBrowser() {
  const [browser] = useState(() =>
    createCaptureBrowser(
      { catalogue: readCaptureCatalogue, detail: readCaptureDetail },
      defaultCaptureQuery,
    ),
  );
  const state = useSyncExternalStore(
    browser.subscribe,
    browser.getSnapshot,
    browser.getSnapshot,
  );
  const [source, setSource] = useState('');
  const [location, setLocation] = useState('any');
  const [bounds, setBounds] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [basis, setBasis] = useState<'evidence' | 'capture'>('evidence');
  const [formError, setFormError] = useState('');
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const captureButtons = useRef(new Map<string, HTMLButtonElement>());
  useEffect(() => {
    void browser.search(defaultCaptureQuery);
    return () => browser.dispose();
  }, [browser]);
  useEffect(() => {
    if (state.selected) detailHeading.current?.focus();
  }, [state.selected]);
  function search(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!!start !== !!end || (start && start > end)) {
      setFormError('Choose both dates, with the end on or after the start.');
      return;
    }
    const bbox =
      location === 'custom'
        ? bounds.trim()
        : locations.find((l) => l[0] === location)?.[2];
    if (location === 'custom') {
      const values = bbox?.split(',').map(Number) ?? [];
      if (
        !bbox ||
        bbox.split(',').some((v) => !v.trim()) ||
        values.length !== 4 ||
        !values.every(Number.isFinite) ||
        !(
          -180 <= values[0] &&
          values[0] < values[2] &&
          values[2] <= 180 &&
          -90 <= values[1] &&
          values[1] < values[3] &&
          values[3] <= 90
        )
      ) {
        setFormError(
          'Enter valid west, south, east and north bounds in degrees.',
        );
        return;
      }
    }
    const query: CaptureQuery = {
      time_basis: basis,
      limit: 10,
      ...(source ? { source_id: source } : {}),
      ...(bbox ? { bbox } : {}),
      ...(start ? { start_date: start, end_date: end } : {}),
    };
    setFormError('');
    void browser.search(query);
  }
  function close() {
    const id = state.selected?.acquisition_id;
    browser.close();
    if (id) captureButtons.current.get(id)?.focus();
  }
  const entry = state.detail?.entry;
  const appliedSource =
    acquisitionSources.find(([id]) => id === state.query.source_id)?.[1] ??
    'All sources';
  return (
    <section className={styles.browser} aria-labelledby="captures-title">
      <header className={styles.heading}>
        <div>
          <p className="eyebrow">TERRENE EARTH</p>
          <h2 id="captures-title">Retained captures</h2>
          <p>
            Find evidence we have collected and inspect its original source,
            location and dates.
          </p>
        </div>
        <span className={styles.tag}>
          <Database size={14} aria-hidden="true" /> Read-only library
        </span>
      </header>
      <form
        className={styles.filters}
        onSubmit={search}
        aria-label="Search retained captures"
      >
        <div className={styles.fields}>
          <label>
            Source
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">All sources</option>
              {acquisitionSources.map(([id, label]) => (
                <option value={id} key={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Location
            <select
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            >
              {locations.map(([id, label]) => (
                <option value={id} key={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date refers to
            <select
              value={basis}
              onChange={(e) =>
                setBasis(e.target.value as 'evidence' | 'capture')
              }
            >
              <option value="evidence">Evidence date</option>
              <option value="capture">Capture date</option>
            </select>
          </label>
          <label>
            From (UTC)
            <input
              type="date"
              value={start}
              max={end || '9998-12-31'}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            To (UTC)
            <input
              type="date"
              value={end}
              min={start || undefined}
              max="9998-12-31"
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <button type="submit" className={styles.search}>
            <Search size={16} aria-hidden="true" /> Search captures
          </button>
        </div>
        {location === 'custom' && (
          <label className={styles.bounds}>
            Bounds: west, south, east, north
            <input
              value={bounds}
              onChange={(e) => setBounds(e.target.value)}
              placeholder="-1.4, 51.6, -1.1, 51.9"
              required
              aria-describedby="capture-location-note"
            />
          </label>
        )}
        <p id="capture-location-note" className={styles.note}>
          Locations use bounding boxes intersecting the original request.
          Weather matches a query point, not surrounding land coverage.
        </p>
        <p className={styles.note}>
          {basis === 'evidence'
            ? 'Evidence-date searches omit undated designations and composite LIDAR. Leave dates blank to include them.'
            : 'Capture date means when Terrene collected the evidence; it does not establish its observation or survey date.'}{' '}
          Start and end dates are inclusive.
        </p>
        {formError && (
          <p role="alert" className={styles.error}>
            {formError}
          </p>
        )}
      </form>
      <div className={styles.resultsHeading}>
        <div>
          <h3>Search results</h3>
          <p>
            {appliedSource} ·{' '}
            {state.query.bbox
              ? 'Within applied location bounds'
              : 'Any retained location'}{' '}
            ·{' '}
            {state.query.start_date
              ? `${state.query.start_date} to ${state.query.end_date} (${state.query.time_basis} dates)`
              : 'All dates'}
          </p>
        </div>
        <button
          type="button"
          className="text-btn"
          disabled={state.listStatus === 'loading'}
          onClick={() => void browser.search(state.query)}
        >
          <RefreshCw size={14} aria-hidden="true" /> Restart search
        </button>
      </div>
      <div className={styles.layout}>
        <div className={styles.results}>
          <output className={styles.summary}>
            {state.listStatus === 'idle' || state.listStatus === 'loading'
              ? 'Searching retained captures…'
              : `${number(state.entries.length)} ${state.entries.length === 1 ? 'match' : 'matches'} loaded · ${number(state.scanned)} captures checked`}
            {state.page && (
              <span>
                {state.page.scan_complete
                  ? 'Reached the end of this search.'
                  : 'More captures remain to be checked.'}
              </span>
            )}
          </output>
          {state.listStatus === 'error' && (
            <div role="alert" className={styles.error}>
              <strong>Search unavailable</strong>
              <p>{state.listError}</p>
              <button
                type="button"
                className="text-btn"
                onClick={() =>
                  void (state.page?.next_cursor
                    ? browser.more()
                    : browser.search(state.query))
                }
              >
                Retry search
              </button>
            </div>
          )}
          {state.listStatus === 'ready' && !state.entries.length && (
            <div className={styles.empty}>
              <Search size={22} aria-hidden="true" />
              <h4>
                {state.page?.scan_complete
                  ? 'No matching retained captures'
                  : 'No matches in the captures checked so far'}
              </h4>
              <p>
                {state.page?.scan_complete
                  ? 'Try another location, source or date range. This library contains successful captures for your organization; an empty search does not establish absence in the real world.'
                  : 'Continue the search to check the next batch. An empty batch is not a completed search.'}
              </p>
            </div>
          )}
          <ul className={styles.list} aria-label="Matching retained captures">
            {state.entries.map((capture) => (
              <li key={capture.acquisition_id + capture.attempt_id}>
                <button
                  type="button"
                  ref={(node) => {
                    if (node)
                      captureButtons.current.set(capture.acquisition_id, node);
                    else captureButtons.current.delete(capture.acquisition_id);
                  }}
                  aria-pressed={
                    state.selected?.acquisition_id === capture.acquisition_id
                  }
                  aria-controls="capture-detail"
                  onClick={() => void browser.select(capture)}
                >
                  <span className={styles.rowTop}>
                    <span className={styles.family}>
                      {families[capture.family]}
                    </span>
                    <ArrowRight size={16} aria-hidden="true" />
                  </span>
                  <strong>{capture.source_label}</strong>
                  <span>
                    {evidenceDateLabel(capture)}
                    {capture.evidence_time.kind !== 'unknown'
                      ? ' · evidence date'
                      : ''}
                  </span>
                  <small>Captured {captured(capture.capture_completed)}</small>
                  <small>{locationLabel(capture)}</small>
                  <small>
                    {capture.requested_geometry.type === 'Point'
                      ? 'Query point'
                      : 'Requested area'}{' '}
                    · {bytes(capture.artifact_bytes)} retained ·{' '}
                    {capture.acquisition_id.slice(0, 8)}
                  </small>
                  <span className={styles.unchecked}>
                    Metadata checked · open to verify files
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {state.page?.next_cursor && state.listStatus !== 'error' && (
            <button
              type="button"
              className={styles.continue}
              disabled={state.listStatus === 'loading'}
              onClick={() => void browser.more()}
            >
              {state.listStatus === 'loading'
                ? 'Checking next batch…'
                : 'Continue search'}
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          )}
          <p className={styles.note}>
            Newest collection requests first. Restart the search to include
            newly completed captures.
          </p>
        </div>
        <section
          id="capture-detail"
          className={styles.detail}
          aria-labelledby="capture-detail-title"
        >
          <header>
            <h3 id="capture-detail-title" tabIndex={-1} ref={detailHeading}>
              {state.selected ? 'Capture details' : 'Inspect a capture'}
            </h3>
            {state.selected && (
              <button
                type="button"
                className="text-btn"
                aria-label="Close capture details"
                onClick={close}
              >
                <X size={17} />
              </button>
            )}
          </header>
          {!state.selected && (
            <p className={styles.note}>
              Choose a result to check its retained files and inspect
              source-specific availability. File verification can take a moment
              for large captures.
            </p>
          )}
          {state.detailStatus === 'loading' && (
            <output>
              Checking retained files for {state.selected?.source_label}…
            </output>
          )}
          {state.detailStatus === 'error' && (
            <div className={styles.error} role="alert">
              <strong>Capture could not be opened</strong>
              <p>{state.detailError}</p>
              <button
                type="button"
                className="text-btn"
                onClick={() =>
                  state.selected && void browser.select(state.selected)
                }
              >
                Retry file verification
              </button>
            </div>
          )}
          {entry && (
            <>
              <span className={styles.verified}>Retained files verified</span>
              <h4>{entry.source_label}</h4>
              <dl className={styles.facts}>
                <div>
                  <dt>Evidence date (UTC)</dt>
                  <dd>{evidenceDateLabel(entry)}</dd>
                </div>
                <div>
                  <dt>Captured (UTC)</dt>
                  <dd>{captured(entry.capture_completed)}</dd>
                </div>
                <div>
                  <dt>
                    {entry.requested_geometry.type === 'Point'
                      ? 'Requested query point'
                      : 'Requested polygon bounds'}
                  </dt>
                  <dd>
                    {locationLabel(entry)}
                    {entry.requested_geometry.type !== 'Point' && (
                      <small>
                        West, south, east, north. Bounds are not the full
                        polygon.
                      </small>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Retained files</dt>
                  <dd>
                    {number(entry.artifact_count)} files ·{' '}
                    {bytes(entry.artifact_bytes)}
                  </dd>
                </div>
              </dl>
              <h4>Evidence availability</h4>
              <p className={styles.note}>
                Counts cover the original request, not the location search box.
              </p>
              <ul className={styles.counts}>
                {entry.counts.map((c) => (
                  <li key={c.series}>
                    <span>{seriesLabels[c.series] ?? c.series}</span>
                    <strong>
                      {number(c.present)}
                      {c.expected !== null ? ` / ${number(c.expected)}` : ''}
                      <small>
                        {c.measure === 'present_days'
                          ? 'days present'
                          : c.measure === 'valid_cells'
                            ? 'valid cells'
                            : 'selected features'}
                      </small>
                    </strong>
                  </li>
                ))}
              </ul>
              <ul className={styles.caveats}>
                {entry.evidence_semantics.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
              <details className={styles.identity}>
                <summary>
                  Capture identity &amp; retained file references
                </summary>
                <dl>
                  {[
                    ['Acquisition', entry.acquisition_id],
                    ['Exact attempt', entry.attempt_id],
                    ['Source', entry.source_id],
                    ['Adapter', entry.adapter_version],
                    ['Manifest SHA-256', entry.manifest_sha256],
                    ['Request SHA-256', entry.request_sha256],
                    ['Geometry fingerprint', entry.geometry_fingerprint],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
                <ul>
                  {state.detail?.artifacts.map((a) => (
                    <li key={a.role}>
                      <strong>{a.role}</strong>
                      <span>{bytes(a.bytes)}</span>
                      <code>{a.sha256}</code>
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
        </section>
      </div>
    </section>
  );
}
