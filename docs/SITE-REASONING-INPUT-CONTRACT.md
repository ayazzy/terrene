# Snapshot-bound Site reasoning input contract

Implementation date: 14 September 2026.

## Purpose

New Site reasoning can now start from an explicitly selected, already committed
Evidence Snapshot instead of relying on the legacy assessment endpoint's
implicit latest-dataset lookup. The contract is additive: it exposes the
existing immutable wetland ModuleRun execution path and does not replace,
rewrite or reinterpret legacy assessments.

## Read contract

`GET /api/sites/{site_id}/reasoning-inputs` returns
`site_reasoning_input_catalogue_v1`. The organization-scoped, no-store GET:

- verifies the Site and every returned committed Evidence Snapshot;
- returns each snapshot's exact ID, semantic content hash, schema/registry,
  Site and boundary identity, creation time and evidence-as-of time;
- distinguishes an exact current-boundary match from a historical snapshot by
  both boundary version and geometry fingerprint;
- returns observation, explicit-gap and source counts plus safe source identity,
  release, retrieval, temporal and licence/attribution metadata;
- omits private manifest keys, raw storage references and raw-reference IDs;
- publishes the one currently supported module and a complete exact
  `site_reasoning_run_request_v1` envelope for each snapshot.

The GET creates no snapshot, assessment or ModuleRun. An empty snapshot list is
a valid catalogue state.

## Write contract

`POST /api/sites/{site_id}/reasoning-runs` accepts only a complete
`site_reasoning_run_request_v1` previously published by the catalogue. The
request pins:

- route and body Site identity;
- Evidence Snapshot ID and semantic content hash;
- boundary version and geometry fingerprint;
- module ID/version and input-binding version;
- complete model specification and signature.

Unknown fields are rejected. Before execution, the service resolves the Site
and snapshot within the organization, verifies their relationship and compares
the submitted envelope with a newly derived canonical envelope. A stale or
contradictory field fails closed. The current wetland envelope pins
`environment_version=null` and `refresh_sources=false` because snapshot-bound
execution performs no acquisition and must not vary with deployment settings.

An accepted request applies `wetland_input_binding_v1`, executes the unchanged
`wetland_restoration_v0_1` implementation and creates or reuses its deterministic
immutable ModuleRun. Identical retries return the same run. The source snapshot,
Site, boundary history and legacy assessment remain unchanged.

## Evidence and model semantics

The selected snapshot is the complete evidence input boundary, but only facts
and gaps explicitly mapped by `wetland_input_binding_v1` affect
`wetland_restoration_v0_1`. Priority Habitat, built-world and building-height
records remain retained evidence and do not silently become model variables.
A future semantic change requires a new binding and/or model version.

Historical snapshots remain runnable when their exact saved boundary object is
available and matches the retained fingerprint. `current_boundary=false` is a
presentation fact, not a reason to retarget the snapshot to the latest boundary.

## Error and compatibility behavior

- Missing, unauthorized and cross-Site identities return a non-disclosing 404.
- Structurally invalid requests return 422.
- Stale or contradictory immutable envelopes return 409 and create no run.
- Stored snapshot/run integrity failures return a sanitized 500 and expose no
  private object-store details.
- `POST /api/sites/{site_id}/assessments` remains unchanged as the legacy
  dataset-acquisition assessment path.
- Existing saved assessments, reports, Screening Context routes and map-scene
  responses are unchanged.

## Verification scope

Focused tests cover read-only catalogue behavior, exact and safe response
identity, strict request validation, stale-envelope rejection, Site and
organization isolation, deterministic retry reuse, historical-boundary
execution and sanitized corrupt-snapshot failure. The established wetland
ModuleRun, Screening Context and infrastructure map-scene regressions remain the
compatibility boundary. The complete backend suite passed 197 tests with 63
retained-data skips on both SQLite and disposable PostgreSQL/PostGIS.
