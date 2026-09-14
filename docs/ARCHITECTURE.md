# Terrene architecture

## Status and vocabulary

This document describes the architecture implemented through 14 September 2026 and its intended direction. It does not claim that future layers already exist. Where code still uses `CRC` or `crc`, those names are retained for historical compatibility and reproducibility.

The core concepts are deliberately distinct:

- **Object:** something represented as existing in the world, such as a parcel, building, habitat feature, railway line or station.
- **Relationship:** a connection or spatial relationship between objects, such as overlap, containment, crossing or minimum distance.
- **Observation:** an evidence-backed reusable fact with defined semantics, spatial/temporal support, coverage, source and lineage.
- **Interpretation:** the versioned output of a reasoning module. It may express suitability, constraint, risk or another modelled conclusion; it is not promoted to a reusable fact.
- **Decision:** a human or operational action/state with its own actor, time and evidence context. It is not an observation or model result.

## Implemented system

The web application consists of a React/TypeScript frontend, a FastAPI API and a Python worker. PostgreSQL/PostGIS provides the intended relational/spatial store; SQLite plus Shapely supports local development and isolated tests. Native artifacts, immutable manifests and reports use content-addressed object storage (`data/objects` locally; private R2-compatible storage when hosted).

The frontend calls the API through the server-side route in `app/api/[...path]/route.ts`. One persistent Infrastructure Operating Picture MapLibre scene is the spatial index for authorized Sites and Project Subjects across geographic overview, Site investigation and Project Intelligence modes. Sites use exact saved boundaries. Project Subjects receive a map marker only through an explicit authorized `site_id` relationship; subjects without one remain in an unlocated-intelligence roster and never receive inferred geography. For a selected Site artifact, `infrastructure_map_scene_v1` projects one exact committed Evidence Snapshot into safe WGS84 presentation features and semantic layer/capability metadata. Native MapLibre GeoJSON sources, rendered-feature queries and feature state own primary-map rendering and selection; SVG projection is confined to the isolated boundary editor. The scene is top-down by default and exposes 55-degree perspective only when valid building-height observations permit evidence-backed extrusion. Layers, generated legend and roster are mutually exclusive left-side surfaces. One shared entity-dossier shell is docked on desktop and becomes a bottom sheet on narrow screens; it presents either Site evidence/reasoning/history or Project source assertions/conclusions/history beside that map. Its identity band names the exact evidence artifact and historical state; collapse changes presentation only and does not clear selection, section or artifact. The shared URL-addressable controller drives map, roster, global entity search, dossier selection, historical artifact and meaningful layer state. The API owns authorization, site/boundary operations, assessment submission, saved evidence and report access. The worker owns deterministic acquisition/processing/model execution under lease and fencing rules.

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

Today, Terrene Earth is implemented principally by the existing CRC Earth records, the validated `land_evidence_v1` projection and immutable `project_evidence_v1` source-assertion bundles. The land projection has versioned definitions and retains boundary identity, observations, gaps, capabilities, source/raw references, selections and lineage.

Registry v3 additionally carries a narrow typed union of OpenMap Local `MappedBuildingObject`, `FunctionalSiteObject`, `RailwayTrackObject` and `RailwayStationObject` records and `ParcelObjectRelationship` records. Registry v4 adds `BuildingHeightObservation` as immutable evidence linked to one existing building, exact paired EA DSM/DTM raw sources and an object-linked gap when the method cannot safely produce a value. Height is not a mutable object attribute. Priority Habitat evidence retains source-feature relationships and mapped habitat classification. This is intentionally not a universal ontology or graph database.

`project_evidence_v1` represents human-submitted, source-backed assertions about a monitored real-world `ProjectSubject`. A minimal immutable Project Subject has organization ownership, a stable ID, display name, bounded project type and an optional Site relationship; no parcel boundary is fabricated when the Site is unknown. Each bundle retains exact source versions, publication and recording times, excerpts, locators, a small typed claim vocabulary, explicit event/target time semantics and correction lineage. Conflicting claims coexist. Attribution does not establish truth, and no Project Evidence route fetches source URLs or creates a derived conclusion.

### Immutable Evidence Snapshots

A saved legacy assessment may be projected into an independently identified snapshot. The canonical validated manifest is stored immutably in private object storage; relational tables index identity, membership, links and origin associations. Semantic content and exact manifest bytes have separate hashes. Reuse is content-addressed, publication is compare-and-set, and a changed boundary/source/observation/selection/gap produces a new identity.

