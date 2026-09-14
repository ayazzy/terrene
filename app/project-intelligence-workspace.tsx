'use client';
import { useState, type Ref } from 'react';
import { AlertTriangle, ArrowRight, RefreshCw } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import EntityDossier from './entity-dossier';
import { WorkspaceLoading, WorkspaceState } from './status-primitives';
import {
  claimValue,
  evidenceStateLabel,
  formatEvidenceTime,
  humanize,
  projectEvidenceSourceKey,
  type EvidenceState,
  type ProjectIntelligenceRun,
} from './project-intelligence';
import { useProjectIntelligenceState } from './use-project-intelligence-state';
import type { OperatingDossierSection } from './operating-picture-state';

function StatePill({ state }: { state: EvidenceState }) {
  return <span className={'intelligence-state state-' + state}>{evidenceStateLabel(state)}</span>;
}

function References({ references, onOpen }: { references: Array<{ claim_id: string }>; onOpen: (claimId: string) => void }) {
  return references.length ? (
    <span className="intelligence-references">
      {references.map((reference) => <button key={reference.claim_id} onClick={() => onOpen(reference.claim_id)}>{reference.claim_id}</button>)}
    </span>
  ) : (
    <span className="intelligence-references">No supporting claim</span>
  );
}

function Overview({ run, onOpenClaim }: { run: ProjectIntelligenceRun; onOpenClaim: (claimId: string) => void }) {
  const result = run.result;
  const timing = result.grid_connection_target;
  return (
    <div className="intelligence-tab-body">
      <div className="intelligence-distinction">
        <span>TERRENE CONCLUSION</span>
        <p>Deterministic interpretation of the explicitly bound source assertions below.</p>
      </div>
      <div className="intelligence-summary-grid">
        <article>
          <small>Reported stage</small>
          <h2>{humanize(result.reported_stage.value)}</h2>
          <StatePill state={result.reported_stage.evidence_state} />
          <References references={result.reported_stage.references} onOpen={onOpenClaim} />
        </article>
        <article>
          <small>Planning status</small>
          <h3>{result.planning_status.values.map(humanize).join(' · ') || 'Not established'}</h3>
          <StatePill state={result.planning_status.evidence_state} />
          <References references={result.planning_status.references} onOpen={onOpenClaim} />
        </article>
        <article>
          <small>Construction status</small>
          <h3>{result.construction_status.values.map(humanize).join(' · ') || 'Not established'}</h3>
          <StatePill state={result.construction_status.evidence_state} />
          <References references={result.construction_status.references} onOpen={onOpenClaim} />
        </article>
        <article>
          <small>Reported grid target</small>
          <h3>{timing.targets.map((target) => target.date).join(' · ') || 'Not established'}</h3>
          <StatePill state={timing.evidence_state} />
          {timing.targets.map((target) => (
            <p className="intelligence-timing" key={target.date}>
              {humanize(target.temporal_state)}
            </p>
          ))}
          <References references={timing.references} onOpen={onOpenClaim} />
        </article>
      </div>
      <section className="intelligence-limitations">
        <h3>Limits of this result</h3>
        <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
    </div>
  );
}

