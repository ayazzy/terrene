# Independent EA LIDAR terrain acquisition

Terrene can now acquire a bounded 1 m terrain raster without creating a Site,
assessment or model run. This is the first raster adapter in the independent
geographic acquisition service. It extends the existing request, immutable
attempt, provenance and integrity-read mechanisms rather than introducing a
second acquisition database.

## Source and scope

Registered source: `environment_agency.lidar_dtm_1m`.
Adapter: `ea_lidar_dtm_wcs_v1`.
Processing: `ea_dtm_native_cell_coverage_v1`.

The [official EA catalogue](https://www.data.gov.uk/dataset/01b3ee39-da3f-47b6-83da-dc98e73a461f/lidar-composite-digital-terrain-model-dtm-1m)
identifies a historical bare-earth composite, published at 1 m resolution,
with metre elevations referenced to Ordnance Datum Newlyn and OGL terms.
It is a raster terrain product; raw point clouds are not acquired here.
The registered [WCS endpoint](https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs)
serves coverage
`13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m`.

The source descriptor retains attribution and catalogue context. The observed
WCS description contains an erroneous radiance unit tag, `W.m-2.Sr-1`.
This adapter explicitly binds vertical meaning to the catalogue, checks that
known tag, and fails on a changed schema/unit tag pending review. It does not
silently interpret a new unit. The catalogue's composite label is context,
not an immutable WCS release identifier or a local survey date.

## Coverage and bounded requests

Requests use `geographic_acquisition_request_v1`, explicitly select the terrain
source/adapter, and pin the existing `ons_england_dec2024_bfe_v1` operational
profile. A previously prepared compatible England BFE hash can be reused.
Historical BFC and Scottish profiles cannot substitute for it.

Whole-area administrative coverage is checked before provider access. The area
is transformed to EPSG:27700 with `always_xy`; projected vertices are not
densified. The bounding window is rounded outward to integer metres with an
additional 3 m margin. The raster is retained in that native bounding window;
cell availability is calculated only inside the requested polygon, excluding
holes and retaining multipart geometry.

Limits are explicit:

- 4,000,000 pixels per bounding window and 4,096 pixels per axis; this is not
  permission to download the whole country or every area accepted by the common
  vector request geometry limit.
- 32 MB per decoded response, 36 MB total, 2 MB per metadata response.
- 180 seconds total network time and 45 seconds per request timeout.
- Current publication only; interval/historical queries are rejected.

The national profile is an operational jurisdiction check, not proof that every
pixel has data. Other UK LIDAR publishers, offshore support, bulk tiling and an
actual survey-date index remain unimplemented.

## Native artifacts and evidence semantics

One successful attempt retains:

1. Original `DescribeCoverage` XML before acquisition.
2. Original GeoTIFF bytes from the exact `GetCoverage` request.
3. A canonical JSON `geographic_raster_coverage_v1` result.
4. Original `DescribeCoverage` XML afterward, which must match the first response.

XML and GeoTIFF are typed binary artifacts with organization-scoped content hashes.
Response endpoint, exact parameters and decoded-byte hashes are retained in
diagnostics. Historical JSON artifact paths, encoding and manifests are unchanged.
No source blob, national geometry, database or public storage URL is committed.

The adapter requires a single float32 band, EPSG:27700, an unrotated north-up 1 m
grid, the exact requested bounds, a finite nodata declaration and bounded raster
dimensions before reading pixel arrays. Unexpected units, off-target/truncated
windows, resampling, unsafe numerical values and provider/schema changes fail
explicitly. Original received artifacts remain attached to failed attempts where
available. Failed requests can append a new attempt; successful retries reuse
their immutable capture without provider access.

Coverage reports candidate area-cell centres, valid cells, missing cells and
their fraction. States are `complete`, `partial` and `no_valid_cells`. A successful
all-nodata capture is retained as `no_valid_cells`; it never becomes zero terrain
or an acquisition/network failure. An area with no native cell centre is rejected
explicitly. Genuine zero elevation remains a valid source value.

No raster pixels are filled, clipped or resampled by Terrene. The publisher's
composite processing remains distinct from this capture method. Availability
is not confidence, local survey age or continuous subpixel coverage. No slope,
height, hydrology, flood probability, suitability or climate model runs here.
Before/after WCS definitions cannot detect every in-place pixel edit; these
checks do not provide an atomic provider snapshot.

## Operator use

Use the [existing private acquisition setup](GEOGRAPHIC-EVIDENCE-ACQUISITION.md).
CLI defaults remain England SSSI v1, so select LIDAR explicitly:

```sh
.venv/bin/python -m backend.acquisition sources --adapter-version ea_lidar_dtm_wcs_v1
.venv/bin/python -m backend.acquisition prepare-coverage --adapter-version ea_lidar_dtm_wcs_v1
```

Use the resulting profile hash in a new request file. Replace the placeholder;
keep source, adapter, geography, temporal mode and idempotency key explicit:

```json
{
  "contract_version": "geographic_acquisition_request_v1",
  "source_id": "environment_agency.lidar_dtm_1m",
  "adapter_version": "ea_lidar_dtm_wcs_v1",
  "coverage_profile_sha256": "<your prepared England BFE profile hash>",
  "area": {"type": "Polygon", "coordinates": [[[-1.300,51.755],[-1.298,51.755],[-1.298,51.757],[-1.300,51.757],[-1.300,51.755]]]},
  "temporal": {"mode": "current_publication"},
  "idempotency_key": "terrain-demo-001"
}
```

```sh
.venv/bin/python -m backend.acquisition acquire --org YOUR_ORG --request /private/path/request.json
.venv/bin/python -m backend.acquisition read --org YOUR_ORG --id ACQUISITION_ID
.venv/bin/python -m scripts.verify_geographic_acquisition --org YOUR_ORG --id ACQUISITION_ID
```

Trusted backend consumers can call
`read_acquisition_artifact(org, acquisition_id, 'native_raster')` to obtain the
exact verified GeoTIFF bytes. An optional `attempt_id` selects historical attempt
artifacts. Organization isolation and all manifest checks apply; callers cannot
supply arbitrary object paths or URLs. This is an internal operator capability,
not a new authenticated HTTP endpoint, map layer or snapshot/model binding.

## Verification

Live captures on 14 September 2026:

| Sample | Retained grid | Cells inside requested area | Valid cells | Independent live checks |
| --- | --- | ---: | ---: | --- |
| Oxford | 167 × 167, native 1 m | 25,600 | 25,600 | Three separate one-cell WCS requests matched |
| East Anglia | 167 × 167, native 1 m | 25,600 | 25,600 | Three separate one-cell WCS requests matched |

The full coverage calculation replays from retained bytes. Fresh processes
read both summaries unchanged, verify native byte hashes, and reuse both
successful requests with network access disabled. All six previous England and
Scotland vector acquisition summaries and manifest identities remain unchanged.
The isolated live verification database still has no Sites, assessments, legacy
datasets/features, Evidence Snapshots or ModuleRuns.

The verifier checks three distributed area cells and adds a missing-data cell
when one exists. It does not claim a second full raster download or scientific
survey validation. Exact requests, sampled values, hashes and replay results
are in the [verification record](verification/ea-lidar-dtm-2026-09-14.json).

The affected acquisition, terrain and building-height suites pass **148 tests
on each of SQLite and PostgreSQL/PostGIS**, including **30 raster acquisition
tests**. They cover native byte
retention, wrong grids/units/extents, complete/partial/all-nodata coverage,
polygon holes, multipart areas, subpixel requests, size limits, source changes,
corruption, organization isolation, retries and independent sample mismatches.
Existing dependency deprecation and PostGIS reflection warnings remain. Python
compilation and diff checks pass. No frontend files or deployment configuration
changed, so browser QA and production deployment were not performed.

## Delivery sequence

The founder deferred Wales and Northern Ireland designation adapters in favour
of LIDAR and additional data families. UK capability remains the broader goal;
this EA source establishes England terrain support only. The next bounded
candidate is independent DSM acquisition with explicit pairing rules for terrain
and surface grids. Dated imagery, historical weather and application/map access
remain subsequent separate tasks. No customer workflow or revenue hypothesis
was validated by this engineering iteration.
