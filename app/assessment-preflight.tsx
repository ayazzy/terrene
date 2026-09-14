'use client';

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  Database,
  FileLock2,
  GitBranch,
  History,
  Play,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export type AssessmentSourcePreview = {
  id: string;
  key?: string;
  state: string;
  retrieved?: string;
  metadata?: { name?: string; source_release?: string };
};

export type SiteReasoningRunRequest = {
  contract_version: 'site_reasoning_run_request_v1';
  site_id: string;
  evidence_snapshot_id: string;
  evidence_content_hash: string;
  boundary_version: number;
  boundary_geometry_fingerprint: string;
  module_id: 'wetland_restoration';
  module_version: 'wetland_restoration_v0_1';
  input_binding_version: 'wetland_input_binding_v1';
  model_signature: string;
  model_spec: Record<string, unknown>;
};

export type SiteReasoningSourcePreview = {
  id: string;
  provider: string;
  dataset: string;
  source_version: string;
  retrieved_at: string;
  reference_period_status: string;
  reference_period_value: string | null;
  reference_period_qualification: string | null;
  licence_or_attribution: string | null;
  licence_metadata_status: string;
};

export type SiteReasoningSnapshotPreview = {
  snapshot_id: string;
  content_hash: string;
  schema_version: string;
  registry_version: string;
  site_id: string;
  boundary_version: number;
  boundary_geometry_fingerprint: string;
  current_boundary: boolean;
  created: string;
  evidence_as_of: string;
  source_count: number;
  observation_count: number;
  evidence_gap_count: number;
  sources: SiteReasoningSourcePreview[];
  run_request: SiteReasoningRunRequest;
};

export type SiteReasoningCatalogue = {
  contract_version: 'site_reasoning_input_catalogue_v1';
  site_id: string;
  current_boundary_version: number;
  current_boundary_geometry_fingerprint: string;
  modules: {
    module_id: string;
    module_version: string;
    input_binding_version: string;
    model_signature: string;
    model_spec: Record<string, unknown>;
    limitations: string;
    input_semantics: string;
  }[];
  snapshots: SiteReasoningSnapshotPreview[];
};

export type SiteReasoningRun = {
  id: string;
  site_id: string;
  boundary_version: number;
  evidence_snapshot_id: string;
  evidence_content_hash: string;
  module_id: string;
  module_version: string;
  input_binding_version: string;
  model_signature: string;
  result: {
    overall?: { score: number | null; band: string };
    missing_inputs?: unknown[];
  };
};

type SourceReadState = 'ready' | 'partial' | 'loading' | 'unavailable';
export type ReasoningReadState = 'idle' | 'loading' | 'ready' | 'unavailable';
type RunMode = 'snapshot' | 'acquisition';

function sourceName(source: AssessmentSourcePreview) {
  return source.metadata?.name || source.key || 'Unnamed source';
}

function sourceRelease(source: AssessmentSourcePreview) {
  return source.metadata?.source_release || source.id.slice(-12).toUpperCase();
}

function sourceStateLabel(state: string) {
  if (state === 'available') return 'Available';
  if (state === 'partial') return 'Partial';
  if (state === 'unavailable') return 'Unavailable';
  return state.replaceAll('_', ' ');
}

function shortIdentity(value: string) {
  return value.replace(/^.*:/, '').slice(0, 8).toUpperCase();
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}

function resultLabel(run: SiteReasoningRun) {
  const band = run.result.overall?.band;
  if (!band || band === 'INSUFFICIENT_DATA') return 'Insufficient evidence';
  return band.replaceAll('_', ' ').toLowerCase();
}

