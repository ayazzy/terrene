# Wetland snapshot binding and ModuleRun

Implementation date: 8 September 2026. Scope: the third and final bounded Land Intelligence Foundation stage before adding new land evidence.

This stage adds a snapshot-driven execution path alongside the legacy assessment path. It does not change acquisition, `land_evidence_v1`, the wetland feature formulas, weights, thresholds, gates, quality rules, scoring, reports, API routes or the frontend.

## Binding

`wetland_input_binding_v1` is implemented in `backend/wetland_binding.py`. It validates one `land_evidence_v1` manifest, verifies its boundary identity, and translates selected facts and explicit gaps into the unchanged `crc_earth_v0_1` input contract. It then calls the existing `compute_features` function. The existing `run_wetland` implementation consumes the result without any model changes.

The binding preserves original precision, support, source lineage, observation IDs, timestamps and legacy quality metadata. This is deliberate compatibility behaviour, not a claim that the legacy vocabulary is the preferred Land Evidence vocabulary.

| Existing wetland input | `land_evidence_v1` source | Binding behaviour |
|---|---|---|
| `terrain.slope_deg` | `physical.slope.mean` | Exact selected observation; scored physical input |
| `soil.drainage_class` | Gap `soil.drainage.class` | Remains missing; no soil value is imputed |
| `hydrology.distance_to_water_m` | `physical.watercourse.distance_min` | Exact selected mapped-watercourse fact |
| `hydrology.mapped_flood_extent_fraction` | `physical.flood.mapped_extent_fraction` with the declared zone/scenario dimensions | Exact selected mapped context; never converted to probability |
| `land_use.current_cover` | `ecology.land_cover.dominant_class` for ESA WorldCover 2021 v200 | Exact legacy category compatibility view; no management or condition meaning is added |
| `land_use.developed_fraction` | `built.mapped_built_up_fraction` for ESA WorldCover 2021 v200 | Exact legacy feasibility proxy; never treated as complete infrastructure |
| `ecology.mapped_wetland_fraction` | `ecology.mapped_herbaceous_wetland_fraction` | Context-only current-state field; never substituted for actual wetland extent |
| `hydrology.surface_water_fraction` | `physical.mapped_permanent_water_fraction` | Context-only current-state field |
| `ecology.wetland_fraction` | Gap `ecology.wetland.actual_extent_fraction` | Remains missing even when mapped herbaceous wetland is present or zero |
| `ecology.habitat_condition` | Gap `ecology.habitat.condition` | Remains missing; remote cover is not condition |
| `human.infrastructure_fraction` | Gap `built.infrastructure.complete_footprint_fraction` | Remains missing; built-up fraction is not substituted |
| `ecology.irreplaceable_habitat_fraction` | Inventory-scoped `ecology.ancient_woodland.mapped_overlap_fraction` plus the explicit broad incomplete-inventory gap | Reconstructs only the original legacy compatibility scalar. Positive mapped overlap remains a conservative lower bound; inventory zero remains unknown. It does not claim complete irreplaceable habitat. |
| `regulatory.protected_area_fraction` | `designations.overlap_fraction` with `designation_type=SSSI`, `status=notified` | Exact review-flag input; no score effect |
| `terrain.elevation_m` | `physical.elevation.mean` | Exact unassessed context input |
| `ecology.distance_to_habitat_m` | Registered-unconnected capability | Remains absent/missing |
| `hydrology.groundwater_depth_m`, `climate.annual_precipitation_mm`, `hydrology.flow_accumulation` | Registered-unconnected capabilities | Remain absent unassessed context |

The CRC feature layer is unchanged: soil retention still consumes the drainage-class compatibility input; water context still consumes mapped flood extent and mapped-watercourse distance; restoration need still consumes current cover, actual wetland extent and condition; habitat proximity still consumes habitat distance; and unblocked area still consumes developed, infrastructure and legacy irreplaceable-habitat inputs. Their values are module interpretations and never become core observations.

## Execution path