function Evidence({ run, focusedClaimId }: { run: ProjectIntelligenceRun; focusedClaimId: string | null }) {
  const binding = run.evidence_binding;
  const sources = new Map(binding.sources.map((item) => [
    projectEvidenceSourceKey(item.source.id, item.source.source_version),
    item.source,
  ]));
  const active = new Set(binding.active_claim_ids);
  return (
    <div className="intelligence-tab-body">
      <div className="intelligence-distinction source">
        <span>SOURCE ASSERTIONS</span>
        <p>Retained claims and passages. These are attributed assertions, not Terrene conclusions.</p>
      </div>
      <div className="binding-strip">
        <span>{binding.bundles.length} explicit bundle{binding.bundles.length === 1 ? '' : 's'}</span>
        <code>{binding.id}</code>
      </div>
      <div className="claim-list">
        {binding.claims.map((item) => {
          const source = sources.get(projectEvidenceSourceKey(
            item.source_record_id,
            item.source_version,
          ));
          return (
            <article key={item.claim.id} className={active.has(item.claim.id) ? '' : 'is-superseded'} data-focused={item.claim.id === focusedClaimId} data-project-claim={item.claim.id} tabIndex={-1}>
              <div className="claim-heading">
                <span>{active.has(item.claim.id) ? 'Active assertion' : 'Superseded assertion'}</span>
                <code>{item.claim.id}</code>
              </div>
              <h3>{humanize(item.claim.predicate)} · {claimValue(item.claim.value)}</h3>
              <blockquote>{item.claim.locator.exact_passage}</blockquote>
              <dl>
                <div><dt>Source</dt><dd>{source?.publisher} · {source?.title}</dd></div>
                <div><dt>Version</dt><dd>{item.source_version}</dd></div>
                <div><dt>Published</dt><dd>{source?.published_at ? formatEvidenceTime(source.published_at) : 'Not reported'}</dd></div>
                <div><dt>Recorded</dt><dd>{source ? formatEvidenceTime(source.recorded_at) : 'Unknown'}</dd></div>
                <div><dt>Correction</dt><dd>{item.claim.supersedes_claim_id ? `Supersedes ${item.claim.supersedes_claim_id}` : 'Original assertion'}</dd></div>
              </dl>
              {source?.reference && <a href={source.reference} target="_blank" rel="noreferrer">Open source reference ↗</a>}
            </article>
          );
        })}
      </div>
    </div>
  );
}

function Conflicts({ run, onOpenClaim }: { run: ProjectIntelligenceRun; onOpenClaim: (claimId: string) => void }) {
  const { conflicts, unresolved_questions: questions } = run.result;
  return (
    <div className="intelligence-tab-body intelligence-issues">
      <section>
        <h2>Conflicts</h2>
        <p>Incompatible active assertions remain visible until an explicit correction resolves them.</p>
        {conflicts.length ? conflicts.map((conflict) => (
          <article key={conflict.id} className="conflict-card">
            <AlertTriangle size={18} />
            <div>
              <h3>{humanize(conflict.predicate)}</h3>
              {conflict.values.map((value) => (
                <p key={value.value}><strong>{humanize(value.value)}</strong><span className="intelligence-references">{value.claim_ids.map((claimId) => <button key={claimId} onClick={() => onOpenClaim(claimId)}>{claimId}</button>)}</span></p>
              ))}
            </div>
          </article>
        )) : <p className="quiet-card">No incompatible active claims in this run.</p>}
      </section>
      <section>
        <h2>Unresolved questions</h2>
        {questions.length ? questions.map((question) => (
          <article className="question-card" key={question.id}>
            <ArrowRight size={17} />
            <div><h3>{question.text}</h3><References references={question.references} onOpen={onOpenClaim} /></div>
          </article>
        )) : <p className="quiet-card">No unresolved evidence questions in this run.</p>}
      </section>
    </div>
  );
}

type ProjectIntelligenceWorkspaceProps = {
  enabled: boolean;
  selectedSubjectId: string | null;
  selectedRunId: string | null;
  section: OperatingDossierSection;
  onSubjectChange: (
    id: string | null,
    method: 'push' | 'replace',
  ) => void;
  onRunChange: (id: string | null, method: 'push' | 'replace') => void;
  onSectionChange: (section: OperatingDossierSection) => void;
  dossierOpen: boolean;
  locationLabel: string;
  onCollapse: () => void;
  onOpenLayers: () => void;
  closeButtonRef?: Ref<HTMLButtonElement>;
};

