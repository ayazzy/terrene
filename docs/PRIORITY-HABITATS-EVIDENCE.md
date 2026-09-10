# Natural England Priority Habitats Land Evidence

Implementation and verification completed 9 September 2026. This is a source-backed Land Evidence addition, not a wetland-model change or ecological validation.

## Source

CRC uses Natural England's authoritative **Priority Habitats Inventory (England)** ArcGIS Feature Layer 0, service item `39403df11c8044d998772db5b54ad86c`:

- catalogue: [Defra Data Services Platform](https://dsp.environment.data.gov.uk/dataset/92b43165-0dd0-4e69-a712-1e49bb5aa0d0);
- service: [Natural England FeatureServer](https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/Priority_Habitats_Inventory_England/FeatureServer/0);
- source publication value in every acquired feature: `Sep_25`;
- product metadata revision: `2025-10-01`; capture period ends `2025-09-10`; product creation date `2013-06-21`;
- live service `dataLastEditDate`: `2025-10-23T12:36:23.345000+00:00`;
- polygon geometry in British National Grid, EPSG:27700;
- declared product content: 27 priority main habitat classes plus four supporting/non-priority main classes.

The implementation validates schema `natural_england_phi_v3_schema_2025_09` before feature import. The semantically used source fields are:

| Field | CRC use |
|---|---|
| `OBJECTID`, `GlobalID`, `UID` | Source-feature identity and inspectable lineage |
| `MainHabs`, `HabCodes` | Ordered, strictly validated main habitat name/code pairs; one polygon may carry multiple pairs |
| `FeatDesc`, `FeatCodes` | Retained feature qualifiers, not independent mapped-area observations |
| `OtherClass` | Retained survey classification qualifier, such as an NVC/other class |
| `AddHabs` | Retained as “may be present” additional-habitat qualifiers; never assigned polygon area |
| `PrimSource` | Retained concise source-feature lineage |
| `AreaHa` | Retained as the provider's rounded source area; never used for parcel measurement |
| `Version` | Source publication release |

Version 3 explicitly permits overlapping habitats and added qualifying information. Live distinct values were checked, including currently used qualifiers `ANTHL` and `DEGRD(LRBOG)` that are not fully represented in the shorter service prose. Unknown or misaligned main, feature or additional codes stop the import.

The spatial metadata declares public OGL use but also retains source-specific embedded terms. CRC records the Natural England/OS notices; Arnside and Silverdale AONB/Lancaster permission; Forestry Commission/OS terms; Cumbria Biodiversity Data Centre/Cumbria Wildlife Trust and National Trust CC BY 4.0 notices; Environment Agency rights; Northumberland National Park Authority OGL; and Natural England, Rural Payments Agency and North Yorkshire Council notices. The official spatial-metadata URL is retained with each acquisition; downstream redistribution must follow the applicable embedded terms rather than treating the whole compiled product as rights-homogeneous.

## Acquisition and deterministic processing

The repository's existing bounded ArcGIS pattern now acquires PHI for `[-1.65, 51.5, -0.85, 52.05]`. It first requests the exhaustive intersecting object-ID set, sorts it, retrieves batches of 100 with all source attributes and `outSR=4326`, verifies the returned count, validates every source value and requires one publication release.

The final acquisition record is `9e8fa958-77ec-4ec6-a24c-6fec5ccd2449`:

- 14,075 features;
- assembled-original source SHA-256 `8670787e199ab69ce3d4d80178479d85d5c435acc44ac524cb91407965e810b5`;
- one invalid source polygon normalized with Shapely `make_valid` for reference analysis, with its original geometry, attributes and reason retained in the immutable metadata/source artifacts;
- separate immutable original assembled source, live service metadata and normalized-reference geometry objects.

Repeated acquisitions produced the same feature count and SHA-256. This verified reproducibility while creating new immutable dataset records for corrected date and attribution metadata; no existing record or object was edited.

Downstream parcel analysis makes no network call. SQLite conservatively selects candidate bounding boxes; PostgreSQL/PostGIS uses `ST_Intersects`; both perform the final exact polygon intersection in EPSG:27700. Source `AreaHa` is not used. Parcel area, clipped area, per-code unions and the all-main-priority union are computed from geometry at full stored precision.

## Evidence model

`land_evidence_registry_v2` adds two native definitions while leaving every v1 definition unchanged:

| Definition | Dimensions and value |
|---|---|
| `ecology.priority_habitat.mapped_overlap_fraction` | One observation per actual priority `habitat_code`, classified by `natural_england_priority_habitats_inventory_v3`; exact mapped intersection hectares, parcel hectares and fraction |
| `ecology.priority_habitat.any_mapped_overlap_fraction` | Spatial union of every polygon carrying at least one main priority `HabCode`, divided by parcel area; overlapping geometry counts once |

Every native observation records habitat name where applicable, source release/schema/dates, EPSG:27700 feature support, complete acquired-product coverage, derivation method, source/raw references and the exact source-feature references that contribute to it.

Each `SourceFeatureReference` retains PHI UID, GlobalID, OBJECTID, release, reference-geometry fingerprint, rounded provider area, exact parcel intersection area/fraction, main class pairs and status, feature qualifiers, `OtherClass`, `AddHabs` and `PrimSource`. This supports the path parcel → intersection → PHI feature → main habitat classification without creating a generic ontology.

Supporting classes (`FHEAT`, `GMOOR`, `GQSIG`, `NMHAB`) remain inspectable source features but do not contribute to a priority-habitat observation or union. Additional habitats likewise remain qualifiers only.

## Coverage and absence semantics

- **Known mapped zero:** full parcel support was examined successfully and the union fraction is exactly zero. The available union observation has `known_zero=true`, complete declared-product support, and the explicit limitation that mapped zero is not ecological absence.
- **Partial acquired coverage:** `partial_coverage` / `partial_acquired_coverage`; no parcel-wide observation or zero is asserted.
- **Outside acquired coverage:** `unavailable` / `outside_acquired_coverage`; no observation or zero is asserted.
- **Unavailable source/processing:** `unavailable` / `source_unavailable`; no observation or zero is asserted.

The source cannot prove complete ecological survey coverage. A positive observation means only: this release maps the named main habitat within the stated support.

## Real Oxford results

All 12 existing verification geometries are fully inside the acquired PHI envelope. Eight have mapped main-priority overlap and four are known mapped zeroes.

| Site | Habitat-specific mapped fractions | Any-main-priority union | Source features |
|---|---|---:|---:|
| Port Meadow | LMEAD 98.51%; CFPGM 0.39% | 98.90% | 24 |
| Hook Meadow / Trap Grounds | LMEAD 91.78%; DWOOD 4.77% | 96.55% | 9 |
| Iffley Meadows | LMEAD 78.18%; LFENS 15.43%; DWOOD 1.35%; CFPGM 0.08%; TORCH <0.01% | 95.05% | 35 |
| Pixey and Yarnton Meads | LMEAD 98.39%; DWOOD 0.36%; CFPGM 0.14% | 98.89% | 26 |
| Wolvercote Meadows | LMEAD 96.56%; CFPGM 0.59%; DWOOD 0.20% | 97.35% | 10 |
| New Marston Meadows | LMEAD 73.82%; LFENS 16.04%; DWOOD 4.78%; CFPGM 0.03% | 94.67% | 39 |
| Wytham Woods hillside | No mapped main priority class; one intersecting GQSIG supporting feature | 0.00%, known mapped zero | 1 |
| Westgate shopping centre | None | 0.00%, known mapped zero | 0 |
| Oxford railway station | None | 0.00%, known mapped zero | 0 |
| Seacourt Park and Ride | CFPGM 35.98%; DWOOD 35.24% | 71.23% | 4 |
| Osney Mead industrial estate | None | 0.00%, known mapped zero | 0 |
| Redbridge Park and Ride | DWOOD 10.04% | 10.04% | 1 |

Pixey and Yarnton provides a real overlap check: habitat-specific fractions sum to `0.9889861545743874`, while the union is `0.9889308509893089`; the difference is overlapping geometry counted once in the union. The synthetic exact test is stronger: LMEAD 0.70, DWOOD 0.70 and CFPGM 0.14 produce a union of exactly 1.00 rather than 1.54.

These are engineering/semantic inspection results, not field validation. The full values, per-feature lineage, snapshot IDs and parity assertions are in [real-verification-results.json](real-verification-results.json) and the readable run is in [REAL-VERIFICATION.md](REAL-VERIFICATION.md).

## Snapshot integration

PHI source, raw and feature references, both definition types, per-class observations, the union observation or explicit gap, and their edges are native snapshot members under registry v2. They participate in semantic validation, canonical content hashing, manifest byte hashing, relational lookup and organisation checks.

For every real site, the verification committed a pre-PHI snapshot and a PHI-enriched snapshot. Every pair had different snapshot/content identity; every earlier manifest was re-read byte-identically after the new commit; every enriched manifest round-tripped through validation; and wrong-organisation loading is covered by the focused persistence test. Registry-v1 snapshot content serialization is unchanged, so historical v1 manifests remain valid and immutable.

The compatibility `projection_id` deliberately remains stable for unchanged legacy evidence so the untouched v1 wetland binding preserves missing-placeholder and derived IDs. Registry v2, the PHI-scoped native observation IDs and the complete content hash carry the new evidence identity; the persisted Evidence Snapshot ID therefore changes.

## Wetland and existing-result parity

PHI is not a legacy overlay adapter and is excluded from the legacy `EarthState`. Its raw/source lineage is constructed natively from the retained PHI finding during Land Evidence projection. `wetland_input_binding_v1`, `wetland_restoration_v0_1`, its feature layer, thresholds, weights, gates and model signature are unchanged. PHI does not populate actual wetland extent, habitat condition, irreplaceable habitat, restoration need or suitability.

Across all 12 sites, the pre-PHI and PHI runs have exact equality for:

- every non-PHI finding;
- the complete legacy environmental state;
- the complete wetland result JSON, including observation IDs, derived IDs, state fingerprint, components, scores/bands, evidence summary, missing inputs, review flags and model signature.

The only new evidence is the PHI finding/native Land Evidence family and the resulting new immutable Evidence Snapshot.

## Verification

- authoritative layer metadata, attribute PDF, spatial metadata, real Oxford feature values, all distinct main code/name combinations, feature qualifiers and additional-habitat codes inspected;
- PHI-focused suite: 10 passed on SQLite and 10 passed on PostgreSQL/PostGIS, including each backend's stored-feature query path;
- full Python suite: 147 passed on SQLite and 147 passed on disposable PostgreSQL 17 / PostGIS 3.5;
- additive migration 5 applied on the disposable PostGIS database; migration history contains 1–5 and `features.properties` is JSON;
- 12/12 real-site deterministic replay, source/provenance resolution, non-synthetic check, exact non-PHI finding/state/wetland parity, paired immutable snapshots and reloads passed;
- manual source-geometry sheet checked for Port Meadow, Oxford railway station and Wytham Woods: source polygons align with the stored boundaries, labels come from actual PHI attributes, the developed sample is mapped zero, and Wytham's one GQSIG feature remains supporting/non-priority;
- frontend regression tests: 19 passed; TypeScript check passed; production build passed with the existing large-chunk advisory.

The first unprivileged PostgreSQL command produced 32 setup errors because the sandbox denied localhost access (`Operation not permitted`). The same suite passed in full after authorized local-container access. This was an execution-environment failure, not a database or implementation failure. No product verification remains failed.

The inspection artifacts are [priority-habitats-source-inspection.svg](priority-habitats-source-inspection.svg) and [priority-habitats-source-inspection.png](priority-habitats-source-inspection.png).

## Limitations

PHI does not by itself establish current habitat condition or quality, complete ecological survey coverage, ecological absence at mapped zero, restoration need, restoration suitability, irreplaceability, legal development feasibility, consent, ownership or current field status. Source vintages vary because PHI compiles many contributing datasets. Geometry inherits source positional/generalization limits and one bounded-source geometry required a recorded validity repair. The acquired evidence envelope is Oxford-area, not national, so parcels outside it correctly remain unknown.

## Recommended next iteration

Implement one deterministic national PHI tile-manifest acquisition and coverage resolver, with per-tile immutable hashes and the same current schema/observation contract, so arbitrary English parcels can distinguish full coverage from missing tiles without changing any model, binding or UI.
