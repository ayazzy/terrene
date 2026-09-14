export type SiteReasoningRunSummary = {
  id: string;
  content_hash: string;
  site_id: string;
  boundary_version: number;
  evidence_snapshot_id: string;
  evidence_content_hash: string;
  evidence_as_of: string;
  current_boundary: boolean;
  module_id: string;
  module_version: string;
  input_binding_version: string;
  model_signature: string;
  result_band: string;
  result_score: number | null;
  data_coverage_available: number | null;
  data_coverage_required: number | null;
  missing_input_count: number;
  review_flag_count: number;
  synthetic: boolean;
  created: string;
  completed: string;
};

export type SiteReasoningRunCatalogue = {
  contract_version: 'site_reasoning_run_catalogue_v1';
  site_id: string;
  current_boundary_version: number;
  current_boundary_geometry_fingerprint: string;
  runs: SiteReasoningRunSummary[];
};

export async function readSiteReasoningRuns(
  siteId: string,
  signal?: AbortSignal,
): Promise<SiteReasoningRunCatalogue> {
  const token = sessionStorage.getItem('crc-token');
  const response = await fetch(`/api/sites/${siteId}/reasoning-runs`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: 'no-store',
    signal,
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
  const catalogue = (await response.json()) as SiteReasoningRunCatalogue;
  if (
    catalogue.contract_version !== 'site_reasoning_run_catalogue_v1' ||
    catalogue.site_id !== siteId ||
    !Array.isArray(catalogue.runs) ||
    catalogue.runs.some((run) => run.site_id !== siteId)
  )
    throw new Error('The reasoning run catalogue does not match this Site.');
  return catalogue;
}
