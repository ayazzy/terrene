# Terrene current state

> Repository implementation is authoritative where this document is stale.

This is an operational map of what exists on 13 September 2026. Inspect the relevant code, tests and linked implementation reports before changing it.

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
- Inspect portfolio sites in map-first or list mode; open the Site Analysis Workspace across Overview, Evidence, Models and History. Screening Context is the default Overview and the wetland assessment is a secondary Terrene Reasoning module.
- View source lineage and exact bounded overlay geometry, compare selected sites, record a current team review status, and export self-contained HTML reports.
- Project legacy saved assessments into immutable `land_evidence_v1` snapshots without changing the original assessment.
- Bind a committed snapshot through `wetland_input_binding_v1`, execute the unchanged wetland model, and persist an immutable ModuleRun.
- Intentionally prepare or reuse Screening Context v1 for a selected saved assessment, inspect its non-scoring facts/gaps/provenance in Overview, and download a self-contained HTML review artifact.
- Read the built-world objects attached to an immutable Screening Context run through an authenticated, organization-scoped WGS84 GeoJSON presentation contract without changing their authoritative EPSG:27700 evidence.
- View and select persisted buildings, functional sites, railway tracks and railway stations on the Site Analysis Workspace map, with truthful per-layer availability and one shared parcel-relationship/source inspector.
- Create/read minimal organization-owned Project Subjects without requiring a Site, and submit/list/read immutable human-structured `project_evidence_v1` source-assertion bundles.
- Bind explicit Project Evidence bundles through `project_evidence_binding_v1`, run deterministic `project_intelligence_v1`, and list/read immutable project-specific runs.
- Inspect Project Subjects, exact source assertions, Terrene conclusions, conflicts, unresolved questions and historical runs in a separate read-only Project Intelligence workspace.

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

`project_evidence_v1` is a separate Terrene Earth contract for attributed project assertions. It retains exact source versions, excerpts and locators; publication, recording and effective/target dates; a bounded planning/construction/grid-target vocabulary; explicit correction lineage; and an optional pin to one committed land Evidence Snapshot. Contradictory claims coexist and no claim is promoted to a Terrene conclusion.

Priority Habitat Inventory observations preserve contributing source features and mapped habitat classes. Known mapped zero is represented separately from missing, partial, outside-coverage or failed evidence.

## Terrene Reasoning today

The historical wetland reasoning module is `wetland_restoration_v0_1`, using retained historical feature and processing identifiers such as `crc_wetland_features_v0_1_1`. It separates physical potential, current restoration need and implementation feasibility and refuses an overall result when required evidence is insufficient. Its snapshot execution path records the binding, model specification/signature, result and immutable ModuleRun identity.

The 12 retained Oxford verification locations have inspectable physical and hydrological components, but the model still reports overall `INSUFFICIENT_DATA`. New Priority Habitat and OpenMap Local evidence is intentionally not silently rebound into the historical wetland model.

`site_screening_context_v1` adds deterministic, offline human-review context over a committed snapshot through `screening_context_binding_v1`. It preserves source-bounded facts and gaps, qualifies mapped zeros, presents fixed source-semantic comparisons and asks unresolved review questions. It produces no score or progression decision. These are pilot rules, not customer-validated requirements.

`project_intelligence_v1` is deterministic reasoning over one explicit `project_evidence_binding_v1`. It reports bounded lifecycle stage, separate planning/construction findings, grid target states, conflicts and evidence-grounded questions. Explicit corrections supersede active use without erasing history; recency alone never resolves conflict, and elapsed targets do not establish outcomes. Results include exact claim/source-version/passage references and no score or recommendation.

## Application/UI state

The current home is a map-first portfolio view with a preserved list workflow. Site Analysis Workspace v2A leads with source-bounded Screening Context, places detailed facts/gaps/provenance under Evidence, places the unchanged wetland assessment under Models, and keeps immutable assessment selection under History. Site-level actions explicitly distinguish creating an assessment, preparing/reusing or exporting Screening Context, exporting the wetland model report and changing the current team review status.

One shared site-workspace controller scopes the selected assessment, Screening Context lifecycle, history selection, map/evidence focus, exports and workspace controls. Switching sites or historical assessments clears stale artifact views and keys Screening Context to the exact assessment/site/boundary identity. Historical map, boundary, Earth evidence, context and model output move together. The desktop review panel is wider; at narrow widths the map and independently scrollable analytical workspace stack deliberately. The UI remains a small-portfolio application and fetches site/history collections without pagination.

The analytical map consumes the selected Screening Context run's map-feature contract and preserves its source-bounded layer states: available objects, mapped zero, unavailable, partial and unsupported historical evidence. Terrene-rendered built-world geometry is visually distinct from the raster basemap. Object selection is shared with Overview/Evidence, does not move the default parcel focus, and opens one inspector with plain parcel relationship, measurement, source/release and limitation; raw identities, fingerprints, exact predicates and detailed provenance remain under Advanced provenance. Locate object is intentional. Hiding its layer, changing run, site or historical assessment clears selection.

Screening Context is an explicit assessment action: POST creates/reuses a snapshot and ModuleRun; GET only discovers or reads stored records. History selection scopes the action to the saved assessment and boundary. Unsupported legacy evidence fails without rewriting it. Export labels current team review status separately from the immutable context. See [Screening Context v1](SCREENING-CONTEXT-V1.md).

