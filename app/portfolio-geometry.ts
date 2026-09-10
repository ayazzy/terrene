import type { Geometry, Position } from 'geojson';

export type SavedMapSite = {
  id: string;
  name: string;
  status: string;
  version: number;
  geometry: Geometry | null;
  assessment?: {
    version?: number;
    result?: { area_ha?: number } | null;
  } | null;
};

// All positions come from the current saved boundary, never assessment geometry.
export function geometryPositions(geometry: Geometry | null): Position[] {
  if (!geometry) return [];
  if (geometry.type === 'GeometryCollection')
    return geometry.geometries.flatMap(geometryPositions);
  const positions: Position[] = [];
  function walk(value: unknown): void {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === 'number') {
      if (
        Number.isFinite(value[0]) &&
        Number.isFinite(value[1]) &&
        Math.abs(value[0]) <= 180 &&
        Math.abs(value[1]) <= 90
      )
        positions.push(value as Position);
    } else value.forEach(walk);
  }
  walk(geometry.coordinates);
  return positions;
}

export function portfolioBounds(
  sites: SavedMapSite[],
): [number, number, number, number] | null {
  const points = sites.flatMap((site) => geometryPositions(site.geometry));
  if (!points.length) return null;
  return points.reduce<[number, number, number, number]>(
    (b, p) => [
      Math.min(b[0], p[0]),
      Math.min(b[1], p[1]),
      Math.max(b[2], p[0]),
      Math.max(b[3], p[1]),
    ],
    [Infinity, Infinity, -Infinity, -Infinity],
  );
}

export function projectedBoundary(
  geometry: Geometry | null,
  project: (position: Position) => { x: number; y: number },
): string {
  if (!geometry) return '';
  const ring = (positions: Position[], close = true) =>
    positions
      .map((p, i) => {
        const q = project(p);
        return `${i ? 'L' : 'M'}${q.x.toFixed(2)},${q.y.toFixed(2)}`;
      })
      .join(' ') + (close ? ' Z' : '');
  switch (geometry.type) {
    case 'Polygon':
      return geometry.coordinates.map((r) => ring(r)).join(' ');
    case 'MultiPolygon':
      return geometry.coordinates
        .flatMap((p) => p.map((r) => ring(r)))
        .join(' ');
    case 'LineString':
      return ring(geometry.coordinates, false);
    case 'MultiLineString':
      return geometry.coordinates.map((r) => ring(r, false)).join(' ');
    case 'GeometryCollection':
      return geometry.geometries
        .map((g) => projectedBoundary(g, project))
        .join(' ');
    default:
      return '';
  }
}
