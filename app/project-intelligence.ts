export type EvidenceState =
  | 'supported'
  | 'conflicting'
  | 'insufficient_evidence';

export type ProjectSubject = {
  id: string;
  org: string;
  name: string;
  project_type: string;
  site_id: string | null;
  content_hash: string;
  created: string;
};

export type EvidenceReference = {
  claim_id: string;
  source_record_id: string;
  source_version: string;
  source_content_hash: string;
  source_record_hash: string;
  exact_passage: string;
  bundle_ids: string[];
};

export type StatusFinding = {
  predicate: 'planning_status' | 'construction_status';
  evidence_state: EvidenceState;
  values: string[];
  unknown_claim_ids: string[];
  references: EvidenceReference[];
};

export type GridTargetFinding = {
  evidence_state: EvidenceState;
  targets: Array<{
    date: string;
    temporal_state: 'future_target' | 'elapsed_unverified';
    references: EvidenceReference[];
  }>;
  unknown_claim_ids: string[];
  references: EvidenceReference[];
};

export type ProjectIntelligenceResult = {
  module_id: 'project_intelligence';
  model_version: 'project_intelligence_v1';
  input_binding_version: 'project_evidence_binding_v1';
  signature: string;
  project_subject_id: string;
  project_subject_content_hash: string;
  evidence_binding_id: string;
  evidence_binding_content_hash: string;
  evidence_as_of: string;
  reported_stage: {
    value: string;
    evidence_state: EvidenceState;
    references: EvidenceReference[];
  };
  planning_status: StatusFinding;
  construction_status: StatusFinding;
  grid_connection_target: GridTargetFinding;
  conflicts: Array<{
    id: string;
    predicate: string;
    values: Array<{
      value: string;
      claim_ids: string[];
      references: EvidenceReference[];
    }>;
  }>;
  unresolved_questions: Array<{
    id: string;
    code: string;
    text: string;
    references: EvidenceReference[];
  }>;
  limitations: string[];
};

export type BoundSource = {
  source: {
    id: string;
    source_version: string;
    publisher: string;
    title: string;
    reference: string;
    published_at: string | null;
    recorded_at: string;
    retained_excerpt: string;
    content_hash: string;
    entry_method: 'human_submitted_structured';
  };
  record_hash: string;
  bundle_ids: string[];
};

export type BoundClaim = {
  claim: {
    id: string;
    project_subject_id: string;
    phase: string | null;
    predicate: string;
    value: string | { state: string; date?: string; reason?: string };
    source_record_id: string;
    locator: { start: number; end: number; exact_passage: string };
    time: { kind: string; effective_or_event_date: string | null };
    supersedes_claim_id: string | null;
    unknown_reason?: string | null;
  };
  claim_hash: string;
  source_record_id: string;
  source_version: string;
  source_content_hash: string;
  source_record_hash: string;
  bundle_ids: string[];
};

export type ProjectIntelligenceRunSummary = {
  id: string;
  org: string;
  project_subject_id: string;
  evidence_binding_id: string;
  evidence_binding_content_hash: string;
  module_id: string;
  module_version: string;
  input_binding_version: string;
  model_signature: string;
  content_hash: string;
  evidence_as_of: string;
  evidence_bundle_ids: string[];
  created: string;
  completed: string;
};

export type ProjectIntelligenceRun = Omit<
  ProjectIntelligenceRunSummary,
  'evidence_as_of' | 'evidence_bundle_ids'
> & {
  evidence_binding: {
    id: string;
    binding_version: 'project_evidence_binding_v1';
    content_hash: string;
    project_subject: Omit<ProjectSubject, 'created'>;
    bundles: Array<{
      id: string;
      content_hash: string;
      manifest_sha256: string;
      schema_version: 'project_evidence_v1';
      claim_ids: string[];
    }>;
    sources: BoundSource[];
    claims: BoundClaim[];
    active_claim_ids: string[];
    superseded_claim_ids: string[];
    evidence_as_of: string;
  };
  model_spec: Record<string, unknown>;
  result: ProjectIntelligenceResult;
};

async function readJson<T>(path: string): Promise<T> {
  const token = sessionStorage.getItem('crc-token');
  const response = await fetch('/api' + path, {
    headers: token ? { Authorization: 'Bearer ' + token } : {},
    cache: 'no-store',
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    throw new Error(
      typeof payload.detail === 'string'
        ? payload.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export function readProjectSubjects() {
  return readJson<ProjectSubject[]>('/project-subjects');
}

export function projectEvidenceSourceKey(sourceId: string, sourceVersion: string) {
  return JSON.stringify([sourceId, sourceVersion]);
}

export async function readProjectIntelligenceRuns(projectSubjectId: string) {
  const runs = await readJson<ProjectIntelligenceRunSummary[]>(
    `/project-subjects/${encodeURIComponent(projectSubjectId)}/intelligence-runs`,
  );
  if (runs.some((run) => run.project_subject_id !== projectSubjectId)) {
    throw new Error('Run history does not match the selected Project Subject.');
  }
  return runs;
}

export async function readProjectIntelligenceRun(runId: string) {
  const run = await readJson<ProjectIntelligenceRun>(
    `/project-intelligence-runs/${encodeURIComponent(runId)}`,
  );
  if (run.id !== runId || run.result.evidence_binding_id !== run.evidence_binding.id) {
    throw new Error('Run detail does not match its immutable evidence envelope.');
  }
  return run;
}

export function humanize(value: string) {
  return value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
}

export function evidenceStateLabel(value: EvidenceState) {
  if (value === 'insufficient_evidence') return 'Insufficient evidence';
  return humanize(value);
}

export function claimValue(value: BoundClaim['claim']['value']) {
  if (typeof value === 'string') return humanize(value);
  if (value.state === 'known' && value.date) return value.date;
  return value.reason ? `Unknown · ${value.reason}` : 'Unknown';
}

export function formatEvidenceTime(value: string) {
  return new Date(value).toLocaleString('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}
