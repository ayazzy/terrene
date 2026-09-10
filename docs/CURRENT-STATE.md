# Terrene current state

> Repository implementation is authoritative where this document is stale.

This is an operational map of what exists on 10 September 2026. Inspect the relevant code, tests and linked implementation reports before changing it.

## Product architecture

- React 19 and TypeScript frontend built through the Vinext/Vite Sites scaffold, with MapLibre for geographic views.
- FastAPI API and a lease-based Python worker sharing SQLAlchemy models and deterministic processing code.
- PostgreSQL/PostGIS is the intended database; SQLite and Shapely provide the local/test path.
- Content-addressed object storage uses `data/objects` locally and requires private R2-compatible storage when hosted.
- Sites, boundary versions, assessments/jobs, dataset versions/features, reports, Evidence Snapshots and ModuleRuns are persisted. Existing tenant/auth controls are implemented, but the hosted external stack has not been deployed end to end.

See [Architecture](ARCHITECTURE.md), [Nature Intelligence](NATURE-INTELLIGENCE.md) and [data/source rules](DATA.md).

## Implemented capabilities

- Create sites from a drawn or uploaded Polygon/MultiPolygon; validate, version and preserve boundary history.
- Submit deterministic assessments with pinned dataset/model configuration, deduplication, worker leases/retries/fencing and immutable saved results.
- Inspect portfolio sites in map-first or list mode; open evidence-aware site analysis across Overview, Physical, Ecology, Constraints, Evidence and History.
- View source lineage and exact bounded overlay geometry, compare selected sites, record a current team review status, and export self-contained HTML reports.
- Project legacy saved assessments into immutable `land_evidence_v1` snapshots without changing the original assessment.
- Bind a committed snapshot through `wetland_input_binding_v1`, execute the unchanged wetland model, and persist an immutable ModuleRun.
- Intentionally prepare or reuse Screening Context v1 for a selected saved assessment, inspect its non-scoring facts/gaps/provenance in Overview, and download a self-contained HTML review artifact.
- Read the built-world objects attached to an immutable Screening Context run through an authenticated, organization-scoped WGS84 GeoJSON presentation contract without changing their authoritative EPSG:27700 evidence.

Implementation reports: [snapshot persistence](LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md), [snapshot-driven wetland runs](WETLAND-SNAPSHOT-MODULE-RUN.md), [evidence-aware site analysis](UI-STAGE-2.md), and [map-first home](UI-STAGE-3-MAP-HOME.md).

## Real-data sources

Connected sources include:

- Environment Agency LIDAR Composite DTM 1m: elevation and slope summaries.
- OS Open Rivers: watercourse intersection, proximity and distance.
- ESA WorldCover 2021 v200: mapped land-cover distribution and derived mapped fractions.
- Environment Agency Flood Map for Planning Zones 2/3 within a bounded Oxford corridor.
- Natural England SSSI, legacy Ancient Woodland and revised Ancient Woodland inventories.
- Natural England Priority Habitats Inventory: source-feature relationships and habitat-specific/union mapped overlap.
- OS OpenMap – Local release `2026-04`: bounded built-world objects and relationships.

Environment Agency Working with Natural Processes floodplain-reconnection data is retained only as an independent verification benchmark, not a model input. Source coverage, licences, embedded terms and limits are detailed in [Data](DATA.md), [Priority Habitats](PRIORITY-HABITATS-EVIDENCE.md) and [OpenMap Local built world](OPENMAP-LOCAL-BUILT-WORLD.md).

## Terrene Earth today

`land_evidence_v1` registry v3 represents reusable observations, gaps, capabilities, definitions, source/raw references and lineage for immutable parcel boundaries. It also represents these built-world objects:

- `MappedBuildingObject`
- `FunctionalSiteObject`
- `RailwayTrackObject`
- `RailwayStationObject`

`ParcelObjectRelationship` records explicit topology such as `contained_within`, `overlaps`, `touches`, `crosses`, `intersects` and `minimum_distance`, with source and processing provenance. Derived observations include mapped building and functional-site overlap, mapped railway length within a parcel, and minimum track/station distance when search coverage is complete.

Priority Habitat Inventory observations preserve contributing source features and mapped habitat classes. Known mapped zero is represented separately from missing, partial, outside-coverage or failed evidence.

## Terrene Reasoning today

The historical wetland reasoning module is `wetland_restoration_v0_1`, using retained historical feature and processing identifiers such as `crc_wetland_features_v0_1_1`. It separates physical potential, current restoration need and implementation feasibility and refuses an overall result when required evidence is insufficient. Its snapshot execution path records the binding, model specification/signature, result and immutable ModuleRun identity.

