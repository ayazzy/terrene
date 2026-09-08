# Verification record — 7 September 2026

## Automated

- **28 tests passed on SQLite** in a separate temporary database.
- **28 tests passed on PostgreSQL 17 / PostGIS 3.5** in the isolated `crc_test` database.
- Verified EPSG:27700 one-hectare area and actual union/intersection, invalid/unclosed/out-of-range boundaries, missing coverage as null, pinned dataset and boundary versions, duplicate submissions, historical report content and review decisions.
- Verified exclusive claims, expired-lease recovery, fencing of stale workers, delayed retry followed by success, bounded final failure and expired third-attempt termination.
- Verified tenant access for lists, mutations, jobs, assessments, report downloads and original boundary downloads. Verified forged JWT rejection and valid ES256 signed sessions for different organizations (including hostile user_metadata). Hosted JWKS is mocked with a real generated signing key in this test; live Supabase is not provisioned.
- TypeScript (`npx tsc --noEmit`) and production build (`npm run build`) passed. The generated React/Vinext/Vite and Cloudflare packages were upgraded together to compatible patched versions after dependency advisories were found. Final npm installation reported **zero vulnerabilities**.
- FastAPI/Starlette test-client deprecation warnings remain; no test failures.

## Real imports and persisted workflow

- Successful bounded extracts: 1,903 legacy woodland polygons, 45 revised woodland polygons and 143 SSSI polygons. Six SSSI source geometries were normalized with explicit audit records; an earlier failed import remains recorded.
- Initially, flood-zone geometry was unavailable and explicitly shown as unknown, never zero. The subsequent verified import is recorded below.
- Created a boundary by clicking four map vertices, saved it, refreshed the browser and verified persistence.
- Uploaded the real public Port Meadow SSSI MultiPolygon through the browser file chooser. Saved and screened it: **167.1509 ha**, **167.1509 ha SSSI overlap (100%)**, no overlap with the imported woodland layers, flood unknown.
- Changed Port Meadow's review status to Investigate and verified that decision after refresh.
- Migrated the development records from SQLite to local PostGIS without deleting the source database. The final running API and worker use PostGIS.
- Uploaded an explicitly synthetic replacement boundary for the drawing example. UI immediately displayed the old assessment as historical (v1 versus v2).
- Ran v2 through the real Postgres worker: **88.7517 ha** area (UI 88.75), compared with original **98.3398 ha** (UI 98.34). SSSI overlap changed from **46.05 ha** (UI) to **41.26 ha** (UI). Both assessments remain in History.
- Selected the two sites and visually inspected the compact comparison: explicit areas, per-layer overlap, unknown flood data and independent review statuses.

## Browser and report QA

- Inspected both the default narrow browser view and desktop layout. Fixed a MapLibre container sizing issue and an inherited tab-layout issue. Excluded local report/data files from Vite watching so saving reports no longer reloads the app. Verified the documented `scripts/dev.sh` startup against persisted PostGIS data.
- Checked the browser bundle: no local database password, database connection string or privileged R2 configuration is included.
- MapLibre raster map, zoom, boundary drawing and undo are implemented. Exact server geometries use MapLibre-projected SVG paths; selected SSSI geometry is visibly highlighted, including the MultiPolygon boundary's hole. Inspected the rendered path attributes and evidence version details.
- Findings show source, retrieval time, immutable dataset ID, boundary version, method, rule, measured hectares, coverage and limitations.
- Report preview renders the saved assessment in an iframe, including all four source entries, exact measurements, historic boundary information when applicable and limitations. The review decision is explicitly labelled as current at export.
- HTTP report export returned 200 and a complete self-contained HTML attachment. Compared all source URLs, dataset IDs and area with the saved assessment, and saved `docs/example-report.html`.
- The in-app browser did not emit a download event for blob HTML links during automation; the direct download anchor and printable preview are present, and the authenticated report response/file content is verified. Native download/print-dialog completion was not claimed.
- WebMCP `list_crc_sites`: verified registration/schema, successful read-back and intentional rejection of unexpected arguments without changing records.

## Not verified / deferred

- Live Render deployment, Supabase hosted sign-in, R2 connectivity/private bucket permissions and external cross-organization acceptance require actual service configuration. No public or disconnected frontend was published.
- AWI county-revision resolution, ecological suitability, distance metrics and definitive BNG analysis are not implemented.
- R2 implementation and hosted startup requirements exist; storage was exercised with development files. Database migration, geometry indexes and worker paths were exercised with real local PostGIS.

