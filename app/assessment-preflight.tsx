'use client';

import {
  AlertTriangle,
  Check,
  Database,
  FileLock2,
  GitBranch,
  Play,
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
  metadata?: {
    name?: string;
    source_release?: string;
  };
};

export type RetainedSceneSourcePreview = {
  id: string;
  provider: string;
  dataset: string;
  release: string;
};

type SourceReadState = 'ready' | 'partial' | 'loading' | 'unavailable';

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

export default function AssessmentPreflight({
  open,
  siteId,
  siteName,
  boundaryVersion,
  boundaryType,
  sources,
  retainedSceneSources,
  sourceReadState,
  viewingHistorical,
  busy,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  siteId: string;
  siteName: string;
  boundaryVersion: number;
  boundaryType: string;
  sources: AssessmentSourcePreview[];
  retainedSceneSources: RetainedSceneSourcePreview[];
  sourceReadState: SourceReadState;
  viewingHistorical: boolean;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  const availableCount = sources.filter(
    (source) => source.state === 'available',
  ).length;
  const previewUnavailable =
    sourceReadState === 'loading' || sourceReadState === 'unavailable';
  const canSubmit = !busy && sources.length > 0 && sourceReadState === 'ready';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="assessment-preflight-dialog">
        <DialogHeader className="assessment-preflight-heading">
          <p className="eyebrow">ASSESSMENT PREFLIGHT</p>
          <DialogTitle>Review assessment inputs</DialogTitle>
          <DialogDescription>
            Confirm the immutable Site and source context before processing
            starts.
          </DialogDescription>
        </DialogHeader>

        <div className="assessment-preflight-body">
          {viewingHistorical && (
            <div className="assessment-preflight-message is-warning">
              <AlertTriangle size={15} aria-hidden="true" />
              This run will use the current saved Site boundary and latest
              registered sources—not the historical assessment being viewed.
            </div>
          )}
          <section
            className="assessment-preflight-scope"
            aria-labelledby="assessment-scope-title"
          >
            <div className="assessment-preflight-section-heading">
              <GitBranch size={16} aria-hidden="true" />
              <span>
                <small>RUN SCOPE</small>
                <strong id="assessment-scope-title">{siteName}</strong>
              </span>
            </div>
            <dl>
              <div>
                <dt>Boundary</dt>
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

          <section
            className="assessment-preflight-sources"
            aria-labelledby="assessment-sources-title"
          >
            <div className="assessment-preflight-section-heading">
              <Database size={16} aria-hidden="true" />
              <span>
                <small>REGISTERED EVIDENCE</small>
                <strong id="assessment-sources-title">
                  {previewUnavailable
                    ? 'Source preview unavailable'
                    : sources.length === 0
                      ? 'No source versions registered'
                      : `${sources.length} source version${sources.length === 1 ? '' : 's'} will be pinned`}
                </strong>
              </span>
              {!previewUnavailable && sources.length > 0 && (
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
                starting an assessment.
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
                At least one registered dataset version is required before an
                assessment can start.
              </div>
            )}

            {sourceReadState === 'partial' && (
              <div className="assessment-preflight-message is-warning">
                <AlertTriangle size={15} aria-hidden="true" />
                The visible registry may be incomplete. Refresh before starting
                this assessment.
              </div>
            )}
            {sources.length === 0 && retainedSceneSources.length > 0 && (
              <div className="assessment-retained-context">
                <div>
                  <strong>
                    Current map scene · {retainedSceneSources.length} retained
                  </strong>
                  <small>
                    Evidence Snapshot context—not registered input for this new
                    assessment
                  </small>
                </div>
                <ul>
                  {retainedSceneSources.map((source) => (
                    <li key={source.id}>
                      <span>{source.dataset}</span>
                      <small>
                        {source.provider} · {source.release}
                      </small>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="assessment-preflight-caveat">
              Registration does not guarantee coverage of this boundary.
              Coverage is evaluated during processing; unavailable or
              out-of-coverage evidence remains unknown, never zero.
            </p>
          </section>

          <section
            className="assessment-preflight-retention"
            aria-labelledby="assessment-retention-title"
          >
            <div className="assessment-preflight-section-heading">
              <FileLock2 size={16} aria-hidden="true" />
              <span>
                <small>WHAT WILL BE RETAINED</small>
                <strong id="assessment-retention-title">
                  One reproducible assessment record
                </strong>
              </span>
            </div>
            <ul>
              <li>
                <Check size={14} aria-hidden="true" /> Exact Site identity and
                boundary version
              </li>
              <li>
                <Check size={14} aria-hidden="true" /> Pinned dataset versions
                and service-selected model specification
              </li>
              <li>
                <Check size={14} aria-hidden="true" /> Result, gaps and source
                provenance when processing completes
              </li>
            </ul>
            <p>
              Earlier assessments remain unchanged. Identical inputs may reuse
              an existing saved assessment. Team review status is not changed.
            </p>
          </section>
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
            onClick={onConfirm}
            disabled={!canSubmit}
          >
            <Play size={15} aria-hidden="true" />
            {busy ? 'Starting…' : 'Start assessment'}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