The legacy assessment is never updated by projection. Earlier manifests remain byte-identical when later registry/source evidence is added.

Project Evidence uses the same publication discipline in a separate contract rather than forcing project claims into parcel observations. A canonical bundle manifest is published through immutable object storage before one transaction records the bundle, exact ordered membership and stable source-version/claim identity catalogues. Organization and Project identity are part of deterministic bundle identity. Identical retries reuse the first committed bundle, including under concurrent submission; changed evidence creates a new bundle. An optional land relationship pins one specific committed Evidence Snapshot ID, content hash, Site and boundary version—never “latest”.

### Versioned module bindings

`wetland_input_binding_v1` validates a committed `land_evidence_v1` snapshot, checks immutable boundary identity and translates selected facts and explicit gaps into the unchanged historical `crc_earth_v0_1` contract. It preserves precision, support, provenance and legacy quality metadata. Binding is explicit so a new evidence registry cannot silently change a historical model input.

`project_evidence_binding_v1` consumes a caller-selected, non-empty set of exact Project Evidence bundle IDs. It canonicalizes ordering, pins every bundle/content/manifest identity and complete source-version/claim membership, requires complete acyclic correction ancestry, and identifies active versus superseded claims without deleting either. Conflicting active claims remain bound. Recording time defines evidence as-of; publication recency is never a conflict-resolution rule. Any changed membership or committed bundle content creates a different binding.

### Terrene Reasoning

The historical wetland module is the deterministic `wetland_restoration_v0_1` model. It runs without network access from the bound state and pinned model specification. Its interpretations remain separate from core Evidence Snapshot membership. Priority Habitat, built-world and building-height additions do not alter this model unless a future versioned binding/model explicitly adopts them. Paired building-height acquisition runs after the legacy model and remains outside `crc_earth_v0_1`.

`site_screening_context` is an additive non-scoring module, version `site_screening_context_v1`, using `screening_context_binding_v1`. It consumes validated committed `land_evidence_v1` content directly and copies source measurements, support, gaps and provenance into a typed review contract. Declared deterministic rules generate mapped-zero qualifications, source-semantic contexts and human questions. The specification signature pins configuration, rule declarations and result-contract schema; runtime timestamps and mutable team status are outside the semantic result. No network acquisition or free-form model interpretation occurs.

`project_intelligence_v1` is a pure deterministic module over one validated `project_evidence_binding_v1`. It reports a bounded project stage plus separate planning and construction findings, reported grid targets, conflicts and unresolved questions. Every conclusion points to retained claim/source-version/passage identities. A correction changes the active conclusion only in a new binding/run; newer publication time alone never wins. Elapsed target dates remain `elapsed_unverified`. The module emits no confidence/risk score, commercial recommendation or workflow decision.

### Immutable ModuleRuns

A ModuleRun records organization, site/boundary, Evidence Snapshot/content hash, module and binding versions, model signature/specification, exact saved result and a deterministic content hash. Repeated identical execution reuses the same identity; contradictory content fails rather than overwrites it.

Screening uses the same ModuleRun table, deterministic identity and immutable persistence primitives, with a narrow module-specific validation dispatch. Its scoped reader also recalculates from committed evidence and rejects contradictions. The existing wetland validation and execution branch is unchanged; no database migration is required.

Project Intelligence uses the dedicated `project_intelligence_runs` table because a Project Subject need not have a Site or boundary. A run stores the complete evidence binding, signed specification and exact result. Identity covers tenant, subject, binding, module/version and signature. Reads select the registered historical implementation from the stored module/binding version tuple, recompute hashes, validate the binding, rerun that module and reconstruct the binding from committed bundles; GET never creates a run. Identical and concurrent POST retries reuse the first immutable run.

### Intentional screening application action

`POST /api/assessments/{id}/screening-context` verifies ownership and a completed or terminal partial saved result, reuses its existing snapshot origin (including historical registry versions), or explicitly creates one before executing the module. Ordinary discovery, run reads and export GETs never create snapshots or runs. Multiple existing origins require explicit version selection that v1 does not offer; unsupported historical evidence is reported and preserved.

The Overview panel is keyed to the selected assessment. Stored facts and rule-generated review items remain separate from mutable team status. The self-contained HTML export contains run/snapshot/boundary identities and inspectable evidence, with current team status labelled as operational state at export. Public raw-reference identities and checksums remain visible; private storage locations and asset paths are omitted.

