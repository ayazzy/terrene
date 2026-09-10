export type EvidenceRefs = {
  observation_ids: string[];
  gap_ids: string[];
  object_ids: string[];
  relationship_ids: string[];
  source_feature_reference_ids: string[];
  source_reference_ids: string[];
  raw_reference_ids: string[];
  capability_ids: string[];
};
export type ContextItem = { id: string; label: string; text: string; references: EvidenceRefs };
export type ScreeningFact = {
  id: string;
  definition_id: string;
  label: string;
  dimensions: Record<string, unknown>;
  value: { kind: 'number' | 'category' | 'boolean'; value: number | string | boolean } |
    { kind: 'distribution'; entries: { category: string; value: number }[] };
  unit: string;
  availability: 'available' | 'partial';
  known_zero: boolean;
  support: { coverage_status: string; coverage_basis: string; thematic_completeness: string };
  limitations: string;
  references: EvidenceRefs;
};
export type ScreeningGap = {
  id: string; definition_id: string | null; legacy_variable: string | null;
  state: string; reason_code: string; reason: string;
  source_reference_ids: string[]; raw_reference_ids: string[];
};
export type ReferenceRecord = { id: string; [key: string]: unknown };
export type ScreeningResult = {
  module_id: 'site_screening_context';
  model_version: 'site_screening_context_v1';
  input_binding_version: 'screening_context_binding_v1';
  site_id: string; boundary_version: number; boundary_geometry_fingerprint: string;
  evidence_snapshot_id: string; evidence_content_hash: string; evidence_as_of: string;
  groups: { id: string; label: string; facts: ScreeningFact[]; gaps: ScreeningGap[] }[];
  unconnected_capabilities: { legacy_variable: string; disposition: string; note: string }[];
  mapped_zero_qualifications: ContextItem[]; cross_source_contexts: ContextItem[];
  review_questions: ContextItem[]; limitations: string[];
  sources: (ReferenceRecord & { dataset: string; source_version: string })[];
  raw_references: (ReferenceRecord & { legacy_raw_id: string })[];
  objects: ReferenceRecord[]; relationships: ReferenceRecord[]; source_features: ReferenceRecord[];
};
export type ScreeningRun = {
  id: string; content_hash: string; site_id: string; boundary_version: number;
  evidence_snapshot_id: string; result: ScreeningResult;
};
export type ScreeningAssessment = { id: string; site_id: string; version: number; state: string };
export type ScreeningContextTarget = Pick<ScreeningAssessment, 'id' | 'site_id' | 'version'>;
export type ScreeningContextReadState =
  | { state: 'absent'; run: null; error: '' }
  | { state: 'available'; run: ScreeningRun; error: '' }
  | { state: 'unsupported' | 'unauthorized' | 'failed'; run: null; error: string };

