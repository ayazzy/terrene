# Independent dated Sentinel-2 acquisition

Implemented 15 September 2026 (Europe/London). Verification timestamps are UTC.

## Outcome and source

Terrene can discover candidate satellite observations and independently capture
one explicitly selected Sentinel-2 Collection 1 Level-2A scene for a bounded area.
This improves Terrene Earth's representation of reality through dated spectral
samples and retained source classification. It does not establish a commercial
workflow or interpret change.

The registered source is `copernicus.sentinel2_c1_l2a_earthsearch`; the adapter is
`sentinel2_c1_native_window_v1`, processing `sentinel2_native_dn_and_scl_v1`.
Copernicus/ESA is the observation producer. Element 84 distributes the COG mirror
through Earth Search collection `sentinel-2-c1-l2a`. It is distinct from Earth
Search's older `sentinel-2-l2a` collection and from a direct Copernicus download.
Public access requires no credentials. The source is geographically suitable for
all four UK nations; each capture must independently pass footprint/grid checks.

Authoritative references:

- [AWS open-data registry](https://registry.opendata.aws/sentinel-2-l2a-cogs/)
- [Element 84 collection and calibration documentation](https://github.com/Element84/earth-search)
- [Copernicus Sentinel-2 products](https://sentiwiki.copernicus.eu/web/s2-products)
- [Copernicus processing and classification](https://sentiwiki.copernicus.eu/web/s2-processing)
- [Sentinel data legal notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice)

## Contract and acquisition

`geographic_satellite_request_v1` explicitly pins source, adapter, scene ID,
canonical STAC Item SHA-256, area, UTC interval and organization-scoped idempotency
key. It has no administrative coverage-profile field: the selected satellite
scene's retained footprint and native raster grids establish supported coverage.
Historical `geographic_acquisition_request_v1` fields/defaults/hashes are unchanged.
Both contracts use the existing request/attempt tables, immutable objects, leases,
fencing, retries and integrity-read service. No migration or dependency was added.

Discovery performs one bounding-box catalogue query, validates each returned
candidate against the precise polygon and source schema, and exposes rejected
candidates and pagination incompleteness. It creates no acquisition or evidence
record. It does not follow arbitrary pagination links, choose a best scene, or
claim that an empty page establishes no observations. Intervals require ordered
UTC timestamps and span at most 366 days; neither an implicit latest observation
nor an unbounded archive request is supported.

Capture requires the whole polygon to be covered by the chosen scene footprint
and every native band grid. Metadata is fetched before and after the capture and
must agree with the request's pin. Source/collection, product baseline, band names,
calibration, file sizes/checksum schema and native UTM grids are validated.

Only fixed registered S3 asset paths are accessible. A custom Rasterio file opener
uses bounded HTTP ranges with strong ETags, `If-Match`, exact Content-Range/length
validation and no redirects or sidecars. GDAL makes no direct network requests.
Each fetched range is retained as original binary bytes, with asset URL, offset,
ETag, response hash and file-size provenance. Failed/truncated/changing captures
remain failed attempts and are never presented as missing or empty observations.

The retained window GeoTIFFs are **lossless derived subsets**, not original complete
publisher files. Native DN, CRS, pixel positions, resolution and nodata are
preserved; there is no resampling, reprojection of raster values, masking/filling
of cloudy cells or reflectance conversion. Original ranges allow offline source
reconstruction for the captured windows with the recorded Rasterio/GDAL versions;
an uncaptured read fails instead of fetching a replacement. Publisher whole-file SHA-256 multihashes
are retained as claims; range reads do not verify whole-file checksums.

## Evidence semantics and limits

- B02/blue, B03/green, B04/red and B08/near infrared are retained separately at 10 m.
- SCL remains at 20 m with all twelve provider class counts, including nodata,
  defective cells, shadows, clouds, cirrus, snow/ice and unclassified cells.
- Spectral DN zero is nodata. For a future reflectance calculation, first mask
  nodata, then use the exact retained per-band scale and offset. A nonzero DN can
  calibrate to zero or negative reflectance; neither is silently clipped here.
- `valid_cell_count` means non-nodata source samples, including cloudy samples.
  It is not a count of usable clear-ground measurements. SCL is a provider
  classification, not observed land-cover truth or predictive confidence.
- STAC `datetime` records observation time. Capture time, product generation,
  processing baseline and catalogue update metadata remain distinct.
- Coverage counts native pixel centres inside the polygon and excludes holes.
  WGS84 edges are densified to at most 0.001 degree before native UTM projection.
  Raster windows retain the surrounding bounding pixels; no national mosaic is made.
- Each window is capped at 1 million cells and 2,048 pixels per axis. The shared
  polygon contract also caps area at 100,000 hectares. HTTP limits are 8 MB per
  response/range, 64 MB total, 256 range requests, 240 seconds overall and 40
  seconds per request. Excessive polygon densification and unsafe TIFF blocks fail.
- One scene must cover the area. Multi-scene mosaics, cross-tile assembly,
  cloud masking, derived indices, change detection, forecasts, public acquisition
  API, raster rendering and model binding are separate work.

## Operator use

Use an isolated/private `CRC_DATA_DIR`; raw imagery must not enter Git. The area
file is a GeoJSON Polygon/MultiPolygon geometry, not a FeatureCollection.

```sh
python -m backend.acquisition sources --adapter-version sentinel2_c1_native_window_v1
python -m backend.acquisition discover-satellite --area area.json \
  --start 2025-06-01T00:00:00Z --end 2025-06-30T23:59:59Z
```

Select an explicit returned `scene_id` and `scene_metadata_sha256`, then construct:

```json
{
  "contract_version": "geographic_satellite_request_v1",
  "source_id": "copernicus.sentinel2_c1_l2a_earthsearch",
  "adapter_version": "sentinel2_c1_native_window_v1",
  "area": {"type": "Polygon", "coordinates": [[[-1.26,51.74],[-1.25,51.74],[-1.25,51.75],[-1.26,51.75],[-1.26,51.74]]]},
  "temporal": {"mode": "interval", "start": "2025-06-01T00:00:00Z", "end": "2025-06-30T23:59:59Z"},
  "scene_id": "COPY_SELECTED_SCENE_ID",
  "scene_metadata_sha256": "COPY_SELECTED_METADATA_HASH",
  "idempotency_key": "operator-chosen-unique-key"
}
```

The placeholders must be replaced; they are deliberately not runnable defaults.

```sh
python -m backend.acquisition acquire --org ORG --request request.json
python -m backend.acquisition read --org ORG --id ACQUISITION_ID
python -m scripts.verify_geographic_acquisition --org ORG --id ACQUISITION_ID
```

A changed scene selection or metadata pin requires a new idempotency key. Exact
successful retries read retained evidence without accessing the provider. Internal
`read_acquisition_artifact` returns checked bytes; it exposes no public storage URL.

## Verification and compatibility

**40 new tests** cover source/role pinning, valid UTC intervals, discovery
incompleteness, cloud/nodata separation, native grids/calibration, polygon holes,
request/byte/window/deadline limits, redirects/ETags/truncation, failure history,
organization isolation, no legacy writes, CLI dispatch, full offline range replay
and detection of different live pixels. The **211-test affected suite passes on
both SQLite and disposable PostgreSQL/PostGIS**. Python compilation and diff
checks pass. No frontend code changed; browser QA and frontend builds do not apply.

The initial PostgreSQL run exposed a new test assuming legacy tables were empty.
It was corrected to assert unchanged before/after counts, preserving pre-existing
test records. Final runs pass. Dependency deprecation/reflection warnings remain;
a deliberately broken TIFF/range test also exercises GDAL's georeferencing warning.

Live verification used isolated local storage and public data:

| Area | Observation | Spectral cells per band | SCL cells present / within area | Fresh pixel matches |
| --- | --- | ---: | ---: | ---: |
| Oxford | 19 June 2025, 11:17:06.796 UTC | 7,681 | 1,918 / 1,918 | 15 |
| Edinburgh | 2 June 2024, 11:25:43.130 UTC | 6,882 | 1,786 / 1,786 | 15 |

Every retained window and coverage summary reproduces from saved source ranges.
Fresh-process readback, provider-free retries and offline replay pass. The
verification script independently locates WGS84 point-in-polygon samples and
performs fresh one-cell reads in all five assets, with matching ETags/metadata.
This is not an independent satellite measurement or a complete second download.

Additional Cardiff and Belfast queries returned 10 and 36 compatible candidates,
respectively, on incomplete catalogue pages. These are **discovery-only** checks;
no Welsh or Northern Irish pixel capture is claimed. Their designation adapters
remain deferred. None of these local checks certifies complete UK temporal coverage.

Ten previously retained vector/DTM/DSM capture summaries and both explicit LIDAR
pairing results remain identical. The isolated satellite database has two requests
and two attempts, and zero Sites, assessments, datasets, features, Evidence
Snapshots or ModuleRuns. No historical model/binding/source identity was changed.

See the [sanitized acceptance record](verification/sentinel2-acquisition-2026-09-15.json).
Original raster ranges, windows, full source metadata and local databases remain
outside Git. No deployment was performed.

## Recommended next task

Add bounded historical weather acquisition with explicit time periods, variable
units and observed-versus-modelled provenance. Satellite map display and temporal
analysis should consume this verified contract in separate tasks.