export default function ProjectIntelligenceWorkspace({
  enabled,
  selectedSubjectId,
  selectedRunId,
  section,
  onSubjectChange,
  onRunChange,
  onSectionChange,
  dossierOpen,
  locationLabel,
  onCollapse,
  onOpenLayers,
  closeButtonRef,
}: ProjectIntelligenceWorkspaceProps) {
  const [focusedClaimId, setFocusedClaimId] = useState<string | null>(null);
  const state = useProjectIntelligenceState(enabled, {
    selectedSubjectId,
    selectedRunId,
    onSubjectChange,
    onRunChange,
  });
  if (!enabled) return null;
  const latestRun = state.runs[0] || null;
  const viewingHistorical = !!(state.selectedRunId && latestRun && state.selectedRunId !== latestRun.id);
  const openClaim = (claimId: string) => {
    setFocusedClaimId(claimId);
    onSectionChange('evidence');
    requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-project-claim="${CSS.escape(claimId)}"]`)?.focus());
  };
  return (
    <EntityDossier className="project-intelligence-workspace" open={dossierOpen} ariaLabel="Project Subject intelligence dossier" entityKind="PROJECT SUBJECT"
      title={state.selectedSubject?.name || 'Project intelligence'} location={locationLabel}
      artifact={state.run ? `${state.run.result.model_version} · ${state.run.evidence_binding.bundles.length} evidence bundles` : 'No intelligence run selected'}
      evidenceAsOf={state.run ? `Evidence as of ${formatEvidenceTime(state.run.evidence_binding.evidence_as_of)}` : undefined}
      historyState={viewingHistorical && state.run ? { label: `Run created ${formatEvidenceTime(state.run.created)}`, onReturnLatest: () => state.setSelectedRunId(latestRun!.id) } : undefined}
      closeButtonRef={closeButtonRef} onCollapse={onCollapse} onOpenLayers={onOpenLayers}>
      {state.error && <div className="alert error" role="alert">{state.error}<button onClick={state.retry}><RefreshCw size={14} /> Retry</button></div>}
        <main className="intelligence-content">
          {state.loading && !state.run ? <WorkspaceLoading /> : !state.selectedSubject ? (
            <WorkspaceState
              kind="empty"
              title={state.subjects.length ? 'Select a Project Subject' : 'No Project Subjects'}
              description={state.subjects.length
                ? 'Choose an authorized Project Subject to inspect its immutable intelligence history.'
                : 'Project Subjects are created through the authenticated evidence workflow. This interface is deliberately read-only.'}
            />
          ) : !state.runs.length ? (
            <WorkspaceState kind="empty" title="No intelligence runs" description="No immutable reasoning run has been created for this Project Subject." />
          ) : state.run ? (
            <>
              <Tabs
                value={section}
                onValueChange={(value) =>
                  onSectionChange(value as OperatingDossierSection)
                }
              >
                <TabsList className="intelligence-tabs" aria-label="Project intelligence sections">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="evidence">Evidence</TabsTrigger>
                  <TabsTrigger value="issues">Conflicts &amp; unknowns</TabsTrigger>
                  <TabsTrigger value="history">History</TabsTrigger>
                </TabsList>
                <TabsContent value="overview"><Overview run={state.run} onOpenClaim={openClaim} /></TabsContent>
                <TabsContent value="evidence"><Evidence run={state.run} focusedClaimId={focusedClaimId} /></TabsContent>
                <TabsContent value="issues"><Conflicts run={state.run} onOpenClaim={openClaim} /></TabsContent>
                <TabsContent value="history">
                  <div className="intelligence-tab-body">
                    <div className="intelligence-distinction"><span>IMMUTABLE RUN HISTORY</span><p>Selecting an earlier run changes the entire evidence and conclusion view. It never rewrites that run.</p></div>
                    <div className="run-history">{state.runs.map((item) => (
                      <button key={item.id} aria-pressed={item.id === state.selectedRunId} onClick={() => state.setSelectedRunId(item.id)}>
                        <span><strong>{formatEvidenceTime(item.created)}</strong><small>Evidence as of {formatEvidenceTime(item.evidence_as_of)} · {item.evidence_bundle_ids.length} bundles</small></span>
                        <code>{item.id.slice(-10)}</code>
                      </button>
                    ))}</div>
                  </div>
                </TabsContent>
              </Tabs>
            </>
          ) : null}
        </main>
    </EntityDossier>
  );
}
