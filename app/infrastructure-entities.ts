import type { Geometry } from 'geojson';
import type {
  ProjectIntelligenceRunSummary,
  ProjectSubject,
} from './project-intelligence';

export type InfrastructureSite = {
  id: string;
  name: string;
  status: string;
  version: number;
  geometry: Geometry | null;
  assessment?: { state?: string; version?: number } | null;
};

export type InfrastructureEntity =
  | {
      kind: 'site';
      id: string;
      name: string;
      site: InfrastructureSite;
      geometry: Geometry | null;
      evidenceState: string;
      locationState: 'saved_boundary' | 'boundary_unavailable';
    }
  | {
      kind: 'project_subject';
      id: string;
      name: string;
      subject: ProjectSubject;
      geometry: Geometry | null;
      linkedSite: InfrastructureSite | null;
      evidenceState: string;
      locationState: 'site_linked' | 'unlocated' | 'linked_site_unavailable';
    };

export type ProjectRunIndex = Readonly<
  Record<string, readonly ProjectIntelligenceRunSummary[]>
>;

function siteEvidenceState(site: InfrastructureSite) {
  const state = site.assessment?.state;
  if (state === 'completed') return 'Assessment available';
  if (state === 'failed') return 'Assessment failed';
  if (state === 'queued' || state === 'running') return `Assessment ${state}`;
  return 'No saved assessment';
}

export function projectInfrastructureEntities(
  sites: readonly InfrastructureSite[],
  subjects: readonly ProjectSubject[],
  runs: ProjectRunIndex = {},
): InfrastructureEntity[] {
  const sitesById = new Map(sites.map((site) => [site.id, site]));
  const siteEntities: InfrastructureEntity[] = sites.map((site) => ({
    kind: 'site',
    id: site.id,
    name: site.name,
    site,
    geometry: site.geometry,
    evidenceState: siteEvidenceState(site),
    locationState: site.geometry ? 'saved_boundary' : 'boundary_unavailable',
  }));
  const projectEntities: InfrastructureEntity[] = subjects.map((subject) => {
    const linkedSite = subject.site_id
      ? sitesById.get(subject.site_id) || null
      : null;
    return {
      kind: 'project_subject',
      id: subject.id,
      name: subject.name,
      subject,
      linkedSite,
      geometry: linkedSite?.geometry || null,
      evidenceState: runs[subject.id]?.length
        ? `${runs[subject.id].length} intelligence run${runs[subject.id].length === 1 ? '' : 's'}`
        : 'No intelligence run',
      locationState: !subject.site_id
        ? 'unlocated'
        : linkedSite?.geometry
          ? 'site_linked'
          : 'linked_site_unavailable',
    };
  });
  return [...siteEntities, ...projectEntities];
}

export function entityKey(entity: Pick<InfrastructureEntity, 'kind' | 'id'>) {
  return `${entity.kind}:${entity.id}`;
}

export function infrastructureEntityLabel(entity: InfrastructureEntity) {
  if (entity.kind === 'site')
    return entity.locationState === 'saved_boundary'
      ? `Site · boundary v${entity.site.version}`
      : 'Site · boundary unavailable';
  if (entity.locationState === 'site_linked')
    return `Project Subject · linked to ${entity.linkedSite?.name}`;
  if (entity.locationState === 'linked_site_unavailable')
    return 'Project Subject · linked Site unavailable';
  return 'Project Subject · No verified geography';
}

export function searchableInfrastructureEntities(
  entities: readonly InfrastructureEntity[],
  query: string,
  limit = 8,
) {
  const normalized = query.trim().toLocaleLowerCase('en-GB');
  if (!normalized) return [];
  return entities
    .filter((entity) =>
      `${entity.name} ${infrastructureEntityLabel(entity)} ${entity.evidenceState}`
        .toLocaleLowerCase('en-GB')
        .includes(normalized),
    )
    .slice(0, limit);
}

// A display anchor is derived only from the exact linked Site envelope. It is
// not a claimed Project location and is never used for unlocated subjects.
export function linkedSiteDisplayAnchor(geometry: Geometry | null) {
  const positions: number[][] = [];
  if (geometry) {
    const walk = (value: unknown): void => {
      if (!Array.isArray(value)) return;
      if (typeof value[0] === 'number') {
        if (
          Number.isFinite(value[0]) &&
          Number.isFinite(value[1]) &&
          Math.abs(value[0]) <= 180 &&
          Math.abs(value[1]) <= 90
        )
          positions.push(value as number[]);
      } else value.forEach(walk);
    };
    const walkGeometry = (item: Geometry): void => {
      if (item.type === 'GeometryCollection')
        item.geometries.forEach(walkGeometry);
      else if ('coordinates' in item) walk(item.coordinates);
    };
    walkGeometry(geometry);
  }
  if (!positions.length) return null;
  const bounds = positions.reduce(
    (value, position) => ({
      west: Math.min(value.west, position[0]),
      south: Math.min(value.south, position[1]),
      east: Math.max(value.east, position[0]),
      north: Math.max(value.north, position[1]),
    }),
    { west: Infinity, south: Infinity, east: -Infinity, north: -Infinity },
  );
  return [
    (bounds.west + bounds.east) / 2,
    (bounds.south + bounds.north) / 2,
  ] as [number, number];
}
