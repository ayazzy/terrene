# Sprint 001 — Versioned infrastructure design proposals

## Approved outcome

Create the minimal backend contract for one infrastructure Project linked to an
existing Site and an explicitly pinned committed Evidence Snapshot, with named
Alternatives and independently retrievable immutable Design Revisions. No
environmental consequence calculation or frontend work is included.

## Technical decisions

- Project, Alternative, Revision and Evidence baseline are separate identities.
- A Project supports `solar` in v1 and copies safe snapshot content/schema/
  registry and boundary identity. Creation integrity-loads the snapshot and
  verifies the exact private historical boundary object; “latest” is never used.
- A revision stores the exact accepted WGS84 FeatureCollection, stable feature
  IDs, roles/labels, bounded source provenance, baseline identity, parent,
  timestamps and deterministic geometry/content fingerprints.
- Polygonal proposal geometry may exceed the Site boundary and is never clipped;
  `extends_beyond_baseline` reports that condition.
- The submitted parent must equal the Alternative head. A stale parent conflicts.
  A scoped idempotency key reuses the same immutable revision only for the exact
  same request and conflicts if its payload changes.
- Proposed geometry is not stored as Terrene Earth evidence and does not reuse
  assessments or ModuleRuns.

## Delegation

The engineering lead assigned implementation to one dedicated implementation
worker in the shared feature branch. A separate lead-assigned reviewer inspects
the integrated change and verification; any resulting finding is resolved by the
lead before final sprint sign-off.

## Implemented

- Additive Project, Alternative and Design Revision tables, indexes, PostgreSQL
  RLS/privilege migration handling and organisation-scoped persistence services.
- Authenticated create/list/read API operations for projects, alternatives and
  exact historical revisions.
- GeoJSON validation for finite 2D WGS84 Polygon/MultiPolygon rings, supported
  roles, labels, unique IDs, valid topology and payload/feature/position limits.
- Immutable revision integrity checks, retry-key conflict semantics, optimistic
  head checks and exact historical-boundary containment reporting.

## Reproducible API flow

With authenticated organisation context and existing `site_id` plus committed
`evidence_snapshot_id`:

1. `POST /api/projects` with name, `solar`, Site and snapshot IDs.
2. `POST /api/projects/{project_id}/alternatives` for `Option A` and `Option B`.
3. `POST /api/alternatives/{option_a_id}/revisions` with parent `null`, an
   idempotency key and a FeatureCollection.
4. Create Option B revision 1 in the same way.
5. Create Option A revision 2 with Option A revision 1 as `parent_revision_id`.
6. Retrieve exact records through `GET /api/design-revisions/{revision_id}` and
   ordered history through `GET /api/alternatives/{alternative_id}/revisions`.

## Verification

`tests/test_design_proposals.py` exercises the full flow, database/engine
reload, unchanged revision 1, fixed baseline after a newer snapshot, exact retry,
changed retry conflict, stale edit, invalid/duplicate geometry, cross-organisation
links, historical-boundary integrity and valid outside-boundary geometry. Lead
review fixes additionally cover a missing snapshot manifest, contradictory copied
baseline, corrupt lineage head, malformed stored boundary and oversized integer
coordinates.

Implementation-worker results: focused Project/Alternative/Revision suite
`11 passed`; complete Python/SQLite suite `194 passed`, with the existing 13
dependency warnings; complete PostgreSQL/PostGIS suite `194 passed`, with 85
dependency/SQLAlchemy inspection warnings. The v6 migration completed against
the disposable PostgreSQL database.
Independent review found one blocking baseline-integrity gap and two malformed-
input error paths. The engineering lead resolved them before sign-off by
revalidating the committed snapshot and copied baseline before every new append,
integrity-checking the stored head/parent, and returning safe 4xx errors for the
malformed cases. The reviewer also confirmed organisation scoping, safe response
fields, outside-boundary semantics and separation from Earth/ModuleRuns.

Final lead verification after the review fixes: focused proposal suite
`14 passed`; complete SQLite suite `197 passed` with 13 warnings; complete
PostgreSQL/PostGIS suite `197 passed` with 88 warnings; additive migration v6,
Python compilation and `git diff --check` passed. Warnings are the existing
dependency deprecations and PostgreSQL geometry-reflection advisory.

## Limitations and unresolved review findings

There is no frontend, CAD/PDF/centreline ingestion, geometry editing, impact or
intersection calculation, alternative comparison, solar layout, scoring,
simulation, workflow scheduling or construction-grade validation. The initial
roles and `solar` type are intentionally narrow. PostgreSQL/PostGIS verification
depends on an available disposable test database. No scientific
validation is claimed. No unresolved blocking review finding remains. A committed
stress test for truly simultaneous PostgreSQL retry/stale writers remains a
verification limitation; database locking and uniqueness were exercised by the
implementation worker, including PostgreSQL, and the reviewer separately forced
simultaneous identical SQLite retries.

## Git

Branch: `feat/versioned-design-proposals`.

- `3339cc4` — `feat: add versioned infrastructure design proposals`
- `b03a8de` — `docs: record design proposal sprint`
- Sprint-closing lead commit — `fix: verify proposal baselines before revision append`
