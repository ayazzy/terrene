'use client';

import { useState, type ReactNode } from 'react';
import {
  ArrowLeft,
  ArrowUpRight,
  Clock3,
  Droplets,
  FileLock2,
  RefreshCw,
} from 'lucide-react';
import type { Model } from './nature-panel';
import type { SiteReasoningRunsState } from './use-site-reasoning-runs';
import type { SiteReasoningRunSummary } from './site-reasoning-runs';

const WETLAND_MODEL_VERSION = 'wetland_restoration_v0_1';

function modelState(model: Model | undefined, assessmentState?: string) {
  if (model) {
    return model.overall.band === 'INSUFFICIENT_DATA'
      ? 'Insufficient evidence'
      : model.overall.band.replaceAll('_', ' ').toLowerCase();
  }
  if (assessmentState === 'queued' || assessmentState === 'running')
    return `Assessment ${assessmentState}`;
  return 'No result for this assessment';
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function shortIdentity(value: string) {
  return value.replace(/^.*:/, '').slice(0, 8).toUpperCase();
}

function runResultState(run: SiteReasoningRunSummary) {
  return run.result_band === 'INSUFFICIENT_DATA'
    ? 'Insufficient evidence'
    : run.result_band.replaceAll('_', ' ').toLowerCase();
}

export default function SiteModelCatalogue({
  model,
  assessmentState,
  reasoningRuns,
  reasoningRunsState,
  reasoningRunsError,
  onRetryReasoningRuns,
  children,
}: {
  model?: Model;
  assessmentState?: string;
  reasoningRuns: SiteReasoningRunSummary[];
  reasoningRunsState: SiteReasoningRunsState;
  reasoningRunsError: string;
  onRetryReasoningRuns: () => void;
  children: ReactNode;
}) {
  const [selected, setSelected] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const selectedRun =
    reasoningRuns.find((run) => run.id === selectedRunId) || null;

  if (selected)
    return (
      <div className="selected-model-workspace">
        <button
          type="button"
          className="model-catalogue-back text-btn"
          onClick={() => setSelected(false)}
        >
          <ArrowLeft size={14} /> Back to model catalogue
        </button>
        {children}
      </div>
    );

  const state = modelState(model, assessmentState);
  const resultState = model
    ? model.overall.band === 'INSUFFICIENT_DATA'
      ? 'is-warning'
      : 'is-available'
    : 'is-unavailable';

  return (
    <section
      className="model-catalogue"
      aria-labelledby="model-catalogue-title"
    >
      <header className="model-catalogue-heading">
        <p className="eyebrow">TERRENE REASONING</p>
        <h2 id="model-catalogue-title">Analytical models</h2>
        <p>
          Inspect the selected legacy assessment result or a separately retained
          snapshot-bound run.
        </p>
      </header>
      <div className="model-catalogue-list" aria-label="Available models">
        <article className="model-catalogue-card">
          <div className="model-catalogue-card-heading">
            <span className="model-catalogue-icon" aria-hidden="true">
              <Droplets size={18} />
            </span>
            <span className={`model-catalogue-state ${resultState}`}>
              {state}
            </span>
          </div>
          <p className="context-kind">Nature intelligence</p>
          <h3>Wetland assessment</h3>
          <p>
            Separates physical potential, restoration need and implementation
            feasibility. Required evidence gaps prevent an overall result.
          </p>
          <dl>
            <div>
              <dt>Version</dt>
              <dd className="model-catalogue-version">
                {model?.model_version || WETLAND_MODEL_VERSION}
              </dd>
            </div>
            <div>
              <dt>Evidence state</dt>
              <dd className="model-catalogue-result-state">{state}</dd>
            </div>
          </dl>
          <button type="button" onClick={() => setSelected(true)}>
            Open assessment result <ArrowUpRight size={15} />
          </button>
        </article>
      </div>
      <section
        className="site-reasoning-run-catalogue"
        aria-labelledby="site-reasoning-runs-title"
      >
        <header>
          <span className="model-catalogue-icon" aria-hidden="true">
            <FileLock2 size={17} />
          </span>
          <span>
            <p className="context-kind">Immutable history</p>
            <h3 id="site-reasoning-runs-title">Snapshot-bound runs</h3>
          </span>
          {reasoningRunsState === 'ready' && (
            <span className="model-catalogue-state">
              {reasoningRuns.length} retained
            </span>
          )}
        </header>
        <p>
          These model results are bound to explicit Evidence Snapshots and are
          separate from the selected legacy assessment above.
        </p>
        {reasoningRunsState === 'loading' || reasoningRunsState === 'idle' ? (
          <output className="site-reasoning-runs-message">
            Loading retained model runs…
          </output>
        ) : reasoningRunsState === 'unavailable' ? (
          <div className="site-reasoning-runs-message is-warning" role="alert">
            <span>
              {reasoningRunsError || 'Retained model runs are unavailable.'}
            </span>
            <button type="button" onClick={onRetryReasoningRuns}>
              <RefreshCw size={13} /> Retry
            </button>
          </div>
        ) : reasoningRuns.length === 0 ? (
          <p className="site-reasoning-runs-empty">
            No snapshot-bound wetland runs have been retained for this Site. Use
            New Analysis to run the model from an Evidence Snapshot.
          </p>
        ) : (
          <div className="site-reasoning-runs-layout">
            <div
              className="site-reasoning-run-list"
              aria-label="Retained snapshot-bound model runs"
            >
              {reasoningRuns.map((run) => (
                <button
                  type="button"
                  key={run.id}
                  aria-label={`${runResultState(run)} snapshot-bound run completed ${displayDate(run.completed)}, ${run.current_boundary ? 'current boundary' : `historical boundary version ${run.boundary_version}`}`}
                  aria-pressed={selectedRun?.id === run.id}
                  onClick={() =>
                    setSelectedRunId((selectedId) =>
                      selectedId === run.id ? null : run.id,
                    )
                  }
                >
                  <span>
                    <strong>{runResultState(run)}</strong>
                    <small>
                      <Clock3 size={12} aria-hidden="true" />{' '}
                      {displayDate(run.completed)}
                    </small>
                  </span>
                  <span>
                    <small>
                      {run.current_boundary
                        ? 'Current boundary'
                        : `Historical boundary v${run.boundary_version}`}
                    </small>
                    <code>{shortIdentity(run.id)}</code>
                  </span>
                </button>
              ))}
            </div>
            {selectedRun && (
              <article className="site-reasoning-run-detail">
                <header>
                  <span>
                    <p className="context-kind">Retained ModuleRun</p>
                    <h4>{runResultState(selectedRun)}</h4>
                  </span>
                  <span
                    className={`model-catalogue-state ${selectedRun.result_band === 'INSUFFICIENT_DATA' ? 'is-warning' : 'is-available'}`}
                  >
                    {selectedRun.current_boundary
                      ? 'Current boundary'
                      : 'Historical boundary'}
                  </span>
                </header>
                <dl>
                  <div>
                    <dt>Evidence coverage</dt>
                    <dd>
                      {selectedRun.data_coverage_available ?? 'Unknown'} /{' '}
                      {selectedRun.data_coverage_required ?? 'unknown'} inputs
                    </dd>
                  </div>
                  <div>
                    <dt>Missing inputs</dt>
                    <dd>{selectedRun.missing_input_count}</dd>
                  </div>
                  <div>
                    <dt>Evidence as of</dt>
                    <dd>{displayDate(selectedRun.evidence_as_of)}</dd>
                  </div>
                  <div>
                    <dt>Model version</dt>
                    <dd>{selectedRun.module_version}</dd>
                  </div>
                  <div>
                    <dt>Evidence Snapshot</dt>
                    <dd>{shortIdentity(selectedRun.evidence_snapshot_id)}</dd>
                  </div>
                  <div>
                    <dt>Input binding</dt>
                    <dd>{selectedRun.input_binding_version}</dd>
                  </div>
                </dl>
                <p>
                  This retained model interpretation is not a Terrene Earth fact
                  or team decision.
                </p>
              </article>
            )}
          </div>
        )}
      </section>
      <p className="model-catalogue-note">
        Model outputs are interpretations, not Terrene Earth facts or team
        decisions.
      </p>
    </section>
  );
}
