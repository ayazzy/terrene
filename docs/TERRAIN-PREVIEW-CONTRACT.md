# Retained terrain preview contract

## Outcome

Terrene can now return an authenticated, georeferenced elevation preview for one
exact successful EA DTM capture. `terrain_preview_v1` packages a bounded PNG with
its display coordinates, native provenance, availability, units and legend.
It prepares retained terrain for map presentation without changing source evidence
or running an analytical model. The map UI does not consume this endpoint yet.

## Implementation / architecture

`GET /api/acquisitions/{id}/terrain-preview?attempt_id={exact_attempt}` returns
the typed `TerrainPreview` model under the existing organization dependency.
The attempt is required; there is no implicit latest attempt, provider fetch or
fallback to a different capture. Unauthorized records and unsuccessful attempts
return 404, unsupported successful sources return 422, and integrity failures
return a sanitized 500. Successful and handled acquisition-error responses carry
`Cache-Control: no-store`. Production JWT checks use the existing implementation.

The response contains:

- `capture`: acquisition, attempt, manifest and native-raster hash; source/adapter;
  capture dates, unknown observation date, attribution and licence.
- `requested_geometry`: the unchanged WGS84 acquisition polygon.
- `native`: original EPSG:27700 grid, 1 m resolution, metre/ODN vertical reference,
  nodata sentinel and original requested-area availability counts.
- `grid`: north-up EPSG:3857 preview grid, projected pixel size and WGS84 image
  corners ordered top-left, top-right, bottom-right, bottom-left. Visible and
  transparent display counts remain separate from native availability.
- `legend`: native requested-area minimum/maximum for the grayscale display;
  colors and explicit valid/missing alpha.
- `image`: RGBA8 PNG encoded as base64, byte count and SHA-256. This is an inline
  display derivative, not a raw-raster download or public object-store URL.
- `rendering`: algorithm version, nearest-neighbour method, mask/projection policy
  and relevant runtime library versions.
- `preview_fingerprint`: SHA-256 of canonical response metadata excluding the
  fingerprint itself and base64 payload. Image hash and byte count remain included.

`ea_dtm_grayscale_web_mercator_v1` validates the retained artifacts, source role,
before/after WCS metadata and full native coverage replay before rendering.
Only native cell centres inside the original polygon, excluding holes, can
contribute. It reprojects with nearest-neighbour sampling to a grid whose longest
side is at most 512 pixels, with no requested output sizing or arbitrary URL input.
The native acquisition polygon is densified at 25 m for its display projection;
a destination pixel-centre mask also excludes holes and outside-request areas.

Missing and excluded pixels are transparent black. Valid elevation maps linearly
from RGB 32 to 240 using all valid native request cells; a constant field uses RGB
128. A fully missing capture returns a transparent image, null legend bounds and
`no_visible_samples`. Zero and negative elevations remain valid data. The PNG
encoder uses standard-library zlib and fixed PNG filter/metadata settings, adding
no dependency. A response's image and metadata travel together to avoid mixing
capture-specific legend/georeferencing with another image.