The 12 retained Oxford verification locations have inspectable physical and hydrological components, but the model still reports overall `INSUFFICIENT_DATA`. New Priority Habitat and OpenMap Local evidence is intentionally not silently rebound into the historical wetland model.

`site_screening_context_v1` adds deterministic, offline human-review context over a committed snapshot through `screening_context_binding_v1`. It preserves source-bounded facts and gaps, qualifies mapped zeros, presents fixed source-semantic comparisons and asks unresolved review questions. It produces no score or progression decision. These are pilot rules, not customer-validated requirements.

## Application/UI state

The current home is a map-first portfolio view with a preserved list workflow. Site analysis is evidence-aware, keeps calculated findings separate from team review status, switches map and evidence together for historical assessments, and exposes missing/partial evidence without manufacturing locations or values. The UI remains a small-portfolio application and fetches site/history collections without pagination.

Screening Context is an explicit assessment action: POST creates/reuses a snapshot and ModuleRun; GET only discovers or reads stored records. History selection scopes the action to the saved assessment and boundary. Unsupported legacy evidence fails without rewriting it. Export labels current team review status separately from the immutable context. See [Screening Context v1](SCREENING-CONTEXT-V1.md).

`GET /api/screening-context-runs/{run_id}/map-features` integrity-checks the selected run and committed Evidence Snapshot, then deterministically presents only its persisted Building, FunctionalSite, RailwayTrack and RailwayStation objects as EPSG:4326 GeoJSON. Layer metadata distinguishes available objects, qualified mapped zero, unavailable, partial and unsupported evidence. The response retains safe source, classification, fingerprint, relationship and measurement linkage while omitting raw storage locations and source payloads; it creates no persistence and never substitutes current objects into a historical run.

The Screening Context read lifecycle is finite: stored, absent, unsupported, authentication/authorization and server/network outcomes are distinct; unresolved reads recover to Retry after 15 seconds. Routine workspace refreshes do not restart an unchanged assessment read, and cancelled or stale assessment responses cannot replace the selected assessment's context.

## Verification baseline

Housekeeping verification on 10 September 2026:

- Python/SQLite suite: **160 passed**, 13 dependency warnings.
- Frontend Node regression suite: **19 passed**.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed with the existing large-chunk advisory.
- `npm run lint`: fails on existing generated UI accessibility rules and pre-existing frontend `any`/effect diagnostics; this is a known baseline, not a housekeeping regression.

The latest OpenMap Local implementation report also records **160 passed** on disposable PostgreSQL 17/PostGIS 3.5 and real-data verification across 12 Oxford locations. That PostgreSQL suite was not rerun during housekeeping.

Screening Context verification: **176 backend tests passed on SQLite and disposable PostgreSQL/PostGIS**, **24 frontend tests passed**, TypeScript and production build passed. New frontend modules pass focused lint; the changed page retains its existing 20 diagnostics. The report records retained-source replay, browser QA and the pre-existing newer-fixture wetland provenance discrepancy.

The finite Screening Context read-state fix was verified with **177 backend tests on SQLite**, **27 frontend tests**, TypeScript, focused lint, production build and browser QA of stored/absent/unsupported/access/failure/retry/timeout/stale-switch states. PostgreSQL/PostGIS was not rerun for this UI lifecycle fix.

Screening Context map-feature verification: **183 backend tests passed on SQLite** and the focused **23-test Screening Context suite passed on PostgreSQL/PostGIS**. Retained real-data checks cover Westgate, Oxford station, Port Meadow and Redbridge; they verify deterministic WGS84 geometry, organization isolation, historical selection, integrity failures, no-write behavior, availability semantics and unchanged persisted measurements.

## Known limitations

- No connected production soil drainage source; actual wetland extent/condition, measured groundwater, water quality, hydroperiod and complete habitat/infrastructure context remain missing.
- Most acquisition is bounded to the Oxford pilot; flood coverage is narrower, and source-specific mapped absence never proves real-world absence.
- The wetland model is unvalidated and cannot yet rank the retained real locations defensibly.
- Hosted Supabase/Render/R2 credentials and end-to-end tenant acceptance have not been configured or verified; the reserved Sites frontend is not a deployed product.
- Team review status is not yet an immutable historical Decision record.
- Scenario modelling is not implemented. Broader Terrene Applications remain hypotheses, not completed architecture.

## Latest meaningful implementation

The Screening Context map-feature read contract was completed on 10 September 2026. It adds an authenticated, deterministic WGS84 presentation of the selected immutable run's persisted built-world evidence without changing acquisition, evidence projection, Screening Context rules, authoritative EPSG:27700 geometry, retained snapshots or pre-existing ModuleRuns.

## Current recommended engineering question

Use the Screening Context pilot with a prospective reviewer to establish which source distinctions and unresolved evidence questions matter in an actual diligence workflow before expanding its rules or datasets.
