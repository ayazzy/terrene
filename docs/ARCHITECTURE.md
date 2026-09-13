# Terrene architecture

## Status and vocabulary

This document describes the architecture implemented on 10 September 2026 and its intended direction. It does not claim that future layers already exist. Where code still uses `CRC` or `crc`, those names are retained for historical compatibility and reproducibility.

The core concepts are deliberately distinct:

- **Object:** something represented as existing in the world, such as a parcel, building, habitat feature, railway line or station.
- **Relationship:** a connection or spatial relationship between objects, such as overlap, containment, crossing or minimum distance.
- **Observation:** an evidence-backed reusable fact with defined semantics, spatial/temporal support, coverage, source and lineage.
- **Interpretation:** the versioned output of a reasoning module. It may express suitability, constraint, risk or another modelled conclusion; it is not promoted to a reusable fact.
- **Decision:** a human or operational action/state with its own actor, time and evidence context. It is not an observation or model result.

## Implemented system

The web application consists of a React/TypeScript frontend, a FastAPI API and a Python worker. PostgreSQL/PostGIS provides the intended relational/spatial store; SQLite plus Shapely supports local development and isolated tests. Native artifacts, immutable manifests and reports use content-addressed object storage (`data/objects` locally; private R2-compatible storage when hosted).

The frontend calls the API through the server-side route in `app/api/[...path]/route.ts`. MapLibre displays a raster basemap and bounded evidence geometry. The API owns authorization, site/boundary operations, assessment submission, saved evidence and report access. The worker owns deterministic acquisition/processing/model execution under lease and fencing rules.

Existing assessment/job persistence predates the newer Land Evidence projection. It remains authoritative historical implementation and is not rewritten by the additive architecture below.

## Implemented evidence-to-reasoning flow

```text
Terrene Earth
  → immutable Evidence Snapshots
  → versioned module bindings
  → Terrene Reasoning
  → immutable ModuleRuns
```

### Terrene Earth

Today, Terrene Earth is implemented principally by the existing CRC Earth records plus the validated `land_evidence_v1` projection. The projection has versioned definitions and retains boundary identity, observations, gaps, capabilities, source/raw references, selections and lineage.

Registry v3 additionally carries a narrow typed union of OpenMap Local `MappedBuildingObject`, `FunctionalSiteObject`, `RailwayTrackObject` and `RailwayStationObject` records and `ParcelObjectRelationship` records. Priority Habitat evidence retains source-feature relationships and mapped habitat classification. This is intentionally not a universal ontology or graph database.

### Immutable Evidence Snapshots

A saved legacy assessment may be projected into an independently identified snapshot. The canonical validated manifest is stored immutably in private object storage; relational tables index identity, membership, links and origin associations. Semantic content and exact manifest bytes have separate hashes. Reuse is content-addressed, publication is compare-and-set, and a changed boundary/source/observation/selection/gap produces a new identity.

The legacy assessment is never updated by projection. Earlier manifests remain byte-identical when later registry/source evidence is added.

### Versioned module bindings

`wetland_input_binding_v1` validates a committed `land_evidence_v1` snapshot, checks immutable boundary identity and translates selected facts and explicit gaps into the unchanged historical `crc_earth_v0_1` contract. It preserves precision, support, provenance and legacy quality metadata. Binding is explicit so a new evidence registry cannot silently change a historical model input.

### Terrene Reasoning

The historical wetland module is the deterministic `wetland_restoration_v0_1` model. It runs without network access from the bound state and pinned model specification. Its interpretations remain separate from core Evidence Snapshot membership. Priority Habitat and built-world additions do not alter this model unless a future versioned binding/model explicitly adopts them.

`site_screening_context` is an additive non-scoring module, version `site_screening_context_v1`, using `screening_context_binding_v1`. It consumes validated committed `land_evidence_v1` content directly and copies source measurements, support, gaps and provenance into a typed review contract. Declared deterministic rules generate mapped-zero qualifications, source-semantic contexts and human questions. The specification signature pins configuration, rule declarations and result-contract schema; runtime timestamps and mutable team status are outside the semantic result. No network acquisition or free-form model interpretation occurs.

### Immutable ModuleRuns

A ModuleRun records organization, site/boundary, Evidence Snapshot/content hash, module and binding versions, model signature/specification, exact saved result and a deterministic content hash. Repeated identical execution reuses the same identity; contradictory content fails rather than overwrites it.

