'use client';
import { AlertTriangle, ArrowRight, Clock3, FileText, RefreshCw } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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

function StatePill({ state }: { state: EvidenceState }) {
  return <span className={'intelligence-state state-' + state}>{evidenceStateLabel(state)}</span>;
}

function References({ references }: { references: Array<{ claim_id: string }> }) {
  return references.length ? (
    <span className="intelligence-references">
      {references.map((reference) => reference.claim_id).join(' · ')}
    </span>
  ) : (
    <span className="intelligence-references">No supporting claim</span>
  );
}

function Overview({ run }: { run: ProjectIntelligenceRun }) {
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
          <References references={result.reported_stage.references} />
        </article>
        <article>
          <small>Planning status</small>
          <h3>{result.planning_status.values.map(humanize).join(' · ') || 'Not established'}</h3>
          <StatePill state={result.planning_status.evidence_state} />
          <References references={result.planning_status.references} />
        </article>
        <article>
          <small>Construction status</small>
          <h3>{result.construction_status.values.map(humanize).join(' · ') || 'Not established'}</h3>
          <StatePill state={result.construction_status.evidence_state} />
          <References references={result.construction_status.references} />
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
          <References references={timing.references} />
        </article>
      </div>
      <section className="intelligence-limitations">
        <h3>Limits of this result</h3>
        <ul>{result.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
      </section>
    </div>
  );
}

function Evidence({ run }: { run: ProjectIntelligenceRun }) {
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
            <article key={item.claim.id} className={active.has(item.claim.id) ? '' : 'is-superseded'}>
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

function Conflicts({ run }: { run: ProjectIntelligenceRun }) {
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
                <p key={value.value}><strong>{humanize(value.value)}</strong><span>{value.claim_ids.join(' · ')}</span></p>
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
            <div><h3>{question.text}</h3><References references={question.references} /></div>
          </article>
        )) : <p className="quiet-card">No unresolved evidence questions in this run.</p>}
      </section>
    </div>
  );
}

export default function ProjectIntelligenceWorkspace({ enabled }: { enabled: boolean }) {
  const state = useProjectIntelligenceState(enabled);
  if (!enabled) return null;
  return (
    <section className="project-intelligence-workspace" aria-label="Project intelligence workspace">
      <div className="heading intelligence-heading">
        <div>
          <p className="eyebrow">PROJECT INTELLIGENCE</p>
          <h1>Investigate reported project state</h1>
          <p>Exact source evidence → immutable binding → deterministic assessment.</p>
        </div>
        <div className="intelligence-as-of">
          <Clock3 size={16} />
          {state.run ? `Evidence as of ${formatEvidenceTime(state.run.evidence_binding.evidence_as_of)}` : 'No run selected'}
        </div>
      </div>
      {state.error && <div className="alert error" role="alert">{state.error}<button onClick={state.retry}><RefreshCw size={14} /> Retry</button></div>}
      <div className="intelligence-layout">
        <aside className="subject-list" aria-label="Project Subjects">
          <div className="subject-list-heading"><span>Project Subjects</span><b>{state.subjects.length}</b></div>
          {state.subjects.map((subject) => (
            <button key={subject.id} aria-pressed={subject.id === state.selectedSubjectId}
              onClick={() => state.setSelectedSubjectId(subject.id)}>
              <FileText size={17} />
              <span><strong>{subject.name}</strong><small>{humanize(subject.project_type)}{subject.site_id ? ' · Site linked' : ' · No Site required'}</small></span>
            </button>
          ))}
        </aside>
        <main className="intelligence-content">
          {state.loading && !state.run ? <WorkspaceLoading /> : !state.selectedSubject ? (
            <WorkspaceState kind="empty" title="No Project Subjects" description="Project Subjects are created through the authenticated evidence workflow. This interface is deliberately read-only." />
          ) : !state.runs.length ? (
            <WorkspaceState kind="empty" title="No intelligence runs" description="No immutable reasoning run has been created for this Project Subject." />
          ) : state.run ? (
            <>
              <div className="intelligence-titlebar">
                <div><p className="eyebrow">MONITORED REAL-WORLD PROJECT</p><h2>{state.selectedSubject.name}</h2><p>{humanize(state.selectedSubject.project_type)} · {state.run.evidence_binding.bundles.length} bound evidence bundles</p></div>
                <code>{state.run.result.model_version}</code>
              </div>
              <Tabs defaultValue="overview">
                <TabsList className="intelligence-tabs" aria-label="Project intelligence sections">
                  <TabsTrigger value="overview">Overview</TabsTrigger>
                  <TabsTrigger value="evidence">Evidence</TabsTrigger>
                  <TabsTrigger value="issues">Conflicts &amp; unknowns</TabsTrigger>
                  <TabsTrigger value="history">History</TabsTrigger>
                </TabsList>
                <TabsContent value="overview"><Overview run={state.run} /></TabsContent>
                <TabsContent value="evidence"><Evidence run={state.run} /></TabsContent>
                <TabsContent value="issues"><Conflicts run={state.run} /></TabsContent>
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
      </div>
    </section>
  );
}