The display grid follows [Rasterio's reprojection API](https://rasterio.readthedocs.io/en/latest/api/rasterio.warp.html).
Corner ordering follows the [MapLibre image-source contract](https://maplibre.org/maplibre-style-spec/sources/#image).
The image is already projected into Web Mercator; a later UI must use the supplied
corners and preserve transparency, attribution and legend rather than treating
native British National Grid corners as a geographic image rectangle.

## Source

Only `environment_agency.lidar_dtm_1m` / `ea_lidar_dtm_wcs_v1` is supported in this
version. Native acquisition and source limitations remain in
[EA terrain acquisition](EA-LIDAR-GEOGRAPHIC-ACQUISITION.md).
DSM, satellite, vector and weather captures are not silently rendered as terrain.
No source requests, new captures, migrations or storage writes are made on reads.

## Evidence semantics

The grayscale image is a disposable presentation output. Resampling and its local
contrast range make pixels unsuitable as analytical elevation measurements or for
direct visual comparison with independently stretched previews. Native elevation,
resolution, cell counts and source hashes remain authoritative and separate.
Downsampling can omit small valid or missing features; `no_visible_samples` does
not establish no native evidence. Transparent margins and holes are not zero terrain.

The source is a historical composite with unknown local survey dates. No height
above ground, hillshade, slope, hydrological calculation, flood risk or climate
interpretation is created. Existing Evidence Snapshots and ModuleRuns do not adopt
this display output. Rendering changes require a new renderer version; changed
image bytes or runtime provenance also produce a different preview fingerprint.

## Files changed

- `backend/terrain_preview.py`: typed contract, integrity checks and bounded renderer.
- `backend/api.py`: authenticated GET and explicit unsupported-source error.
- `tests/test_terrain_preview.py`: 23 focused rendering/integrity/access tests.
- `docs/verification/terrain-preview-2026-09-15.json`: sanitized real-data acceptance.
- `docs/TERRAIN-PREVIEW-CONTRACT.md`, `docs/ARCHITECTURE.md` and
  `docs/CURRENT-STATE.md`: implementation, semantics and current task boundary.

No raw rasters, PNGs, base64 image payloads, provider files, local databases or
private storage keys are committed.

## Verification

**285 affected tests pass on SQLite and 285 on disposable PostgreSQL/PostGIS**,
including **23 new tests**. The affected run covers preview, catalogue, geographic
acquisition, coverage profiles, DTM, DSM, satellite, weather and NatureScot modules.
New checks cover exact source/attempt identity, fingerprint reproducibility,
inverse geographic pixel lookup and orientation, zero/negative/missing values,
constant and empty images, holes/multipart gaps, exclusion of bounding margins from
legend statistics, output size bounds, source rejection, corrupted bytes/metadata,
failed-attempt history, no-write/no-provider GETs and typed OpenAPI.

Production JWT handling is exercised with locally signed tokens and a stubbed
JWKS lookup, including wrong tenants, expiry, issuer/audience errors and forged
signatures. This is not hosted acceptance. Python compilation and final diff checks
pass. Existing dependency deprecation, raster transform and PostGIS reflection
warnings remain. Frontend builds and browser interaction QA were not rerun because
no frontend code or existing UI behavior changed.

## Real-data verification

The active Oxford DTM capture `11051877-6624-4e58-9b71-4f252eaa7465`, exact attempt
`9b0eeb7e-96e1-4499-afed-14bd063cfbdc`, produces a **511 × 512** PNG of **109,893
bytes**. It has 252,941 visible pixels and 8,691 transparent pixels; its unchanged
native request has 1,000,000 valid cells. The display legend spans the retained
native request range, approximately 54.30–76.36 m ODN.

The PNG was decoded and visually inspected. **235 inverse-coordinate native
sample checks passed**, including 180 valid pixels and 55 transparent pixels.
Sampling used a 17 × 17 grid and excluded native cell-edge distances below 0.05
pixels to avoid ambiguous nearest-cell comparisons between projection operations.
These are retained-source consistency checks, not an independent survey or complete
pixel certification. Fresh-process output and the actual API and same-origin proxy
responses match exactly, including hashes and cache headers. One local render took
approximately 1.72 seconds; no service-level performance guarantee is inferred.

All **20 database table fingerprints and 78 stored object-file hashes remain
unchanged** across the verification reads. All four prior acquisition manifest
hashes match their recorded acceptance identities. The original Oxford assessment
remains completed. See the [acceptance record](verification/terrain-preview-2026-09-15.json).

## Historical / compatibility impact

Existing acquisition, assessment, source, snapshot, model and binding identities
remain unchanged. This is an additive read contract with no schema or dependency
change. The local API was restarted with its existing explicit Oxford database and
object-root settings; its original assessments and acquired evidence are retained.

## Known limitations

This is one bounded terrain image per exact capture, computed on each request.
There is no shared cache, tile pyramid, national mosaic, terrain mesh, point query,
display UI or raster-derived model. Larger-scale rendering and concurrency need
separate performance work. Runtime projection differences can change rendering;
the fingerprint identifies the returned derivative rather than claiming identical
output across every software environment. Raw source artifacts remain private.

The local database/object root is still an external temporary directory. Durable
storage/backup and hosted tenancy acceptance remain operational follow-ups.

## Git

Branch: `feat/terrain-preview-contract`, based on the verified Oxford capture-library
branch because this task consumes its real retained evidence and existing catalogue.

## Recommended next task

Consume this verified contract in one bounded map-layer UI task: explicitly select
a retained terrain capture, display its image with the supplied placement and
legend, and preserve source/date/missing-data semantics and map context. Satellite
rendering, acquisition controls and analytical models remain separate iterations.