## Flood integration follow-up

- Imported 440 real Environment Agency Flood Zones 2 and 3 polygons for the Oxford corridor [-1.33, 51.72, -1.22, 51.82]. Recorded 270 FZ2 and 170 FZ3 features, 10,932,020 downloaded bytes and 91 explicitly audited source geometry normalizations. The larger pilot exceeded the bounded download limit and remains a recorded failed attempt.
- All 28 tests passed on both SQLite and PostgreSQL/PostGIS. Added pagination/provenance success and malformed count, duplicate, zone, CRS, continuation-link and byte-limit failures. Added flood rule, union/no-double-counting and failed-refresh/history checks.
- Browser showed the newer-reference-data notice on the original Port Meadow assessment. Ran screening through the UI: completed with 4/4 layers covered, **162.20 ha combined flood overlap (97.04%)**. Evidence detail displays the actual source, import extent/method, pinned version, rule, attribution and limitations.
- Port Meadow assessment `a78b40e9-7159-4a36-91c7-5ed134be8c07` preserves boundary v1; earlier partial assessment `d0a5100a-db85-45f3-88f2-91a47ffec2a6` still retains its original unknown flood finding. Updated `docs/example-report.html` from the new authenticated report endpoint.
- Verified the flood SVG overlay is rendered with a nonempty geometry path and visually inspected the map. Opened the updated printable report in the browser and confirmed measurements, source version, bounded extent, import method, attribution and limitations. TypeScript and production build passed after the flood changes.
- The synthetic v2 example also completed with 4/4 sources: 88.6012 ha combined flood overlap (99.83%), assessment `c09e2fb3-0f46-4b1e-b18b-0a1f1bac48db`. Earlier versions remain saved.

## Nature Intelligence v0.1 — 8 September 2026

- Preserved the V0 application and added CRC Earth Schema, four adapters for existing layers, explicit raw/normalized/derived states, provenance, derived features and the versioned deterministic wetland model. Added the Wetland model parcel tab, evidence lineage inspector, JSON audit download and model-aware saved HTML reports.
- **63 tests passed on SQLite and 63 on PostgreSQL/PostGIS**, including all 28 prior tests. New tests verify canonical units/bounds, source mapping/fallback, provenance serialization, constituent missing-data propagation, deterministic scoring, expected sensitivity, favourable/unsuitable/pristine-wetland conditions, ecological safeguards, conservative constraint scoring, pinned configuration, original-before-repair preservation, additive migrations and unchanged historical outputs.
- TypeScript and the production build passed. The new `app/nature-panel.tsx` passes targeted lint. Full-project lint remains failing on pre-existing scaffold/V0 issues (vendored component accessibility rules, legacy `any` types and React-effect warnings); these were not suppressed or represented as passing. Existing FastAPI/Starlette test-client deprecations and a frontend chunk-size build warning remain.
- Applied additive migration 2 to the local PostGIS database and restarted the existing API/worker with the upgraded code. The frontend remains on its existing localhost preview.
- Verified a real run through the frontend's same-origin API proxy for the saved **Port Meadow — public reference site**, assessment `18054630-584d-473d-8d04-653c4f2ca268`. Job completed with 4/4 imported overlay layers. The wetland model separately reported **INSUFFICIENT_DATA**, no overall numeric score, data-confidence index **3.3/100**, four raw source references and eight normalized/derived observations. All parent and raw-source references resolved within the saved state.
- The partial physical index (97.0, only 17.5% weighted input coverage) and hydrological proxy (97.0, 50% input coverage) are explicitly partial; they do not unlock a ranking. Terrain, soil, cover/condition, distance and implementation measurements remain missing. These indices are based on available flood context only and do not establish physical suitability.
- The model specification matched the job's pinned signature. The saved report includes the model, missing data, configuration and complete provenance. Both prior Port Meadow assessment results were compared before/after and remained identical.
- No new browser interaction/visual QA was performed in this iteration; the request asked for implementation and tests. Prior browser QA entries above describe V0 only. The updated route was checked for successful server compilation/HTTP response.
- No new live source data or synthetic production measurements were imported. Raw-before-repair behavior was tested with isolated synthetic invalid geometry; existing immutable provider snapshots were not rewritten.
- Hosting remains unconfigured: the private Sites project has no runtime environment entries, including no `CRC_API_URL`. The external Render/Supabase/R2 path was not deployed or revalidated, and a disconnected frontend was not published.