export default function AssessmentPreflight({
  open,
  siteId,
  siteName,
  boundaryVersion,
  boundaryType,
  sources,
  sourceReadState,
  reasoningCatalogue,
  reasoningReadState,
  reasoningError,
  operationError,
  completedRun,
  busy,
  onOpenChange,
  onRetryReasoning,
  onRunSnapshot,
  onRunAcquisition,
}: {
  open: boolean;
  siteId: string;
  siteName: string;
  boundaryVersion: number;
  boundaryType: string;
  sources: AssessmentSourcePreview[];
  sourceReadState: SourceReadState;
  reasoningCatalogue: SiteReasoningCatalogue | null;
  reasoningReadState: ReasoningReadState;
  reasoningError: string;
  operationError: string;
  completedRun: SiteReasoningRun | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onRetryReasoning: () => void;
  onRunSnapshot: (request: SiteReasoningRunRequest) => void;
  onRunAcquisition: () => void;
}) {
  const orderedSnapshots = useMemo(
    () =>
      [...(reasoningCatalogue?.snapshots || [])].sort(
        (left, right) =>
          Number(right.current_boundary) - Number(left.current_boundary) ||
          Date.parse(right.created) - Date.parse(left.created),
      ),
    [reasoningCatalogue],
  );
  const [mode, setMode] = useState<RunMode>('snapshot');
  const [selectedSnapshotId, setSelectedSnapshotId] = useState('');
  const preferredSnapshot =
    orderedSnapshots.find((snapshot) => snapshot.current_boundary) ||
    orderedSnapshots[0];
  const selectedSnapshot =
    orderedSnapshots.find(
      (snapshot) => snapshot.snapshot_id === selectedSnapshotId,
    ) || preferredSnapshot;
  const effectiveMode =
    reasoningReadState === 'ready' && !orderedSnapshots.length
      ? 'acquisition'
      : mode;
  const availableCount = sources.filter(
    (source) => source.state === 'available',
  ).length;
  const registryUnavailable =
    sourceReadState === 'loading' || sourceReadState === 'unavailable';
  const canAcquire = !busy && sources.length > 0 && sourceReadState === 'ready';
  const canRunSnapshot =
    !busy && reasoningReadState === 'ready' && !!selectedSnapshot?.run_request;

  if (completedRun)
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="assessment-preflight-dialog">
          <DialogHeader className="assessment-preflight-heading">
            <p className="eyebrow">REASONING COMPLETE</p>
            <DialogTitle>Wetland model run retained</DialogTitle>
            <DialogDescription>
              The immutable result is tied to the Evidence Snapshot you chose.
            </DialogDescription>
          </DialogHeader>
          <div className="assessment-preflight-body">
            <section className="assessment-run-complete" aria-live="polite">
              <span className="assessment-run-complete-icon">
                <Check size={18} aria-hidden="true" />
              </span>
              <div>
                <small>RESULT</small>
                <h3>{resultLabel(completedRun)}</h3>
                <p>
                  {completedRun.module_version} · Boundary v
                  {completedRun.boundary_version}
                </p>
              </div>
            </section>
            <dl className="assessment-run-identities">
              <div>
                <dt>Evidence Snapshot</dt>
                <dd>{shortIdentity(completedRun.evidence_snapshot_id)}</dd>
              </div>
              <div>
                <dt>ModuleRun</dt>
                <dd>{shortIdentity(completedRun.id)}</dd>
              </div>
              <div>
                <dt>Input binding</dt>
                <dd>{completedRun.input_binding_version}</dd>
              </div>
            </dl>
            <p className="assessment-preflight-caveat">
              This is a Terrene Reasoning result, not an Earth fact or team
              decision. The selected Evidence Snapshot and earlier assessments
              remain unchanged.
            </p>
          </div>
          <DialogFooter className="assessment-preflight-actions">
            <button
              type="button"
              className="primary"
              onClick={() => onOpenChange(false)}
            >
              Done
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="assessment-preflight-dialog">
        <DialogHeader className="assessment-preflight-heading">
          <p className="eyebrow">SITE ANALYSIS</p>
          <DialogTitle>Choose how to start</DialogTitle>
          <DialogDescription>
            Run a model from retained evidence, or acquire a new legacy
            assessment from registered datasets.
          </DialogDescription>
        </DialogHeader>

        <div className="assessment-preflight-body">
          <section
            className="assessment-preflight-scope"
            aria-labelledby="assessment-scope-title"
          >
            <div className="assessment-preflight-section-heading">
              <GitBranch size={16} aria-hidden="true" />
              <span>
                <small>SITE</small>
                <strong id="assessment-scope-title">{siteName}</strong>
              </span>
            </div>
            <dl>
              <div>
                <dt>Current boundary</dt>
                <dd>Version {boundaryVersion}</dd>
              </div>
              <div>
                <dt>Geometry</dt>
                <dd>{boundaryType || 'Saved Site geometry'}</dd>
              </div>
              <div>
                <dt>Site identity</dt>
                <dd>{siteId.slice(-8).toUpperCase()}</dd>
              </div>
            </dl>
          </section>

          <div
            className="assessment-mode-picker"
            role="radiogroup"
            aria-label="Analysis input path"
          >
            <label
              className={effectiveMode === 'snapshot' ? 'is-selected' : ''}
            >
              <input
                type="radio"
                name="assessment-input-path"
                value="snapshot"
                checked={effectiveMode === 'snapshot'}
                onChange={() => setMode('snapshot')}
                disabled={
                  reasoningReadState === 'ready' && !orderedSnapshots.length
                }
              />
              <Sparkles size={17} aria-hidden="true" />
              <span>
                <strong>Use retained evidence</strong>
                <small>Run a model without reacquiring sources</small>
              </span>
            </label>
            <label
              className={effectiveMode === 'acquisition' ? 'is-selected' : ''}
            >
              <input
                type="radio"
                name="assessment-input-path"
                value="acquisition"
                checked={effectiveMode === 'acquisition'}
                onChange={() => setMode('acquisition')}
              />
              <Database size={17} aria-hidden="true" />
              <span>
                <strong>Acquire new evidence</strong>
                <small>Use the legacy registered-dataset pipeline</small>
              </span>
            </label>
          </div>

          {effectiveMode === 'snapshot' ? (
            <section
              className="assessment-preflight-sources"
              aria-labelledby="reasoning-snapshots-title"
            >
              <div className="assessment-preflight-section-heading">
                <FileLock2 size={16} aria-hidden="true" />
                <span>
                  <small>IMMUTABLE INPUT</small>
                  <strong id="reasoning-snapshots-title">
                    Choose an Evidence Snapshot
                  </strong>
                </span>
                {orderedSnapshots.length > 0 && (
                  <span className="assessment-source-summary">
                    {orderedSnapshots.length} retained
                  </span>
                )}
              </div>

              {reasoningReadState === 'loading' ||
              reasoningReadState === 'idle' ? (
                <output className="assessment-preflight-message">
                  Loading verified Evidence Snapshots…
                </output>
              ) : reasoningReadState === 'unavailable' ? (
                <div className="assessment-preflight-message is-warning">
                  <AlertTriangle size={15} aria-hidden="true" />
                  <span>
                    {reasoningError ||
                      'Evidence Snapshots could not be verified.'}
                    <button
                      type="button"
                      className="text-btn"
                      onClick={onRetryReasoning}
                    >
                      <RefreshCw size={13} aria-hidden="true" /> Retry
                    </button>
                  </span>
                </div>
              ) : orderedSnapshots.length === 0 ? (
                <div className="assessment-preflight-message is-warning">
                  <AlertTriangle size={15} aria-hidden="true" />
                  No committed Evidence Snapshot is available for this Site.
                  Acquire new evidence when registered datasets are available.
                </div>
              ) : (
                <div
                  className="assessment-snapshot-options"
                  role="radiogroup"
                  aria-label="Evidence Snapshot"
                >
                  {orderedSnapshots.map((snapshot) => (
                    <label
                      className={
                        selectedSnapshot?.snapshot_id === snapshot.snapshot_id
                          ? 'is-selected'
                          : ''
                      }
                      key={snapshot.snapshot_id}
                    >
                      <input
                        type="radio"
                        name="evidence-snapshot"
                        value={snapshot.snapshot_id}
                        checked={
                          selectedSnapshot?.snapshot_id === snapshot.snapshot_id
                        }
                        onChange={() =>
                          setSelectedSnapshotId(snapshot.snapshot_id)
                        }
                      />
                      <span className="assessment-snapshot-choice">
                        <span
                          className="assessment-radio-dot"
                          aria-hidden="true"
                        />
                        <span>
                          <strong>
                            {snapshot.current_boundary
                              ? 'Current boundary evidence'
                              : `Historical boundary v${snapshot.boundary_version}`}
                          </strong>
                          <small>
                            Evidence as of{' '}
                            {displayDate(snapshot.evidence_as_of)}
                            {' · '}
                            {snapshot.registry_version.replace(
                              'land_evidence_registry_',
                              '',
                            )}
                          </small>
                        </span>
                      </span>
                      <span className="assessment-snapshot-counts">
                        {snapshot.source_count} sources ·{' '}
                        {snapshot.observation_count} observations ·{' '}
                        {snapshot.evidence_gap_count} gaps
                      </span>
                    </label>
                  ))}
                </div>
              )}

              {selectedSnapshot && (
                <div className="assessment-selected-snapshot">
                  {!selectedSnapshot.current_boundary && (
                    <div className="assessment-preflight-message is-warning">
                      <History size={15} aria-hidden="true" />
                      This run stays tied to historical boundary v
                      {selectedSnapshot.boundary_version}. It will not use or
                      change the current boundary.
                    </div>
                  )}
                  <div className="assessment-selected-model">
                    <span>
                      <small>MODEL</small>
                      <strong>Wetland assessment</strong>
                    </span>
                    <code>{selectedSnapshot.run_request.module_version}</code>
                  </div>
                  <ul className="assessment-source-list assessment-snapshot-source-list">
                    {selectedSnapshot.sources.map((source) => (
                      <li key={source.id}>
                        <span>
                          <strong>{source.dataset}</strong>
                          <small>
                            {source.provider} · {source.source_version}
                          </small>
                        </span>
                        <span className="assessment-source-state state-available">
                          Retained
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="assessment-preflight-caveat">
                    The snapshot is the evidence boundary. Only inputs mapped by
                    {` ${selectedSnapshot.run_request.input_binding_version} `}
                    affect this model; retained building and height evidence is
                    not silently treated as a wetland input.
                  </p>
                </div>
              )}
            </section>
          ) : (
            <section
              className="assessment-preflight-sources"
              aria-labelledby="assessment-sources-title"
            >
              <div className="assessment-preflight-section-heading">
                <Database size={16} aria-hidden="true" />
                <span>
                  <small>REGISTERED DATASETS</small>
                  <strong id="assessment-sources-title">
                    {registryUnavailable
                      ? 'Source preview unavailable'
                      : sources.length === 0
                        ? 'No source versions registered'
                        : `${sources.length} source version${sources.length === 1 ? '' : 's'} will be pinned`}
                  </strong>
                </span>
                {!registryUnavailable && sources.length > 0 && (
                  <span className="assessment-source-summary">
                    {availableCount} available
                  </span>
                )}
              </div>

              {sourceReadState === 'loading' ? (
                <output className="assessment-preflight-message">
                  Loading the source registry…
                </output>
              ) : sourceReadState === 'unavailable' ? (
                <div className="assessment-preflight-message is-warning">
                  <AlertTriangle size={15} aria-hidden="true" />
                  The source registry could not be verified. Refresh before
                  acquiring evidence.
                </div>
              ) : sources.length ? (
                <ul className="assessment-source-list">
                  {sources.map((source) => (
                    <li key={source.id}>
                      <span>
                        <strong>{sourceName(source)}</strong>
                        <small>Release {sourceRelease(source)}</small>
                      </span>
                      <span
                        className={`assessment-source-state state-${source.state}`}
                      >
                        {sourceStateLabel(source.state)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="assessment-preflight-message is-warning">
                  <AlertTriangle size={15} aria-hidden="true" />
                  At least one registered dataset version is required before a
                  new assessment can start.
                </div>
              )}

              {sourceReadState === 'partial' && (
                <div className="assessment-preflight-message is-warning">
                  <AlertTriangle size={15} aria-hidden="true" />
                  The visible registry may be incomplete. Refresh before
                  starting this assessment.
                </div>
              )}
              <p className="assessment-preflight-caveat">
                This path uses the current Site boundary and latest registered
                dataset versions. Registration does not guarantee boundary
                coverage; unavailable evidence remains unknown, never zero.
              </p>
            </section>
          )}

          <section
            className="assessment-preflight-retention"
            aria-labelledby="assessment-retention-title"
          >
            <div className="assessment-preflight-section-heading">
              <FileLock2 size={16} aria-hidden="true" />
              <span>
                <small>HISTORY</small>
                <strong id="assessment-retention-title">
                  Existing records stay unchanged
                </strong>
              </span>
            </div>
            <ul>
              <li>
                <Check size={14} aria-hidden="true" /> Exact Site, boundary,
                evidence and model identities are retained
              </li>
              <li>
                <Check size={14} aria-hidden="true" /> Identical inputs safely
                reuse the existing immutable result
              </li>
              <li>
                <Check size={14} aria-hidden="true" /> Team review status is not
                changed
              </li>
            </ul>
          </section>
          {operationError && (
            <div
              className="assessment-preflight-message is-warning"
              role="alert"
            >
              <AlertTriangle size={15} aria-hidden="true" />
              {operationError}
            </div>
          )}
        </div>

        <DialogFooter className="assessment-preflight-actions">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="primary"
            onClick={() =>
              effectiveMode === 'snapshot' && selectedSnapshot
                ? onRunSnapshot(selectedSnapshot.run_request)
                : onRunAcquisition()
            }
            disabled={
              effectiveMode === 'snapshot' ? !canRunSnapshot : !canAcquire
            }
          >
            <Play size={15} aria-hidden="true" />
            {busy
              ? 'Starting…'
              : effectiveMode === 'snapshot'
                ? 'Run wetland model'
                : 'Acquire assessment'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
