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

The implemented module is the deterministic `wetland_restoration_v0_1` model. It runs without network access from the bound state and pinned model specification. Its interpretations remain separate from core Evidence Snapshot membership. Priority Habitat and built-world additions do not alter this model unless a future versioned binding/model explicitly adopts them.

### Immutable ModuleRuns

A ModuleRun records organization, site/boundary, Evidence Snapshot/content hash, module and binding versions, model signature/specification, exact saved result and a deterministic content hash. Repeated identical execution reuses the same identity; contradictory content fails rather than overwrites it.

## Existing application records

Sites have mutable presentation fields and point to a current immutable boundary version. Assessments snapshot the boundary, dataset/model configuration and evidence at submission. Dataset releases/features and content-addressed raw artifacts retain source provenance. HTML reports render saved assessment evidence; current team review state is shown separately.

The current review status is operational state, not yet an append-only Decision record. A future decision architecture should add records rather than recast existing status as historical evidence.

## Intended, not completed

### Terrene Scenario

Scenario will represent a proposed intervention as an input and compute an alternative/future state against the same Earth and Reasoning foundations. No general intervention entity, alternative-state engine or scenario comparison contract is implemented today. Drawing a site boundary is not the same as modelling an intervention.

### Terrene Applications

The current UI implements early screening, portfolio navigation and evidence review. Screen, Diligence, Scenario, Monitor, Portfolio, Nature/BNG, Restoration, Field Evidence and infrastructure/renewable workflows are strategic application candidates, not a list of completed products. Customer evidence should determine which vertical workflow is hardened first.

## Architectural constraints

- Facts, interpretations and decisions stay separate.
- Evidence/source scope must remain explicit; known mapped zero is not real-world absence.
- Historical identifiers, hashes, signatures, database structures, snapshots and runs are not renamed for branding.
- Native/licensed/private artifacts remain outside Git and behind organization-aware server access.
- Add new entities, versions and bindings when meaning changes; do not silently mutate historical records.
- Do not optimize the current architecture around 3D visualization.

Detailed implementation references: [Land Intelligence Foundation](LAND-INTELLIGENCE-FOUNDATION.md), [Evidence Snapshot persistence](LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md), [wetland binding and ModuleRuns](WETLAND-SNAPSHOT-MODULE-RUN.md), [Priority Habitats](PRIORITY-HABITATS-EVIDENCE.md), and [OpenMap Local built world](OPENMAP-LOCAL-BUILT-WORLD.md).