`GET /api/screening-context-runs/{run_id}/map-features` integrity-checks the selected run and committed Evidence Snapshot, then deterministically presents only its persisted Building, FunctionalSite, RailwayTrack and RailwayStation objects as EPSG:4326 GeoJSON. Layer metadata distinguishes available objects, qualified mapped zero, unavailable, partial and unsupported evidence. The response retains safe source, classification, fingerprint, relationship and measurement linkage while omitting raw storage locations and source payloads; it creates no persistence and never substitutes current objects into a historical run.

The Screening Context read lifecycle is finite: stored, absent, unsupported, authentication/authorization and server/network outcomes are distinct; unresolved reads recover to Retry after 15 seconds. Routine workspace refreshes do not restart an unchanged assessment read, and cancelled or stale assessment responses cannot replace the selected assessment's context.

The read-only Project Intelligence workspace is isolated from the Site map. It lazily reads Project Subjects and immutable run history, allows explicit historical selection, and visually separates source assertions from Terrene conclusions. It provides no evidence/project editor or workflow action.

Versioned Design Studies remain API-only. The frontend has no Alternative editor, design map tools or Design Revision history UI.

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

Site Analysis Workspace v2A verification: **28 frontend regression tests passed**, TypeScript passed, focused lint passed on the new/refined workspace modules, and the production build passed with the existing large-chunk advisory. Browser QA covered populated and absent Screening Context, Evidence/Models navigation, model-to-evidence routing, historical selection/reset, both distinct exports, desktop 1440×900 and narrow 390×844 layouts, and finished with no browser warnings or errors. Backend and PostgreSQL suites were not rerun because this iteration changes frontend information architecture and state only.

Site Analysis Workspace v2 verification: **32 frontend regression tests passed**, TypeScript passed, focused lint passed on the new/refined map/workspace modules, and the production build passed with the existing large-chunk advisory. Browser QA at 1280px, 1024px and 390px used isolated retained records for Westgate, Oxford station, Port Meadow and Redbridge; verified object counts, source/relationship inspection, exact 43.3473% and 279.31 m evidence, mapped-zero/partial/unsupported semantics, layer-driven selection reset, historical switching, no horizontal overflow and no browser warnings/errors. Backend and PostgreSQL suites were not rerun because the v2B contract and evidence persistence were unchanged.

Screening Context map-feature verification: **183 backend tests passed on SQLite** and the focused **23-test Screening Context suite passed on PostgreSQL/PostGIS**. Retained real-data checks cover Westgate, Oxford station, Port Meadow and Redbridge; they verify deterministic WGS84 geometry, organization isolation, historical selection, integrity failures, no-write behavior, availability semantics and unchanged persisted measurements.

Sprint 001 design-proposal verification: **197 backend tests passed on SQLite and PostgreSQL/PostGIS**, including the focused **14-test** Project/Alternative/Revision suite after independent-review fixes. Persistence is verified across a database/engine reload; regressions cover missing/corrupt baselines and lineage plus malformed geometry/boundary inputs. The additive v6 migration passed against the disposable PostgreSQL database.

Sprint 002 verification: the combined Project Evidence, Design Study and Project Intelligence suite passed **43 tests on SQLite** and **43 tests on disposable PostgreSQL/PostGIS**. The default fresh-clone path passed **163 tests with 63 retained-data checks explicitly skipped**; the retained-data opt-in passed **226 tests**. All **36 frontend Node tests**, TypeScript, focused lint and the production build passed. Browser QA covered the complete four-run synthetic history, exact evidence/correction inspection, desktop and narrow layouts, no horizontal overflow, and no browser errors. The existing large-chunk build advisory remains. See [Project Intelligence v1](PROJECT-INTELLIGENCE-V1.md).

## Known limitations

- No connected production soil drainage source; actual wetland extent/condition, measured groundwater, water quality, hydroperiod and complete habitat/infrastructure context remain missing.
- Most acquisition is bounded to the Oxford pilot; flood coverage is narrower, and source-specific mapped absence never proves real-world absence.
- The wetland model is unvalidated and cannot yet rank the retained real locations defensibly.
- Hosted Supabase/Render/R2 credentials and end-to-end tenant acceptance have not been configured or verified; the reserved Sites frontend is not a deployed product.
- Team review status is not yet an immutable historical Decision record.
- Scenario modelling is not implemented. Broader Terrene Applications remain hypotheses, not completed architecture.
- Proposed design revisions accept bounded Polygon/MultiPolygon GeoJSON only; there is no CAD/PDF ingestion, centreline buffering, layout generation, environmental intersection, impact calculation or A/B consequence comparison.

## Latest meaningful implementation

Project Intelligence v1 was completed on 13 September 2026. It reconciles Project Subjects with the retained Design Study contract, binds exact Project Evidence, produces deterministic stage/status/target findings and exposes immutable history through API and a thin read-only UI. It does not imply a real-project claim, validated customer workflow, commercial recommendation or Scenario capability.

## Current recommended engineering question

Use a real-project research engagement and customer discovery to test whether these inspectable findings materially improve a recurring project decision. Do not add automated research, scoring or workflow actions before that evidence exists.