Screening uses the same ModuleRun table, deterministic identity and immutable persistence primitives, with a narrow module-specific validation dispatch. Its scoped reader also recalculates from committed evidence and rejects contradictions. The existing wetland validation and execution branch is unchanged; no database migration is required.

### Intentional screening application action

`POST /api/assessments/{id}/screening-context` verifies ownership and a completed or terminal partial saved result, reuses its existing snapshot origin (including historical registry versions), or explicitly creates one before executing the module. Ordinary discovery, run reads and export GETs never create snapshots or runs. Multiple existing origins require explicit version selection that v1 does not offer; unsupported historical evidence is reported and preserved.

The Overview panel is keyed to the selected assessment. Stored facts and rule-generated review items remain separate from mutable team status. The self-contained HTML export contains run/snapshot/boundary identities and inspectable evidence, with current team status labelled as operational state at export. Public raw-reference identities and checksums remain visible; private storage locations and asset paths are omitted.

## Existing application records

Sites have mutable presentation fields and point to a current immutable boundary version. Assessments snapshot the boundary, dataset/model configuration and evidence at submission. Dataset releases/features and content-addressed raw artifacts retain source provenance. HTML reports render saved assessment evidence; current team review state is shown separately.

The current review status is operational state, not yet an append-only Decision record. A future decision architecture should add records rather than recast existing status as historical evidence.

## Versioned proposed infrastructure state

Terrene now persists the first narrow proposed-state contract alongside, but not
inside, Terrene Earth:

```text
Site + one explicitly committed Evidence Snapshot
  → Infrastructure Project (`solar` in v1)
  → named Design Alternative
  → immutable Design Revision history
  → future versioned Scenario calculation (not yet implemented)
```

A Project copies the safe identity of one committed Evidence Snapshot and its
exact historical Site boundary: snapshot/content/schema/registry identity,
Site ID, boundary version and boundary geometry fingerprint. Project creation
integrity-loads the private snapshot manifest and verifies the stored historical
boundary object; it never selects “latest”, acquires evidence or triggers an
assessment. Later snapshots therefore do not retarget an existing project.

Each Design Revision retains its Project, Alternative, parent revision and full
baseline identity together with the exact accepted WGS84 FeatureCollection,
submission provenance, geometry/content fingerprints and whether any proposed
geometry extends beyond the pinned boundary. Revisions append at the current
alternative head. An explicit parent provides optimistic concurrency control;
an idempotency key safely resolves identical retries and conflicts on changed
payloads. Proposed footprints are not observations, Earth objects, assessments
or ModuleRuns.

## Intended, not completed

### Terrene Scenario

Scenario will compute consequences or alternative/future state from a pinned Design Revision and Evidence Snapshot. The versioned proposal input now exists, but no scenario binding, evidence-intersection calculation, alternative comparison or impact interpretation is implemented. Drawing either a Site boundary or a proposed footprint is not itself a calculation.

### Terrene Applications

The current UI implements early screening, portfolio navigation and evidence review. Screen, Diligence, Scenario, Monitor, Portfolio, Nature/BNG, Restoration, Field Evidence and infrastructure/renewable workflows are strategic application candidates, not a list of completed products. Customer evidence should determine which vertical workflow is hardened first.

## Architectural constraints

- Facts, interpretations and decisions stay separate.
- Evidence/source scope must remain explicit; known mapped zero is not real-world absence.
- Historical identifiers, hashes, signatures, database structures, snapshots and runs are not renamed for branding.
- Native/licensed/private artifacts remain outside Git and behind organization-aware server access.
- Add new entities, versions and bindings when meaning changes; do not silently mutate historical records.
- Do not optimize the current architecture around 3D visualization.

Detailed implementation references: [Land Intelligence Foundation](LAND-INTELLIGENCE-FOUNDATION.md), [Evidence Snapshot persistence](LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md), [wetland binding and ModuleRuns](WETLAND-SNAPSHOT-MODULE-RUN.md), [Priority Habitats](PRIORITY-HABITATS-EVIDENCE.md), [OpenMap Local built world](OPENMAP-LOCAL-BUILT-WORLD.md), and [Screening Context v1](SCREENING-CONTEXT-V1.md).
