# Oxford operational capture library

## Outcome

On 15 September 2026, four fresh captures were acquired in the active
`local-development` organization and verified through the running Data sources
browser. This makes real terrain, surface, spectral and historical weather evidence
available for inspection and future reuse. It improves Terrene's representation
of reality; it does not establish a forecast or assessment result.

| Capture | Requested evidence | Retained availability |
| --- | --- | --- |
| EA terrain, DTM 1 m | Historical composite over Oxford Station context | 1,000,000 / 1,000,000 area cells |
| EA last-return surface, DSM 1 m | Same polygon and coverage profile | 1,000,000 / 1,000,000 area cells |
| Sentinel-2 C1 L2A | 19 June 2025, 11:17:06.796 UTC | 10,003 / 10,003 cells in each of four spectral bands; 2,500 / 2,500 SCL cells |
| NASA POWER / MERRA-2 | 1 January–31 December 2025, UTC, centre point | 365 / 365 days for each of six variables; 2,190 variable-day values |

The raster polygon is a 1,000 m square centred at EPSG:27700 E450508 N206359,
converted to the exact WGS84 coordinates retained in each request. It encloses the
saved Oxford Station boundary. Weather queries the centre at approximately
longitude -1.269702, latitude 51.753653; it does not represent a square-area average.

## Implementation / architecture

Used the existing `backend.acquisition` operator service, immutable organization
storage, registered source adapters, catalogue and detail contracts. No production
code, dependency, migration, API, model or UI changes were necessary.

Prepared a fresh official England BFE coverage profile in the active storage root.
DTM and DSM explicitly share that profile and polygon. Satellite discovery returned
19 compatible candidates on an incomplete page; the selected scene had the lowest
scene-wide cloud percentage among that page (0.247%). Its exact metadata hash was
pinned before acquisition. This is an explicit bounded operator selection, not a
claim to have searched the entire archive or found cloud-free local ground.

Each source used a new idempotency key. DSM's first attempt failed with
`network_failure`; an exact request retry succeeded as attempt 2 and preserved
attempt 1. There are four acquisition rows and five attempts. No earlier
verification capture was copied, moved or assigned to another organization.

## Source

- `environment_agency.lidar_dtm_1m`, adapter `ea_lidar_dtm_wcs_v1`.
- `environment_agency.lidar_dsm_last_return_1m`, adapter `ea_lidar_dsm_wcs_v1`.
- `copernicus.sentinel2_c1_l2a_earthsearch`, adapter `sentinel2_c1_native_window_v1`.
- `nasa.power_merra2_daily`, adapter `nasa_power_daily_point_v1`.

Original provider responses and source provenance are retained by the established
adapters. Source identity, terms and limits remain as documented in
[terrain acquisition](EA-LIDAR-GEOGRAPHIC-ACQUISITION.md),
[surface acquisition](EA-DSM-GEOGRAPHIC-ACQUISITION.md),
[satellite acquisition](SENTINEL2-GEOGRAPHIC-ACQUISITION.md) and
[weather acquisition](HISTORICAL-WEATHER-ACQUISITION.md).

## Evidence semantics

- LiDAR is historical composite elevation in metres relative to Ordnance Datum
  Newlyn. Local survey dates remain unknown. The 1,007 × 1,007 native windows
  include bounding margins; availability counts refer to the requested polygon.
- The explicit read-only DTM/DSM pairing confirms grid compatibility and
  1,000,000 jointly valid area cells. Matching survey dates remain unverified;
  no subtraction, building-height result or model run was produced.
- Satellite blue, green, red and near-infrared retain native 10 m samples; provider
  scene classification remains at 20 m. Non-nodata does not mean clear ground.
  Native windows replay from retained original byte ranges; whole publisher-file
  checksums remain unverified.
- Weather is coarse MERRA-2 reanalysis queried at a point, with temperature,
  precipitation, wind and humidity in their original units. It is neither station
  observation nor farm-scale prediction. Availability is not predictive confidence.
- Capture dates never replace unknown evidence dates. A 2025 evidence-date search
  returns satellite and weather; undated composite LiDAR remains excluded.

## Files changed

- `docs/OXFORD-CAPTURE-LIBRARY.md`: this operational acceptance report.
- `docs/verification/oxford-capture-library-2026-09-15.json`: exact request,
  capture/attempt/hash identities, counts, verification and preserved-history record.
- `docs/CURRENT-STATE.md`: populated active library, acceptance and next boundary.

Raw provider data, local databases, object files, coverage geometry and temporary
operator outputs remain outside Git. The verification record contains bounded
request geometry and metadata, not raster pixels or daily weather series.

## Verification

All four final summaries match fresh-process integrity reads and provider-free
idempotent retries. Catalogue checks verify all four records, the Oxford bounding
filter, capture-day filtering, the two dated records in a 2025 evidence filter and
an empty unrelated organization. Live backend and same-origin proxy GETs return
the same four identities; all eight exact detail reads verify retained artifacts
and preserve `Cache-Control: no-store`.

No application code changed, so frontend builds, unit suites and PostgreSQL suites
were not rerun. Verification targets real acquisition, stored-byte integrity,
running local API/browser behavior and historical preservation. Hosted tenancy and
deployment are not claimed. Final JSON validation and Git diff checks passed.

## Real-data verification

The existing source verifiers passed full retained-byte/summary replay and **39
fresh same-provider sample comparisons**: three DTM cells, three DSM cells,
15 satellite samples across five assets and 18 weather values across six variables
on the first, middle and last requested dates. These checks establish consistency
with the same services, not independent survey, station or scientific validation.

The pairing fingerprint is stable across a fresh-process read. Complete availability
for this square does not establish national coverage or present-day accuracy.

## Browser QA

The active workspace displays four Oxford matches. Each source's detail was opened
and showed verified files and its original availability counts: one million cells
per elevation source, 10,003 cells per spectral band, 2,500 SCL cells and 365 days
per weather variable. Undated LiDAR and point-weather caveats remain visible.
The existing Oxford Analyst brief and five retained scene sources remain visible.
No layout or responsive behavior was changed in this task.

## Historical / compatibility impact

Before acquisition, the active database was backed up outside Git and all existing
table contents and object files were fingerprinted. All 18 tables outside the
acquisition request/attempt tables remain identical, including three Sites, the
original Oxford assessment, one Evidence Snapshot and two ModuleRuns. All 12
pre-existing object files retain their byte hashes.

The existing runtime database configuration was preserved. No historical result,
boundary, source identity, processing version or tenant ownership was rewritten.
The five historical map-scene sources and the new independent captures remain
separate evidence paths; the empty legacy assessment registry is not replaced by
the independent capture count.

## Known limitations

The collection is local development evidence, not national ingestion or hosted
storage. The current runtime data root is an external temporary directory; durable
storage and backups remain an operational follow-up. A fresh clone cannot recreate
these exact captures from Git alone. Original publisher data may change, so a new
capture must have a new idempotency key and any required fresh metadata/profile pin.

The read-only browser exposes evidence details, not raster map rendering or daily
weather charts. No acquisition UI, new assessment binding, derived index, temporal
analysis or climate forecast was added.

## Git

Branch: `data/oxford-capture-library`, based on `feat/acquisition-browser` because
this operation depends on its retained-capture UI and catalogue. The commit records
the acceptance metadata and documentation only; operational data remains private.

## Recommended next task

Establish an authenticated terrain display contract for one retained DTM capture,
with exact capture identity, geographic bounds, units, nodata and rendering
provenance. Verify it against these retained bytes before a subsequent map-layer
UI task. Satellite display, acquisition controls and analytical bindings remain
separate iterations.
