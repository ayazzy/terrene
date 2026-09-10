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
    throw new Error(typeof detail === 'string' ? detail : `Screening context request failed (${response.status})`);
  }
  return response;
}
export async function requestScreeningContext(assessment: ScreeningAssessment, method: 'GET' | 'POST', signal?: AbortSignal): Promise<ScreeningRun | null> {
  const response = await contextResponse(await fetch(contextPath(assessment.id), {
    method, headers: contextHeaders(), signal, cache: 'no-store',
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
