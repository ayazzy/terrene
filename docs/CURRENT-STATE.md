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

The implemented reasoning module is `wetland_restoration_v0_1`, using retained historical feature and processing identifiers such as `crc_wetland_features_v0_1_1`. It separates physical potential, current restoration need and implementation feasibility and refuses an overall result when required evidence is insufficient. Its snapshot execution path records the binding, model specification/signature, result and immutable ModuleRun identity.

The 12 retained Oxford verification locations have inspectable physical and hydrological components, but the model still reports overall `INSUFFICIENT_DATA`. New Priority Habitat and OpenMap Local evidence is intentionally not silently rebound into the historical wetland model.

## Application/UI state

The current home is a map-first portfolio view with a preserved list workflow. Site analysis is evidence-aware, keeps calculated findings separate from team review status, switches map and evidence together for historical assessments, and exposes missing/partial evidence without manufacturing locations or values. The UI remains a small-portfolio application and fetches site/history collections without pagination.

## Verification baseline

Housekeeping verification on 10 September 2026:

- Python/SQLite suite: **160 passed**, 13 dependency warnings.
- Frontend Node regression suite: **19 passed**.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed with the existing large-chunk advisory.
- `npm run lint`: fails on existing generated UI accessibility rules and pre-existing frontend `any`/effect diagnostics; this is a known baseline, not a housekeeping regression.

The latest OpenMap Local implementation report also records **160 passed** on disposable PostgreSQL 17/PostGIS 3.5 and real-data verification across 12 Oxford locations. That PostgreSQL suite was not rerun during housekeeping.

## Known limitations

- No connected production soil drainage source; actual wetland extent/condition, measured groundwater, water quality, hydroperiod and complete habitat/infrastructure context remain missing.
- Most acquisition is bounded to the Oxford pilot; flood coverage is narrower, and source-specific mapped absence never proves real-world absence.
- The wetland model is unvalidated and cannot yet rank the retained real locations defensibly.
- Hosted Supabase/Render/R2 credentials and end-to-end tenant acceptance have not been configured or verified; the reserved Sites frontend is not a deployed product.
- Team review status is not yet an immutable historical Decision record.
- Scenario modelling is not implemented. Broader Terrene Applications remain hypotheses, not completed architecture.

## Latest meaningful implementation

The latest implementation is the [OS OpenMap – Local built-world iteration](OPENMAP-LOCAL-BUILT-WORLD.md), completed 10 September 2026. It adds four source-backed object types, parcel relationships and reusable observations while preserving previous Evidence Snapshots and exact wetland binding/ModuleRun parity.

## Current recommended engineering question

Do not start another product iteration until this Terrene project setup is reviewed. After that review, use customer discovery to decide whether the next bounded engineering work should operationalize a specific diligence workflow and, if so, which minimum non-scoring reasoning adapter or missing evidence source is necessary for that validated decision.
