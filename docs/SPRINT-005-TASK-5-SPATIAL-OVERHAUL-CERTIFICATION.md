# Sprint 005 Task 5 — Spatial overhaul certification

## Outcome

Sprint 005 is certified as an evidence-safe spatial foundation. Oxford Station remains the real-data proving scene, while failed cartography, missing or historical height evidence and late scene responses now have explicit presentation states. The changes improve Terrene's ability to represent reality without turning a basemap or an extrusion into evidence.

This task does not claim that the current interface is production-ready. It closes the engineering failure modes before a separate observation-led usability bug bash.

## Root cause

The native scene and dark operating picture were functional, but their failure boundaries were not fully separated in the interface. A remote style failure could prevent the normal style-load path that installs Terrene layers; building-level partial or unavailable height states were visible only after inspection; and an optional basemap sprite warning polluted browser diagnostics. Scene reads already used immutable identity checks, but cancellation needed an explicit generation-fence regression so late responses could not reintroduce a prior assessment.

## Implementation / architecture

- The primary MapLibre scene installs Terrene sources and semantic layers from `style.load`, including after a failed remote style swaps to an evidence-only dark style.
- Basemap state is explicit as loading, available, degraded or unavailable. A cartographic failure does not recast retained evidence as missing.
- Optional missing decorative basemap sprites resolve to a transparent pixel and remain outside the evidence failure channel.
- Scene-level status derives only from building features in the selected immutable scene. It distinguishes partial evidence, unavailable height, historical unsupported evidence and mixed evidence-backed/flat coverage.
- Available and partial `BuildingHeightObservation` records remain valid extrusion inputs; gap, unsupported and unrecorded buildings remain flat. No default height is introduced.
- The selected scene read remains no-store and exact-snapshot scoped. Abort plus a monotonically increasing request generation prevents a late response from replacing the current assessment.
- The prior decisions establishing the snapshot-native map scene, object-level height evidence and GeoLibre's non-runtime role remain authoritative. A final decision records their shared failure-boundary rule.

## Files changed

- `app/map.tsx` — basemap fallback, presentation states and scene-level height status.
- `app/infrastructure-map-scene.ts` — deterministic building-height state aggregation and copy.
- `app/map-feature-inspector.tsx` and `app/globals.css` — explicit available/partial observation labels.
- `app/infrastructure-map.module.css` — non-blocking scene-status treatment across desktop and narrow layouts.
- `tests/infrastructure-map-scene.test.mjs` and `tests/map-regressions.test.mjs` — height semantics, fallback and stale-request regression coverage.
- `docs/CURRENT-STATE.md`, `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` — certified state, durable failure boundaries and next product question.

## Verification

- Frontend Node regression suite: **81 passed**.
- TypeScript: `npx tsc --noEmit` passed.
- Focused lint on the changed TypeScript and test modules: passed.
- Production build: passed with the existing large-chunk advisory.
- Fresh-clone backend suite: **189 passed, 63 retained-data tests skipped**.
- Focused building-height, map-scene and Oxford operating-scene suite on disposable PostgreSQL/PostGIS: **19 passed**.
- `git diff --check`: passed.

## Browser QA

- The live Oxford registry-v4 scene at the available 1283 px viewport loaded with an available dark basemap, exact selected asset, explicit `Partial evidence · 4 of 5 building estimates have a partial state` status and zero horizontal document overflow.
- Perspective enabled the evidence-backed extrusion layer and changed the control to pressed `2D`; returning to 2D restored the top-down state without clearing Said Business School selection.
- A configured unreachable style produced an explicit basemap-unavailable warning while the boundary, buildings, functional sites, tracks, station and selected asset remained available on the evidence-only background.
- The final normal reload produced no new browser warning or error. Task 3's unchanged operating shell remains previously certified at 1440, 1280, 1024 and 390 px; Task 5 adds only the responsive status surface within that shell.

## Historical / compatibility impact

No Site, boundary, assessment, Evidence Snapshot, ModuleRun, source artifact, object, relationship or observation changed. Registries v1–v3 and the legacy `screening_context_map_features_v1` response remain supported and unchanged. Registry-v3 building heights remain unsupported and flat; no registry-v4 value is substituted into historical evidence.

GeoLibre remains a design and style-authoring reference rather than a runtime dependency. OpenFreeMap remains an attributed local-development default without a production SLA commitment.

## Known limitations

- The committed repository intentionally contains no Oxford QA database or raw DSM/DTM rasters; a fresh environment must run the external provisioner.
- OpenFreeMap's public service is still suitable only for local development. Production requires an approved configured style or legacy tile endpoint.
- The interface exposes the evidence model comprehensively but is still too dense and system-centric to count as a validated development-analyst workflow.

## Git

Branch: `fix/spatial-overhaul-certification`.

## Recommended next task

Conduct a hands-on usability bug bash as a separate discovery/fix iteration. Record observed failures against the portfolio, site-diligence and asset-intelligence tasks, reproduce and prioritize them, then agree one bounded post-certification UX sprint before implementation.