`run_wetland_from_snapshot(snapshot_id, org=..., binding_version=..., spec=...)` performs the bounded execution:

1. resolves and validates the committed snapshot inside the organisation;
2. resolves the matching current or immutable historical boundary and verifies its fingerprint;
3. applies `wetland_input_binding_v1` without acquisition or network access;
4. recomputes the existing feature layer and calls the unchanged `run_wetland` model with the caller-supplied pinned model specification;
5. inserts or safely reuses the immutable ModuleRun.

No assessment result or Evidence Snapshot is updated. The original assessment pipeline in `backend/nature.py` continues to use its saved assessment-owned `EarthState`, and saved reports continue to render only the authoritative saved assessment result.

## ModuleRun

Migration 4 adds one `module_runs` table. Each row records:

- organisation, site and boundary version;
- Evidence Snapshot ID and semantic evidence content hash;
- module ID `wetland_restoration` and module version `wetland_restoration_v0_1`;
- input binding version;
- complete pinned model specification and signature;
- immutable full wetland result;
- deterministic execution ID, immutable content hash, and creation/completion times.

The deterministic ID covers organisation, snapshot ID, module ID/version, binding version and model signature. The content hash additionally covers site/boundary, evidence content hash, exact model specification and complete output. An identical execution safely returns the first row; changed evidence, binding, module version or model configuration has a different identity. Read-time verification rejects a modified result or identity. No update path is provided.

PostgreSQL migration enables row-level security for `module_runs` and revokes direct browser-role access. All run and snapshot lookups include the organisation. No public API was added.

## Parity and separation

The retained-case regression persists a committed Evidence Snapshot for each of the 12 Oxford assessments, binds it, and asserts that both the complete reconstructed `EarthState` and complete `run_wetland` JSON equal the saved legacy values. This full equality includes:

- source and derived feature observations and IDs;
- component inputs, scores, bands, coverage, confidence and missing inputs;
- review flags and current-state fields;
- overall score, band, blocking gaps and evidence summary;
- model, adapter and feature versions, model signature and state fingerprint.

Land Evidence relational memberships continue to contain definitions, reusable facts, gaps, capabilities and provenance only. ModuleRun IDs/results are not added to the snapshot manifest or membership/link tables. Legacy wetland indices remain legacy module-output references, not Land Evidence observations.

## Historical compatibility

All 12 saved assessment payload fingerprints are asserted unchanged after snapshot execution. Existing assessment execution, reads, results, reports and frontend behaviour remain unchanged. Snapshot-driven execution is additive and is not selected as the default for new assessments in this iteration.

## Verification

Verification completed on 8 September 2026:

- SQLite backend suite: **137 passed**, with 13 dependency deprecation warnings;
- additive migration 4 applied successfully to disposable local PostgreSQL/PostGIS `crc_test`;
- PostgreSQL/PostGIS backend suite, including native ModuleRun persistence: **137 passed**, with the same 13 warnings;
- retained Oxford parity: **12/12 exact complete `EarthState` and wetland-result matches**;
- frontend Node regression suite: **19 passed**;
- `npx tsc --noEmit`: passed;
- `npm run build`: passed, with the existing large-chunk advisory;
- Python bytecode compilation for backend and the new test module: passed;
- `npm run lint`: reports 39 existing frontend/generated-component accessibility, `any`, effect and template-expression diagnostics; none is in this backend change.

The focused tests cover missing core inputs, known zero, incomplete ancient-woodland inventory, partial evidence, invalid/corrupt snapshots, wrong boundary, historical boundary resolution, wrong organisation, duplicate/idempotent execution, changed snapshot, changed binding identity, changed model configuration, stored-result integrity and exclusion of module output from Land Evidence.

## Recommended next bounded iteration

Add one source-backed Priority Habitats evidence family to `land_evidence_v1`, including precise habitat-inventory dimensions, coverage/gap semantics, immutable acquisition lineage and retained-real validation; do not change the wetland binding or scoring in that iteration.
