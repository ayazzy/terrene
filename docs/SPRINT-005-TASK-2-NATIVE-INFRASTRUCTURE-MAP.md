# Sprint 005 Task 2 — Native infrastructure map

## Outcome

Terrene's primary map now reads one exact committed Evidence Snapshot through
`infrastructure_map_scene_v1` and renders its infrastructure objects as native
MapLibre GeoJSON layers. The map contract is additive and read-only. The
existing `screening_context_map_features_v1` response remains unchanged for
Screening Context consumers.

This iteration improves Terrene's ability to represent and inspect reality: a
map interaction resolves to a persisted object, its source release, its typed
parcel relationships and, for registry-v4 buildings, its independent height
observation or explicit evidence gap.

## Contract and evidence semantics

`GET /api/land-evidence-snapshots/{snapshot_id}/map-scene` authorizes the exact
snapshot by organization, reloads and validates its immutable manifest, checks
the relational snapshot/Site/boundary/content envelope and returns no-store
`infrastructure_map_scene_v1`.

The response includes:

- exact snapshot, Site and historical boundary identity;
- WGS84 presentation geometry with authoritative EPSG:27700 identity retained;
- Buildings, Functional Sites, Railway Tracks and Railway Stations as semantic
  layers with available, mapped-zero, partial, unavailable or unsupported state;
- object type, source/release, retained classification and typed parcel
  relationships with their persisted measurements;
- safe source metadata, evidence time and explicit scene capabilities; and
- per-building height availability, full-precision P50/P90, valid sample count,
  coverage, source references and gap semantics.

Registry v1/v2 snapshots produce explicit unsupported layer states. Registry
v3 produces built-world features with height capability unsupported. Registry
v4 permits an extrusion value only when a linked `BuildingHeightObservation`
contains a valid P90 estimate. No missing or invalid height is defaulted.

## Native map architecture

The persistent primary map uses separate native GeoJSON sources for Sites,
Project Subjects, environmental findings and snapshot infrastructure. Semantic
MapLibre layers own layer order, visibility and styling. Click selection uses
`queryRenderedFeatures`; shared object selection is represented with feature
state. Height-backed buildings have an extrusion layer, while buildings without
height evidence retain a flat dashed outline. The isolated boundary editor
alone keeps temporary SVG drawing geometry.

The existing URL-addressable entity, historical artifact, dossier and layer
state remains authoritative. Site workspace requests for the legacy Screening
Context map contract and the new snapshot scene use independent abort and
latest-request fences, so one response cannot invalidate or replace the other.

## Compatibility and history

No historical assessment, Evidence Snapshot, ModuleRun, wetland result,
registry-v1–v3 manifest or legacy map-feature response is rewritten. The new
GET performs no persistence and exposes no raw object-storage path, native
raster or private payload. Presentation geometry is not treated as a new Earth
fact.

## Verification

- Full backend suite on SQLite: 187 passed, 63 retained-data tests skipped.
- Full backend suite on PostgreSQL/PostGIS: 187 passed, 63 retained-data tests
  skipped.
- New API/contract tests verify organization isolation, no-write GET behavior,
  deterministic Oxford Station v3 replay, 5 Buildings, 2 Functional Sites,
  7 Railway Tracks, 1 Railway Station, WGS84 bounds, manifest-envelope
  integrity, v3 fallback and v4 observation/gap height gating.
- Frontend Node regression suite: 74 passed.
- TypeScript: passed with `npx tsc --noEmit`.
- Focused lint on the new/refined map, scene, inspector and workspace modules:
  passed.
- Production build: passed with the existing large-chunk advisory.

## Known limitation

The normal local development database does not contain a committed Oxford
Evidence Snapshot, and no database or duplicated evidence is committed by this
task. Therefore Oxford Station cannot yet appear in the currently open local
UI. Provisioning an isolated QA database from retained Oxford records belongs
to Sprint 005 Task 4.