## Real environmental inputs — 8 September 2026

- Retained architecture and all 63 previous tests. **98 tests pass on SQLite and 98 on isolated PostgreSQL/PostGIS `crc_test`**, including real captured EA DTM, OS river and ESA WorldCover fixtures. No synthetic fixture is selected by production acquisition.
- New checks cover analytic Horn slope/units, nodata neighbourhoods, parcel holes and full raster/halo coverage, terrain statistics, immutable source checksums, exact mapped river distance/buffers/intersection, conservative land-cover semantics, categorical soil support without fake permeability, mapped-wetland-zero safeguards, age/quality semantics, source failures, assessment-specific source replay, refresh pinning, benchmark completeness and deterministic results.
- TypeScript, targeted `app/nature-panel.tsx` lint and the production build pass. Existing FastAPI/Starlette and Rasterio/Affine deprecation warnings remain. The existing frontend chunk-size warning remains; unrelated lint and bundle work were not undertaken.
- Ran 12 real Oxford locations: six actual Natural England SSSI polygons and six clearly labelled sample windows at real developed/hillside locations. [Full before/after report](REAL-VERIFICATION.md), [JSON](real-verification-results.json), [exact boundaries/expectation sources](real-verification-sites.geojson). Every run passed deterministic replay, non-synthetic-input assertions and raw/parent provenance resolution.
- At every example, required-input availability improved **1/10 → 5/10**. These counts exclude optional habitat proximity; all scored-input availability is 1/11 → 5/11. **All 12 overall rankings remain INSUFFICIENT_DATA**. Soil drainage, actual wetland extent/condition, complete infrastructure and irreplaceable-habitat evidence remain missing; generic grassland also cannot establish restoration need. No thresholds or completeness gates were weakened.
- Port Meadow: mean elevation **57.528 m**, mean slope **1.176°**, native DTM 1m, 1,671,506 parcel cell centres, complete valid elevation/slope cells. Mapped watercourse intersects the parcel; **23.374%** lies within 100m of the mapped network. ESA 2021 dominant class is grassland; its **0.893%** herbaceous-wetland class is explicitly not actual total wetland extent. Combined data-support index improves **3.3/100 → 20.3/100**, distinct from 50% required coverage. Physical component is VERY_HIGH on 70% input coverage; soil remains absent.
- The six floodplain examples have very high partial physical components; Wytham's hillside is low. Osney Mead combines high partial physical potential and **99.3% mapped built-up cover**, demonstrating why physical potential cannot substitute for restoration opportunity. The dated land-cover source under-represents built-up class at the Seacourt/Redbridge parking samples; discrepancies are documented without tuning to them.
- Downloaded a complete bounded independent EA WWNP reconnection benchmark: **294 features**, **199,403 bytes**, seven invalid raw reference geometries retained and audited before working-copy repair. Seven example sites overlap; five do not. It is binary reconnection mapping, not an official high/low wetland score. Benchmark input never enters CRC inference.
- Restarted the identified local API and worker with this implementation; existing frontend remains at localhost:3000. Submitted Port Meadow through the frontend's same-origin API proxy, assessment **`71f31c26-3903-4a30-8586-a869d8fd9a93`**. Job completed with the new pinned source profile and 5/10 required inputs. Its saved model exactly reproduces from its saved state/specification.
- Exported the saved report through the authenticated/development-scoped same-origin endpoint: HTTP 200, model/uncertainty/source evidence retained in [Port Meadow report](port-meadow-wetland-report.html). Hashes of all three prior Port Meadow assessment results match before/after. No existing boundary or review decision was changed.
- No new browser interaction or visual QA was claimed. HTTP/proxy/report flow, compilation and model evidence were checked. The private Sites reservation still has no runtime `CRC_API_URL`; external backend/auth/storage hosting remains unconfigured and no disconnected frontend was published.
- User confirmed no existing LandIS access and requested the soil gap remain documented. [Current access findings](SOIL-DATA-GAP.md) distinguish the April 2026 free-access release from the still-required registration/licence step. No terms were accepted and no account was created.
