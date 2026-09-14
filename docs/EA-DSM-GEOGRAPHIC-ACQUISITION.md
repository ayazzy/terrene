# Independent EA surface-model acquisition and explicit terrain pairing

This iteration adds independent last-return DSM acquisition and a read-only
compatibility check against a specifically selected retained DTM capture. It
extends the [existing terrain acquisition path](EA-LIDAR-GEOGRAPHIC-ACQUISITION.md)
without changing legacy terrain/height calculations or automatically running a model.

## Source and evidence semantics

Source: `environment_agency.lidar_dsm_last_return_1m`.
Adapter: `ea_lidar_dsm_wcs_v1`.
Processing: `ea_dsm_native_cell_coverage_v1`.

The [official EA DSM catalogue](https://www.data.gov.uk/dataset/cf3f1137-c12b-44a1-a835-e80fe4a60b92/lidar-composite-digital-surface-model-dsm-1m)
describes a historical composite surface containing terrain, buildings,
vegetation and vehicles. Its published grid is 1 m, with metre elevations
referenced to Ordnance Datum Newlyn and OGL terms. Surface elevation is not
height above ground, and a matching composite label does not prove a common
local survey date.

The registered endpoint is
`https://environment.data.gov.uk/spatialdata/lidar-composite-digital-surface-model-last-return-dsm-1m/wcs`,
with coverage
`9ba4d5ac-d596-445a-9056-dae3ddec0178__Lidar_Composite_Elevation_LZ_DSM_1m`.
The observed metadata has the same erroneous radiance unit tag as DTM; metre/ODN
meaning is bound to the DSM catalogue and changed tags require explicit review.
Unknown local survey date, observation time and immutable release remain unknown.

## Acquisition contract

Use `geographic_acquisition_request_v1` with the DSM source and adapter and a
prepared `ons_england_dec2024_bfe_v1` profile hash. Shared geometry supports the
UK, but this publisher path establishes bounded England support only. Each new
source or changed request needs its own idempotency key. DSM never substitutes
for a failed DTM request or vice versa.

Acquisition retains original before/after WCS XML, original native GeoTIFF bytes,
and the raster cell-availability summary. Source identity, required metadata,
single-band float32 EPSG:27700 1 m grid, exact window bounds, nodata and numerical
checks apply to DSM. The two coverage descriptions must agree. Original received
artifacts remain attached to failed attempts where available.

Limits remain 4 million pixels, 4,096 pixels per axis, 32 MB per decoded response,
36 MB total, 2 MB per metadata response and 180 seconds total network time.
The complete/partial/no-valid-cell distinction, polygon holes, 3 m window margin,
private immutable storage, retries and integrity reads follow the DTM contract.
Terrene does not clip, resample, fill pixels or execute a height model here.

## Explicit pairing

`read_lidar_pair(org, dtm_acquisition_id=..., dsm_acquisition_id=...)` returns
`lidar_pair_compatibility_v1`. It is a trusted internal, read-only operation:

1. Integrity-read two successful captures in the supplied organization and
   require the explicit DTM and DSM adapter roles.
2. Require identical canonical request geometry and the same coverage-profile
   hash; even separately prepared profiles with similar geometry are not silently
   treated as equivalent in v1.
3. Validate retained source metadata, replay each raster's coverage from original
   bytes, and require matching grid, resolution, extent, unit and vertical datum.
4. Count cells valid in both rasters inside the polygon. Report joint missing
   cells and cells valid in only one source. Disjoint valid masks can produce
   `no_valid_pairs` despite both individual rasters containing data.
5. Return exact capture/attempt/manifest/raster references and a deterministic
   compatibility fingerprint, with `temporal_compatibility` explicitly
   `unverified_local_survey_dates` and `same_survey_confirmed` null.

This creates no pair entity, Evidence Snapshot, ModuleRun or binding and makes
no provider request. `grid_compatible` is not scientific suitability or a
building-height result. Joint availability is not confidence. A later difference
model must state its interpretation and assumptions in a separate versioned contract.

## Operator workflow

Use the existing private storage/database configuration. An existing compatible
England BFE profile can be reused; setup remains available explicitly:

```sh
.venv/bin/python -m backend.acquisition sources --adapter-version ea_lidar_dsm_wcs_v1
.venv/bin/python -m backend.acquisition prepare-coverage --adapter-version ea_lidar_dsm_wcs_v1
```

Create a new request with `source_id=environment_agency.lidar_dsm_last_return_1m`,
`adapter_version=ea_lidar_dsm_wcs_v1` and a new idempotency key. To check a pair,
use the exact same area and profile as the chosen DTM request. Current-publication
mode remains required; no historical/date-range selection is added.

```sh
.venv/bin/python -m backend.acquisition acquire --org YOUR_ORG --request /private/path/dsm-request.json
.venv/bin/python -m backend.acquisition read --org YOUR_ORG --id DSM_ACQUISITION_ID
.venv/bin/python -m scripts.verify_geographic_acquisition --org YOUR_ORG --id DSM_ACQUISITION_ID
.venv/bin/python -m backend.acquisition pair-lidar --org YOUR_ORG --dtm-id DTM_ACQUISITION_ID --dsm-id DSM_ACQUISITION_ID
```

Successful retries retain their original capture, so obtain a new publication
capture with a new key. The terrain-only internal `fetch_dtm` entry point and
default DTM helpers remain compatible; DSM selection is always explicit.

## Verification and compatibility

Verified on 15 September 2026 in Europe/London; record timestamps are UTC:

| Sample | DSM grid | Valid requested-area cells | Jointly valid DTM/DSM cells | Independent source check |
| --- | --- | ---: | ---: | --- |
| Oxford | 167 × 167, native 1 m | 25,600 | 25,600 | Three separate DSM one-cell requests matched |
| East Anglia | 167 × 167, native 1 m | 25,600 | 25,600 | Three separate DSM one-cell requests matched |

Both DSM coverage summaries replay from retained bytes. Fresh-process readback,
native checksums, retries with provider access disabled and pair fingerprints
match. Pairing/retries add no acquisition rows. All eight earlier DTM and
England/Scotland vector capture summaries remain unchanged, and isolated legacy
Site, assessment, dataset/feature, Evidence Snapshot and ModuleRun tables remain
empty. No raw rasters, XML files, local databases or storage keys are tracked.

The affected suites pass **171 tests on SQLite and 171 on PostgreSQL/PostGIS**,
including **23 new DSM/pairing tests**. Tests cover source/role confusion, grid,
unit and extent failures, retries, corruption, organization boundaries, different
areas/profiles, joint nodata masks, genuine zero values, holes, no-write reads,
CLI use and independent DSM sample mismatches. Existing dependency warnings
remain. Python compilation and diff checks pass; no frontend/deployment changes
were made, so browser QA and hosted acceptance were not run.

See the [small verification record](verification/ea-lidar-dsm-2026-09-15.json)
for exact inputs, sample values, hashes and pairing results. Samples do not
establish national completeness, survey accuracy or a second full raster download.
No current building-height, change-detection or future-climate claim follows.

## Next bounded candidate

Dated satellite imagery is next in the data-family sequence, followed separately
by historical weather. Map presentation, authenticated acquisition and model
bindings remain separate tasks. Wales and Northern Ireland designation adapters
remain deferred; the broader UK capability requirement is unchanged.