export class ScreeningContextRequestError extends Error {
  readonly status?: number;
  readonly kind: 'http' | 'network' | 'timeout';
  constructor(message: string, status?: number, kind: 'http' | 'network' | 'timeout' = 'http') {
    super(message);
    this.name = 'ScreeningContextRequestError';
    this.status = status;
    this.kind = kind;
  }
}
export const SCREENING_CONTEXT_TIMEOUT_MS = 15_000;
export function screeningAssessmentKey(assessment: ScreeningContextTarget) {
  return `${assessment.id}:${assessment.site_id}:${assessment.version}`;
}
export function contextPath(assessmentId: string) {
  return '/api/assessments/' + encodeURIComponent(assessmentId) + '/screening-context';
}
export function contextHeaders(): Record<string, string> {
  const token = sessionStorage.getItem('crc-token');
  return token ? { Authorization: 'Bearer ' + token } : {};
}
export async function contextResponse(response: Response) {
  if (!response.ok) {
    const error: unknown = await response.json().catch(() => null);
    const detail = error && typeof error === 'object' && 'detail' in error ? error.detail : null;
    throw new ScreeningContextRequestError(
      typeof detail === 'string' ? detail : `Screening context request failed (${response.status})`,
      response.status,
    );
  }
  return response;
}
export async function requestScreeningContext(
  assessment: ScreeningContextTarget, method: 'GET' | 'POST', signal?: AbortSignal,
  timeoutMs = SCREENING_CONTEXT_TIMEOUT_MS,
): Promise<ScreeningRun | null> {
  const request = new AbortController();
  let timedOut = false;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let cancel: (() => void) | undefined;
  const operation = (async () => {
    const response = await contextResponse(await fetch(contextPath(assessment.id), {
      method, headers: contextHeaders(), signal: request.signal, cache: 'no-store',
    }));
    const run: ScreeningRun | null = await response.json();
    if (run && (run.site_id !== assessment.site_id || run.boundary_version !== assessment.version ||
        run.result.site_id !== assessment.site_id || run.result.boundary_version !== assessment.version ||
        run.result.evidence_snapshot_id !== run.evidence_snapshot_id ||
        run.result.module_id !== 'site_screening_context')) {
      throw new Error('Stored context does not match the selected assessment boundary.');
    }
    if (method === 'POST' && !run) throw new Error('No persisted screening context was returned.');
    return run;
  })();
  const boundaries: Promise<ScreeningRun | null>[] = [operation];
  if (timeoutMs > 0) boundaries.push(new Promise((_, reject) => {
    timeout = setTimeout(() => {
      timedOut = true;
      reject(new ScreeningContextRequestError(
        'The saved context check took too long. Check the connection and retry.', undefined, 'timeout',
      ));
      request.abort();
    }, timeoutMs);
  }));
  if (signal) boundaries.push(new Promise((_, reject) => {
    cancel = () => {
      request.abort();
      reject(signal.reason instanceof Error ? signal.reason :
        new DOMException('The request was cancelled.', 'AbortError'));
    };
    if (signal.aborted) cancel();
    else signal.addEventListener('abort', cancel!, { once: true });
  }));
  try {
    return await Promise.race(boundaries);
  } catch (cause) {
    if (cause instanceof ScreeningContextRequestError || signal?.aborted) throw cause;
    if (timedOut) throw new ScreeningContextRequestError(
      'The saved context check took too long. Check the connection and retry.', undefined, 'timeout',
    );
    throw new ScreeningContextRequestError(
      cause instanceof Error ? cause.message : 'The screening context request failed.',
      undefined, 'network',
    );
  } finally {
    if (timeout) clearTimeout(timeout);
    if (signal && cancel) signal.removeEventListener('abort', cancel);
  }
}
export async function readScreeningContext(
  assessment: ScreeningContextTarget, signal?: AbortSignal, timeoutMs = SCREENING_CONTEXT_TIMEOUT_MS,
): Promise<ScreeningContextReadState> {
  try {
    const run = await requestScreeningContext(assessment, 'GET', signal, timeoutMs);
    return run ? { state: 'available', run, error: '' } : { state: 'absent', run: null, error: '' };
  } catch (cause) {
    if (signal?.aborted) throw cause;
    const error = cause instanceof Error ? cause.message : 'The screening context request failed.';
    const status = cause instanceof ScreeningContextRequestError ? cause.status : undefined;
    if (status === 401 || status === 403) return { state: 'unauthorized', run: null, error };
    if (status === 409) return { state: 'unsupported', run: null, error };
    return { state: 'failed', run: null, error };
  }
}
export function screeningValue(fact: ScreeningFact): string {
  const value = fact.value;
  if (value.kind === 'distribution') {
    return value.entries.map(e => `${e.category}: ${(e.value * 100).toLocaleString('en-GB', { maximumFractionDigits: 2 })}%`).join(' · ');
  }
  if (typeof value.value === 'boolean') return value.value ? 'Yes' : 'No';
  if (typeof value.value === 'string') return value.value.replaceAll('_', ' ');
  const fraction = fact.unit === 'fraction';
  return (value.value * (fraction ? 100 : 1)).toLocaleString('en-GB', { maximumFractionDigits: 3 }) +
    (fraction ? '%' : fact.unit === 'degree' ? '°' : ' ' + fact.unit);
}
