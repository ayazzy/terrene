# CRC pilot data and screening rules

The overlay rules documented below remain the retained V0 evidence layer. The new [Nature Intelligence model](NATURE-INTELLIGENCE.md) consumes canonical observations derived from these overlays and retains their limitations. New imports preserve original assembled source geometry before repair in `source.json` and save prepared geometry separately. Historical snapshots remain unchanged.

Default pilot: a rectangular Oxfordshire-area extract, **[-1.65, 51.50, -0.85, 52.05]** in longitude/latitude. Flood data uses the smaller Oxford corridor **[-1.33, 51.72, -1.22, 51.82]**. Only boundaries fully inside each source’s extract receive covered observations. Polygon selection retrieves complete intersecting source features; it does not download national datasets.

## Authoritative integrations verified 7 September 2026

| Layer | Publisher / access | Latest successful extract | Fitness and limits |
|---|---|---:|---|
| Ancient Woodland (legacy) | [Natural England REST](https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/Ancient_Woodland_England/FeatureServer/0) | 1,903 polygons | Inventory observations only. Revised completed-county data supersedes the legacy inventory. Absence is not proof of no ancient woodland. |
| Ancient Woodland (revised) | [Natural England REST](https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/Ancient_Woodland_Revised_England/FeatureServer/0) | 45 polygons | Completed counties only. CRC does not yet determine county revision completeness. Show both inventories, never sum their overlaps. |
| Sites of Special Scientific Interest | [Natural England REST](https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/SSSI_England/FeatureServer/0) | 143 polygons | Notified SSSIs; excludes proposed sites and impact risk zones. No legal/consent conclusions. |
| Flood Map for Planning | [Environment Agency metadata](https://www.data.gov.uk/dataset/104434b0-5263-4c90-9b1e-e43b1d57c750/flood-map-for-planning-flood-zones1) | 440 polygons (270 FZ2, 170 FZ3), Oxford corridor | Verified EA OGC Features geometry. Combined zones are unioned to avoid double counting. River/sea flood zones ignore defences and are not wetland suitability. |
| OS OpenMap – Local | [OS Downloads API](https://api.os.uk/downloads/v1/products/OpenMapLocal) | Release 2026-04; 148,494 bounded objects | Generalized Building, FunctionalSite, RailwayTrack and RailwayStation objects in EPSG:27700. Source-scale mapped zero is not real-world absence; rail lines remain lines. See [built-world iteration](OPENMAP-LOCAL-BUILT-WORLD.md). |
| EA LIDAR Composite DSM/DTM 1m | [DSM metadata](https://www.data.gov.uk/dataset/cf3f1137-c12b-44a1-a835-e80fe4a60b92/lidar-composite-digital-surface-model-dsm-1m) / [DTM metadata](https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m) | Per-assessment bounded WCS crops | Co-registered historical surface-height evidence for retained mapped buildings. Composite constituents span 2000–2022; vegetation, vehicles, age and footprint generalisation affect estimates. Not current surveyed height. See [building-height evidence](EA-LIDAR-BUILDING-HEIGHTS.md). |

Natural England datasets and the Environment Agency flood-zone metadata identify Open Government Licence v3. See [AWI licence and metadata](https://www.data.gov.uk/dataset/9461f463-c363-4309-ae77-fdcd7e9df7d3/ancient-woodland-england), [SSSI licence and metadata](https://www.data.gov.uk/dataset/5b632bd7-9838-4ef2-9101-ea9384421b0d/sites-of-special-scientific-interest-england3), and [OGL v3](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Attribution: © Natural England 2026; contains Ordnance Survey data © Crown copyright and database right 2026. The complete source-specific woodland attribution is retained in each metadata snapshot. Source websites remain the authority for terms and changes.

## Repeatable imports

Run `python -m backend.import_data` with the same database/environment as API and worker. For Natural England ArcGIS sources, the pipeline requests the full intersecting object-ID list, downloads batches of 100, checks feature counts, validates geometry, and saves an immutable version. Each successful version records retrieval time, endpoint, bbox, count, source edit metadata, checksum, attribution and limits. Source snapshots are stored once per version in local object storage or R2. Features are shared database records, indexed by dataset and spatial geometry. Failed runs produce explicit unavailable versions; the latest failed import is **not** silently replaced by an older success. Existing assessments retain their original pinned versions.

The first SSSI import failed on invalid source geometry. The subsequent import explicitly used Shapely `make_valid` on six reference polygons, retaining original geometries, reason and normalization method in the metadata snapshot. Nonpolygon components are excluded. The limitation is exposed in evidence and reports. **User boundaries are never repaired.** All reference features are validated before the import transaction commits.

Run `python -m backend.import_data --only flood` to refresh the flood source independently. The adapter uses the [EA OGC Features collection](https://environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1/collections/Flood_Zones_2_3_Rivers_and_Sea), its advertised canonical items URL and CRS84 coordinates. It verifies pagination, stable total counts, unique feature IDs, zone values, geometry types and response CRS, and rejects foreign or altered continuation links. Limits are 50,000 features and 128 MiB. The broader pilot exceeded the byte limit; the successful smaller corridor import downloaded 10,932,020 bytes across two pages. Outside that corridor, flood coverage remains unknown.

Run `python -m backend.import_data --only built_world --openmap-archive PATH` to import the pinned official OpenMap Local archive. The importer first verifies the live release/artifact record, then exact archive identity, shapefile schemas, CRS, source UUIDs, feature codes and code-list values. It retains the original ZIP byte-for-byte and indexes WGS84 geometry for candidate lookup while preserving source geometry in EPSG:27700. Only the Oxford support and the bounded railway search halo are retained.

The successful flood version `f877fc6b-de26-4085-a244-4cbcf1877c2f` contains 440 polygons. 91 invalid reference polygons were normalized with `make_valid`; original geometries and reasons are retained in its metadata. Attribution: © Environment Agency copyright and/or database right 2025. All rights reserved. Open Government Licence v3. The immutable snapshot records counts, page URLs, timestamps, coverage, checksum and import method. Failed attempts and older assessments remain preserved. No flood fixtures are substituted into real runs.

## Method and interpretation

- Boundary validation accepts one WGS84 Polygon or MultiPolygon, including one-feature FeatureCollections. Rejects invalid/self-intersecting/empty geometry, unclosed rings, non-2D coordinates, oversized uploads and unsuitable coordinate ranges. No silent snapping, simplification or repair.
- EPSG:4326 input is transformed with pyproj into EPSG:27700. Area is planar square metres / 10,000. Transform accuracy depends on installed PROJ grids; v0 is desk screening, not a cadastral measurement.
- PostgreSQL `ST_Intersects` and GiST select candidate reference geometry server-side. Shapely transforms, unions and intersects it against the input boundary. Unioning prevents double counting within a layer. Touch-only intersections measure zero hectares.
- Rule `crc-screening-1`: overlap above zero → geographic constraint to investigate, with the question of ecological implications and consents. No overlap → observation limited to that inventory/version. Missing source or coverage → measured result `null`, category missing, request further data. No overall score.
- Rule `crc-flood-1`: combined present-day river/sea Flood Zones 2 and 3 overlap prompts flood-risk specialist review. This ignores benefits of defences; Zone 1 is not mapped. No overlap does not establish no flood risk, and overlap does not establish wetland or restoration suitability. No climate-change projections or functional-floodplain classification are inferred.
- Legacy and revised ancient woodland are separate measured observations, **not two independent confirmations of absence**. “Covered” means the extraction covered the boundary, not a complete ecological inventory.
- Field habitat/condition survey, tenure/consents and local recovery/connectivity checks are explicit next steps. No automated habitat-condition, BNG-unit or suitability predictions.

Each overlay finding retains source URL, immutable dataset ID, retrieval date, boundary version, method/rule versions, measured hectares, coverage, limitations, attribution and clipped overlap geometry. Assessments snapshot the boundary and name at submission; later edits do not alter them. Reports use that saved evidence and label the current user review status separately at export time.

## Examples and synthetic content

`port-meadow-reference.geojson` is the publicly mapped Natural England SSSI boundary, used as a real reference geometry. It is not an offered site, an ownership assertion or a restoration recommendation. Its measured v0 area is 167.1509 ha and SSSI overlap is 100%.

`synthetic-boundary.geojson` is explicitly synthetic and only demonstrates edit/history behavior. The synthetic drawing uses **real** imported reference layers; its land-opportunity premise is fictional. Automated tests use a separate temporary database and explicit synthetic one-hectare features, never the real catalog.


## Real environmental acquisition (8 September 2026)

The wetland worker now also acquires EA native 1m DTM, OS Open Rivers and ESA WorldCover 2021 v200. These are stored as immutable native assets/parcel subsets and canonical observations; they do not increase the legacy overlay-layer completeness counter. Their availability is shown separately in the model data-coverage summary. Exact calculations, source limitations, observation dates, licence attribution and the registered-access soil gap are documented in [Nature Intelligence](NATURE-INTELLIGENCE.md).

EA WWNP floodplain reconnection geometry is retained only for [independent verification](REAL-VERIFICATION.md), never as a scored source.
