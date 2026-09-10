# Land Evidence Snapshot persistence

Implementation date: 8 September 2026. Scope: the second bounded Land Intelligence Foundation stage.

This stage makes a validated `land_evidence_v1` projection independently identifiable and persistable alongside its legacy assessment. It does not change acquisition, EarthState, wetland features/scoring, assessment results, reports, API routes or the UI.

## Persistence model

The implementation adds four small relational tables and keeps the canonical payload in existing private object storage:

| Table | Purpose |
|---|---|
| `land_evidence_snapshots` | Organisation, site, immutable boundary version/hash, schema/registry version, semantic content hash, manifest byte hash/key and first commit time |
| `land_evidence_snapshot_members` | Ordered membership for definitions, observations, selections, gaps, capabilities, diagnostics, source references and raw references |
| `land_evidence_snapshot_links` | Ordered observation parent/source/raw edges, source-to-raw edges, gap source/raw edges and selection-to-observation edges |
| `land_evidence_snapshot_origins` | Append-only association to each saved legacy assessment from which identical evidence was projected, with the original assessment-result fingerprint |

Observation values and full provenance are not split prematurely across many future-domain tables. The complete validated `LandEvidenceProjection` is stored as canonical JSON. Relational rows provide discovery and reference resolution without becoming a second representation of the value.

Schema migration 3 creates these tables. PostgreSQL migration also enables RLS on the organisation-bearing snapshot/origin tables and revokes browser roles from every new table. No public snapshot API is introduced.

## Snapshot identity and immutability

There are two hashes with deliberately different jobs:

- `content_hash` identifies reusable core evidence: `land_evidence_v1`, its registry, stable site ID, boundary version/reference/geometry hash, geography, evidence-as-of, definitions, source/raw references, observations at original precision, support, lineage, selections, gaps, capabilities and diagnostics.
- `manifest_sha256` identifies the exact stored JSON bytes, including the legacy bridge metadata retained by the complete projection.

The snapshot ID is deterministic from organisation scope, stable site ID, immutable boundary identity, schema/registry and `content_hash`. A database uniqueness constraint on `(org, site_id, boundary_version, schema_version, content_hash)` prevents a second identity for the same content key.

Mutable site names and legacy wetland/module outputs are excluded from core content identity. `project_land_evidence` now scopes its projection/observation IDs from boundary and core evidence inputs rather than the whole assessment presentation or wetland result. The legacy assessment fingerprint, module-output references and wetland-result reference remain inspectable in the full manifest, but no module output receives a core membership row.

If another assessment produces the same core evidence, CRC reuses the existing snapshot and adds an origin association. It never replaces the first committed manifest. A changed boundary version or geometry, source/version, observation value/precision/support, selection, lineage, gap or other core content produces a different hash and snapshot.

Object creation is compare-and-set: local development uses exclusive file creation and hosted R2 uses a conditional `If-None-Match: *` put. An existing key is accepted only when its bytes are identical. No persistence method updates a snapshot, member, link or manifest.

## Legacy bridge

`create_snapshot_from_legacy_assessment(assessment_id, org=...)` performs the bounded bridge:

1. resolves the assessment and site inside one organisation;
2. requires an existing saved result;
3. calls the pure `project_land_evidence(saved_result)` function;
4. validates the projection and checks its site, boundary version and boundary geometry hash against the immutable assessment row;
5. commits the independent snapshot and origin association.

It never updates the assessment or its embedded `environmental_state`. Selected assessments can be bridged explicitly after migration 3:

```bash
.venv/bin/python -m backend.migrate
.venv/bin/python -m scripts.persist_land_evidence --org ORG_ID ASSESSMENT_ID [ASSESSMENT_ID ...]
```

There is intentionally no automatic destructive historical migration. Repeating the command for unchanged evidence resolves the same snapshot and origin row.

## Commit consistency

Publication uses an object-first/database-second protocol:

1. serialize validated projection JSON canonically;
2. write it under content and byte hashes with immutable create semantics;
3. read it back and verify exact bytes plus SHA-256;
4. insert the snapshot, every membership/link and its origin in one database transaction.

A transaction failure therefore leaves at most an unreferenced content-addressed object. It cannot leave a visible snapshot missing some relational memberships. An identical retry verifies and reuses the orphan before committing all database rows. Once a database row exists, every load verifies the manifest byte hash, validates `land_evidence_v1` again and recomputes the semantic content hash.

The SQLite-to-PostgreSQL copy utility verifies and conditionally copies every referenced land-evidence manifest before copying its relational rows. Missing or corrupt manifests stop the copy before snapshot rows are inserted.

## Organisation and private evidence access

Snapshot discovery and loading always query by both snapshot/site and organisation. Manifest keys are organisation-scoped and are resolved only after the database ownership check. The manifest may retain private raw-artifact references, but this stage adds no direct object or raw-evidence endpoint. Existing private-bucket and server-side access rules remain in force.

## Verification

Focused persistence tests cover:

- projection, bridge persistence and exact manifest round-trip for all 12 retained Oxford assessments;
- stable content hashes and idempotent duplicate creation;
- relational observation/gap/capability/source/raw membership and reference edges;
- known zero versus missing evidence after persistence;
- module-output exclusion from core membership;
- legacy assessment hash preservation;
- invalid projection and boundary-support rejection;
- injected membership failure, invisible orphan handling and successful retry;
- compare-and-set manifest immutability;
- wrong-organisation discovery/load denial;
- changed boundary version and changed observation content producing new snapshots;
- reuse of core identity when only site presentation or wetland output changes.

Verification completed on 8 September 2026:

- SQLite Python suite: **125 passed**, with 13 dependency deprecation warnings;
- disposable local PostgreSQL/PostGIS `crc_test` suite after migration 3: **125 passed**, with the same 13 warnings;
- direct PostgreSQL Port Meadow snapshot round-trip: **121 members** and **97 links**, manifest and content hashes verified;
- frontend regression suite: **19 passed**;
- `npx tsc --noEmit`: passed;
- `npm run build`: passed, with the existing large-chunk advisory;
- `npm run lint`: still fails on existing generated UI-component accessibility rules and pre-existing frontend `any`/effect diagnostics; no reported issue is in this backend persistence change.

The R2 conditional-write branch was checked against the installed botocore service model and `IfNoneMatch` is supported. No live hosted R2 credentials were supplied, so an end-to-end hosted object write was not performed.

## Historical parity

Legacy assessments remain authoritative and byte-for-byte unchanged. Wetland continues to consume `assessment.result.environmental_state`; it does not read the new snapshot tables or manifest. No weight, threshold, gate, model signature, acquisition path, report or frontend behavior changed.

## Recommended next bounded iteration

Introduce an explicit versioned wetland input-binding and `ModuleRun` record that reads one committed Evidence Snapshot while proving parity against the unchanged legacy adapter. Keep new environmental datasets, scoring changes, refresh orchestration, UI and decision records out of that iteration.