### Snapshot-native infrastructure map scene

`GET /api/land-evidence-snapshots/{snapshot_id}/map-scene` is a read-only presentation projection, not a new evidence store. The API authorizes the snapshot by organization, reloads and validates its immutable manifest, checks the relational snapshot envelope and content hash, and only then returns `infrastructure_map_scene_v1`. It includes exact snapshot, Site and boundary identity; semantic layer and capability states; source/release/evidence-time metadata; WGS84 GeoJSON presentation geometry; mapped-object classifications; typed parcel relationships; and object-linked height evidence or gaps. Authoritative geometry identity and measurements remain EPSG:27700.

The primary map discovers the selected snapshot through the existing immutable Screening Context run envelope, then reads the scene directly by snapshot ID. Its client request lifecycle is fenced by both cancellation and a monotonically increasing generation, so a late response cannot replace the currently selected assessment. A failed or identity-inconsistent scene fails closed instead of retaining an earlier entity's objects. The legacy `screening_context_map_features_v1` endpoint remains unchanged for its existing Screening Context consumers. Registry v1/v2 scenes expose unsupported layers, registry v3 exposes built-world objects with height unsupported, and registry v4 permits extrusion only when a valid `BuildingHeightObservation` supplies an exact P90 value. Missing, partial, gap and unsupported height states remain explicit at scene level: only valid available/partial observations may extrude, while every other building remains a labelled flat outline and never receives a fallback.

### Basemap and operating-picture presentation

MapLibre style selection is presentation configuration, not evidence acquisition. `NEXT_PUBLIC_BASEMAP_STYLE_URL` selects the preferred production vector style. `NEXT_PUBLIC_BASEMAP_URL` remains a compatibility fallback for the earlier raster configuration. When neither is configured in local development, the application uses OpenFreeMap Dark with its required attribution. It does not use the public OpenFreeMap service implicitly in production because that service has no SLA; an unconfigured production build retains a dark blank style, renders Terrene-owned scene layers and reports the missing configuration explicitly. A remote style failure at runtime swaps to the same evidence-only dark style and then installs the Terrene sources and layers. Later tile failures mark the basemap degraded without recasting retained evidence as unavailable. Optional missing decorative basemap sprites resolve transparently and do not pollute the evidence-failure channel.

The operating palette has stable semantic roles: cyan for Site boundaries, amber for selection, slate for buildings, teal for functional sites, high contrast for stations and exact retained-classification colours for railway tracks. The generated legend is derived from the loaded scene and its capability/layer states, including available, mapped-zero, partial, unavailable and unsupported. Style and legend logic may explain missing evidence but may not substitute values, classifications or route identities.

GeoLibre informs cartographic authoring and analyst-workbench direction but is not a frontend dependency, embedded runtime or evidence authority. General GIS authoring remains deferred until a validated workflow requires it.

## Existing application records

Sites have mutable presentation fields and point to a current immutable boundary version. Assessments snapshot the boundary, dataset/model configuration and evidence at submission. Dataset releases/features and content-addressed raw artifacts retain source provenance. HTML reports render saved assessment evidence; current team review state is shown separately.

Project Subjects are intentionally not a general project-management model. `/api/project-subjects` owns monitored real-world project identity and immutable evidence; it has no editable stage, score, recommendation, task, assignee, pipeline or decision field. Project Intelligence findings are immutable versioned reasoning output and never update source evidence.

The existing `/api/projects` and `infrastructure_projects` persistence remain the technical Design Study compatibility contract: a Site- and Evidence-Snapshot-pinned container for Alternatives and immutable Design Revisions. A Design Study cannot exist without its baseline. It is distinct from a Project Subject even when both describe related future work; linking them is deferred.

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

Detailed implementation references: [Land Intelligence Foundation](LAND-INTELLIGENCE-FOUNDATION.md), [Evidence Snapshot persistence](LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md), [wetland binding and ModuleRuns](WETLAND-SNAPSHOT-MODULE-RUN.md), [Priority Habitats](PRIORITY-HABITATS-EVIDENCE.md), [OpenMap Local built world](OPENMAP-LOCAL-BUILT-WORLD.md), [EA LIDAR building heights](EA-LIDAR-BUILDING-HEIGHTS.md), [Screening Context v1](SCREENING-CONTEXT-V1.md), and [Project Evidence v1](PROJECT-EVIDENCE-V1.md).
