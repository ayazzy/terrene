# OS OpenMap – Local built-world iteration

Verified and implemented 10 September 2026. This is a bounded CRC Earth change. It adds source-backed mapped objects, parcel relationships and reusable observations; it adds no interpretation, suitability score, UI feature or wetland-model input.

## Source

The live [OS Downloads API product](https://api.os.uk/downloads/v1/products/OpenMapLocal) identified **OS OpenMap – Local release `2026-04`** as current during implementation. CRC pins the official `SP` ESRI Shapefile artifact:

- file: `opmplc_essh_sp.zip`
- access: [OS Downloads API SP artifact](https://api.os.uk/downloads/v1/products/OpenMapLocal/downloads?area=SP&format=ESRI%C2%AE+Shapefile&redirect)
- size: 132,851,994 bytes
- official MD5: `fce94d990c044ae6316e566b418224f6`
- independently recorded SHA-256: `1e1654017820ef8cf63a93d16a148849cecb651c3e5cb8f153840df931f91bd6`
- source CRS: British National Grid, **EPSG:27700**
- source schema identity: `os_openmap_local_1_0_shapefile_2026_04`
- GML schema cross-reference: [OSOpenMapLocal.xsd 1.0](https://www.ordnancesurvey.co.uk/xml/open/oml/1.0/OSOpenMapLocal.xsd)
- technical definition: [OS OpenMap – Local technical specification](https://docs.os.uk/os-downloads/products/maps-and-imagery-portfolio/os-openmap-local/os-openmap-local-technical-specification)
- licence: OS OpenData under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
- attribution: “Contains Ordnance Survey data © Crown copyright and database right 2026.”

The importer live-checks the product release and artifact metadata, then verifies byte size, MD5 and SHA-256 before use. It stores the official ZIP immutably. Module execution never requests the network.

The admitted shapefiles were inspected directly, rather than inferred from documentation:

| Source feature | Shape | Fields in the 2026-04 Shapefile | Full SP records | Bounded retained records |
|---|---|---|---:|---:|
| Building | `POLYGONZ` | `ID C(38)`, `FEATCODE N(5)` | 1,033,958 | 146,632 |
| FunctionalSite | `POLYGONZ` | `ID C(38)`, `DISTNAME C(120)`, `SITETHEME C(21)`, `CLASSIFICA C(90)`, `FEATCODE N(5)` | 2,861 | 446 |
| RailwayTrack | `POLYLINEZ` | `ID C(38)`, `CLASSIFICA C(45)`, `FEATCODE N(5)` | 6,369 | 1,389 |
| RailwayStation | `POINTZ` | `ID C(38)`, `DISTNAME C(150)`, `CLASSIFICA C(65)`, `FEATCODE N(5)` | 159 | 27 |

The import validates UUID source IDs, exact field layouts, shape types, EPSG:27700 `.prj` files, admitted feature codes and values from the official [Site classification](https://www.ordnancesurvey.co.uk/xml/codelists/map/SiteClassificationOML.xml), [Site theme](https://www.ordnancesurvey.co.uk/xml/codelists/sites/SiteTheme.xml), [railway-track classification](https://www.ordnancesurvey.co.uk/xml/codelists/map/RailwayTrackClassificationOML.xml) and [railway-station classification](https://www.ordnancesurvey.co.uk/xml/codelists/map/RailwayStationClassificationOML.xml) code lists.

OpenMap Local is generalized contextual mapping at nominal 1:10,000, with a recommended viewing range of 1:3,000–1:20,000. Its building geometry can amalgamate structures and is not a legal or engineering footprint. FunctionalSite describes mapped classification, theme and name, not current operational status. RailwayTrack is a line representation, may break beneath obstructing detail, and omits some sidings and travelling-structure tracks. A mapped zero therefore means only that this release contains no qualifying mapped feature at this scale.

## Objects admitted

Four deliberately narrow object types were added to `land_evidence_v1` registry v3:

| CRC Earth object | Preserved source content | Reason admitted |
|---|---|---|
| `MappedBuildingObject` | UUID, feature code, unmodified 2D BNG polygon geometry, release, geometry fingerprint and source/raw lineage | Represents an identifiable generalized mapped built entity independently of any summary score. |
| `FunctionalSiteObject` | The above plus distinctive name, site theme and classification | Retains meaningful mapped function instead of flattening hospitals, education and transport sites into “developed”. |
| `RailwayTrackObject` | UUID, feature code, classification and original BNG line geometry | Preserves the source’s linear semantics; no fictional surface footprint is created. |
| `RailwayStationObject` | UUID, feature code, distinctive name, classification and BNG point | Represents the actual point feature supplied by OpenMap Local. |

This is a discriminated typed union, not a generic ontology or knowledge-graph facility. Object IDs are deterministic from the independent built-world projection scope, source object identity, release and geometry fingerprint.

## Relationships

`ParcelObjectRelationship` links one immutable parcel boundary to one admitted object. Every record has a deterministic ID, explicit geometry semantics, EPSG:27700 support, processing version `crc_openmap_local_spatial_v1`, measurements where meaningful, and source/raw provenance.

- Polygon `contained_within`: the parcel covers the complete mapped polygon. It carries overlap area plus parcel and object fractions.
- Polygon `overlaps`: polygon interiors share positive area, but the complete object is not covered by the parcel. It carries the same measurements.
- Polygon or line `touches`: only boundary contact is present. It carries no area or in-parcel length.
- Railway line `crosses`: the OGC crossing predicate is true and the line passes through parcel interior.
- Railway line `intersects`: there is positive in-parcel line length, but the feature is neither covered nor classified as crossing.
- Railway line `contained_within`: the parcel covers the complete source line.
- Station `contained_within` or `touches`: the point is in parcel interior or on its boundary.
- Rail object `minimum_distance`: planar Euclidean parcel-to-object distance, asserted only when the complete bounded 5,000 m source search is covered.

Calculations use a declared 1 cm BNG precision grid to remove sub-millimetre WGS84↔BNG round-trip noise. Persisted source geometry remains unchanged. If the 5 km halo crosses the retained SP/Oxford support boundary, CRC emits a `partial_search_coverage` gap instead of a possibly false minimum.

## Derived evidence

Five independent definitions are available; no universal `infrastructure_fraction` is introduced.

| Definition | Measurement |
|---|---|
| `built.building.mapped_overlap_fraction` | Area of the spatial union of parcel-clipped Building polygons / parcel area. |
| `built.functional_site.mapped_overlap_fraction` | Area of the spatial union of parcel-clipped FunctionalSite polygons / parcel area. |
| `transport.railway_track.mapped_length_within` | Length of the spatial union of clipped RailwayTrack lines; touching boundary lines contribute zero. |
| `transport.railway_track.distance_min` | Minimum mapped track distance within a complete 5 km search. |
| `transport.railway_station.distance_min` | Minimum mapped station-point distance within a complete 5 km search. |

Each observation retains the full-precision numerator, denominator where applicable, units, aggregation method and supporting object IDs. Polygon and line spatial unions prevent double counting. A fully covered empty object class creates a known mapped zero; partial, unsupported, unavailable, acquisition-failed and processing-failed states do not.

## Oxford results

The complete 12-location record, including every object, relationship, observation, gap and source comparison, is in [Real Oxford parcel verification](REAL-VERIFICATION.md) and [the machine-readable results](real-verification-results.json).

The most informative results were:

- **Westgate:** 13 mapped Building objects; 7 overlap and 6 are contained; unioned overlap is **43.3473%**. WorldCover maps **95.32%** built-up, demonstrating useful coexistence rather than forced agreement. No FunctionalSite overlaps the sample.
- **Oxford station:** 5 Building objects and **30.4075%** building union; 2 overlapping FunctionalSites and **30.9793%** functional-site union. The sites retain `Bus Station / Road Transport` and `Said Business School / Education / Higher or University Education`. Seven track objects yield **279.31 m** of unioned line within the parcel, and the mapped Oxford Railway Station point is inside it.
- **Osney Mead:** 11 Building objects and **34.1152%** union overlap, alongside WorldCover **99.29%** built-up. The difference reflects generalized building polygons versus a raster land-cover class.
- **Port Meadow:** known mapped zero Building and FunctionalSite overlap, WorldCover **0.07%** built-up, and PHI **98.90%** union overlap. The nearest mapped track is 6.855 m under a complete search; no line is converted to area.
- **Seacourt Park & Ride:** known mapped zero Building and FunctionalSite overlap despite WorldCover **22.04%** built-up and PHI **71.23%** union overlap. This is reported as an OpenMap Local source/scale limitation; no rule is manipulated to force an expected object.
- **Redbridge Park & Ride:** known mapped zero Building and FunctionalSite overlap, WorldCover **28.47%** built-up and PHI **10.04%** union overlap. Parcel-object coverage is full, but rail minimum distances are withheld because the SP acquisition does not cover the complete 5 km halo.
- **Iffley Meadows:** likewise has full parcel-object coverage and mapped-zero building/site observations, while rail distances are explicit partial-coverage gaps.

All other site-level results are retained in the linked report. No verification label or expected site type entered a processing rule.

## CRC Earth implication

The approach proved useful enough to extend later: CRC can preserve individual mapped objects and classifications, inspect parcel-to-object topology, and derive reusable measurements without erasing identity. Westgate, Oxford station and Osney Mead show positive object evidence; Port Meadow shows useful mapped-zero semantics; Seacourt and Redbridge show why source disagreement and coverage gaps must remain first-class.

WorldCover, PHI, flood and OpenMap Local remain distinct evidence families. The change creates no feasibility interpretation. In particular, built-world evidence does not populate legacy `human.infrastructure_fraction`.

## Snapshot and history parity

The smallest persistence extension keeps objects and relationships inside the canonical immutable snapshot manifest and adds only generic membership/reference catalogue entries. It does not introduce a graph database or a new ontology table family.

For each Oxford boundary, verification committed the PHI-era pre-built snapshot, retained its manifest bytes, then committed the built-world-enriched registry-v3 snapshot. Every enriched snapshot received a different deterministic snapshot/content identity; every old manifest remained byte-identical; every new manifest passed load and full validation; organisation-scoped reads rejected another organisation.

`wetland_input_binding_v1`, wetland features, configuration, thresholds and `ModuleRun` code are unchanged. Native PHI and built-world findings are excluded from the legacy `EarthState`. The pre-built and enriched states and wetland outputs were exactly equal for all 12 locations, and the established immutable ModuleRun regression suite remained exact. Existing WorldCover and PHI observations were unchanged and coexist in registry v3.

## Verification

- Direct inspection of the official 132,851,994-byte archive, all four admitted schemas, CRS declarations, source IDs, feature codes and real classifications.
- Real SQLite import of 148,494 bounded objects from the retained archive and deterministic analysis of all 12 Oxford locations.
- Synthetic tests for UUID/source identity, multiple objects, polygon intersection, union without double counting, touch versus overlap, line touch/cross/contain/intersect behavior, line-union length, FunctionalSite classification, mapped zero, incomplete rail halo, unavailable/partial/outside source, WorldCover and PHI coexistence, immutable snapshot identity/history, organisation isolation and unchanged wetland binding.
- Full backend suite: **160 passed** on SQLite and **160 passed** on disposable PostgreSQL 17/PostGIS 3.5.
- `npx tsc --noEmit` passed, and the Sites/Vinext production build completed. This iteration modifies no UI.

## Recommended next task

Implement one versioned, non-scoring CRC Reasoning adapter that consumes the new built-world observations and emits only an inspectable human-review context record, with explicit rules for source disagreement and missing coverage; do not change wetland v0.1.
