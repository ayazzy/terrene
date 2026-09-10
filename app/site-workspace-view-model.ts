import type { ScreeningAssessment } from './screening-context.ts';
import type { Geometry } from 'geojson';
import type { Earth, Model } from './nature-panel.tsx';
import type { OverlayFinding } from './site-evidence.ts';

export type WorkspaceResult = {
  area_ha: number;
  completeness: number;
  dataset_count: number;
  findings?: OverlayFinding[];
  wetland_model?: Model;
  environmental_state?: Earth;
  limitations?: string;
};

export type WorkspaceAssessment = ScreeningAssessment & {
  result?: WorkspaceResult;
  geometry: Geometry;
  created: string;
  dataset_ids: string[];
  error?: string;
};

export type WorkspaceSite = {
  id: string;
  version: number;
  assessment?: WorkspaceAssessment | null;
};

export function resolveWorkspaceAssessment(
  site: WorkspaceSite | undefined,
  history: WorkspaceAssessment[],
  selectedAssessmentId: string | null,
) {
  const historical = selectedAssessmentId
    ? history.find(
        (item) => item.id === selectedAssessmentId && item.site_id === site?.id,
      )
    : undefined;
  return historical || site?.assessment || undefined;
}
