import test from 'node:test';
import assert from 'node:assert/strict';
import {
  geometryPositions,
  portfolioBounds,
  projectedBoundary,
} from '../app/portfolio-geometry.ts';

const polygon = {
  type: 'Polygon',
  coordinates: [
    [
      [-1.4, 51.8],
      [-1.3, 51.8],
      [-1.3, 51.9],
      [-1.4, 51.8],
    ],
    [
      [-1.38, 51.82],
      [-1.35, 51.82],
      [-1.35, 51.84],
      [-1.38, 51.82],
    ],
  ],
};
const project = ([x, y]) => ({ x: x * 100, y: y * 100 });
const saved = (geometry) => ({
  id: 'saved',
  name: 'Saved parcel',
  status: 'Investigate',
  version: 2,
  geometry,
});

test('regional bounds use every current saved component, never historical assessments', () => {
  const multi = {
    type: 'MultiPolygon',
    coordinates: [
      polygon.coordinates,
      [
        [
          [-1.5, 51.7],
          [-1.48, 51.7],
          [-1.48, 51.71],
          [-1.5, 51.7],
        ],
      ],
    ],
  };
  const site = {
    ...saved(multi),
    assessment: { geometry: { type: 'Point', coordinates: [0, 0] } },
  };
  assert.deepEqual(portfolioBounds([site]), [-1.5, 51.7, -1.3, 51.9]);
  assert.deepEqual(geometryPositions(multi)[0], [-1.4, 51.8]);
});
test('projected paths preserve holes and separate multipolygon islands', () => {
  const path = projectedBoundary(polygon, project);
  assert.equal((path.match(/M/g) || []).length, 2);
  assert.equal((path.match(/ Z/g) || []).length, 2);
  assert.match(path, /^M-140.00,5180.00/);
  const multi = {
    type: 'MultiPolygon',
    coordinates: [polygon.coordinates, polygon.coordinates],
  };
  assert.equal(
    (projectedBoundary(multi, project).match(/ Z/g) || []).length,
    4,
  );
});
test('missing or invalid coordinates never manufacture a location', () => {
  assert.equal(portfolioBounds([saved(null)]), null);
  assert.deepEqual(
    geometryPositions({ type: 'Point', coordinates: [NaN, 51] }),
    [],
  );
  assert.deepEqual(
    geometryPositions({ type: 'Point', coordinates: [181, 51] }),
    [],
  );
  assert.equal(projectedBoundary(null, project), '');
});
test('geometry collections retain each valid stored position', () => {
  const geometry = {
    type: 'GeometryCollection',
    geometries: [polygon, { type: 'Point', coordinates: [-1.6, 51.6] }],
  };
  assert.deepEqual(
    portfolioBounds([saved(geometry)]),
    [-1.6, 51.6, -1.3, 51.9],
  );
  assert.equal(
    projectedBoundary(geometry, project),
    projectedBoundary(polygon, project) + ' ',
  );
});
