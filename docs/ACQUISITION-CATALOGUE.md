# Retained acquisition catalogue

Implemented 15 September 2026.

## Outcome

An authenticated user can discover their organization's successful independent
captures by source, requested location and date, then inspect the exact retained
capture. This makes existing Terrene Earth evidence discoverable without creating
a Site, assessment or model run. Frontend presentation is a separate iteration.

## Implementation / architecture

Two GET routes reuse the existing `organization` dependency:

| Route | Response | Integrity scope |
| --- | --- | --- |
| `/api/acquisitions` | `acquisition_catalogue_v1` | Request/terminal envelope, manifest hash, source and geometry identity; artifacts not read |
| `/api/acquisitions/{id}?attempt_id={id}` | `acquisition_detail_v1` | Exact successful capture through existing retained-artifact checks |

Each entry identifies its source/adapter, acquisition, exact terminal attempt,
request and manifest hashes, geometry fingerprint, original requested geometry,
capture times, evidence time, availability counts, artifact count/bytes and exact
detail path. Source-specific caveats accompany the entry. Detail adds artifact
roles, byte lengths and checksums. Neither route exposes provider dictionaries,
idempotency keys, organization identifiers, storage keys or download URLs.

Catalogue entries explicitly say `manifest_verified: true` and
`artifact_verification: not_performed`. Detail says `artifact_verification: verified`
after successful retained checks. This is integrity of retained bytes, not scientific
validation or an assertion that original complete remote files were downloaded.

Production authentication validates signed JWTs and derives ownership from trusted
`app_metadata.org_id`. The existing explicit `CRC_ENV=development` bypass resolves
to `local-development`; it must not be mistaken for hosted tenant acceptance.
No query/header can choose an organization. Successful and handled operational
error responses use `Cache-Control: no-store`. Missing membership returns 401,
foreign/missing/unsuccessful captures return 404, invalid query/cursor returns 422,
and unreadable or corrupt retained metadata/artifacts return a sanitized 500.
No internal exception is returned by the acquisition operation wrapper.

### Query contract

| Parameter | Meaning |
| --- | --- |
| `bbox` | Optional `west,south,east,north` WGS84 bounds; finite coordinates, positive dimensions; antimeridian-crossing boxes unsupported |
| `source_id` | Optional exact registered source; unknown sources rejected |
| `start_date`, `end_date` | Both required together; inclusive ISO calendar dates interpreted as UTC days |
| `time_basis` | `evidence` default, or explicit `capture` |
| `limit` | 1–20 matching entries, default 10 |
| `cursor` | Opaque continuation returned by the preceding page; retain all query parameters |

For example, `/api/acquisitions?bbox=-1.4,51.6,-1.1,51.9&start_date=2024-02-01&end_date=2024-02-29`
looks for evidence intervals/instants intersecting February 2024 and request
geometries intersecting those bounds. It does not acquire February data.

Rows sort by descending request creation time and ID, rather than evidence date.
A call examines up to 50 successful request manifests and returns up to `limit`
matches. It fetches one additional database row to determine continuation. Follow
`next_cursor` until `scan_complete`, even when a filtered page has no entries.
`scanned_count` is page work, not a total evidence count. The base64 cursor is an
unsigned position bound to the query and organization hash; its marker is checked
for ownership. Forging a position cannot bypass SQL tenant scoping. Pagination is
live: a previously pending request can succeed between calls and be missed behind
the cursor. Restart a scan when a fresh view is needed.

## Source

The catalogue covers retained captures from Natural England SSSI, NatureScot SSSI,
EA 1 m DTM and last-return DSM, Copernicus Sentinel-2 C1 L2A and NASA POWER/MERRA-2
daily weather. It introduces no provider, licence change or expanded coverage.
Only successful independent acquisitions are listed; legacy datasets, snapshots,
failed attempts and captures owned by other organizations are excluded.

## Evidence semantics

- Location filtering intersects the requested Polygon/MultiPolygon or weather Point,
  including polygon holes. It is not a test of source footprint or valid pixels.
- Counts describe the original full retained request; partial search intersections
  never clip or recompute them. Vector components need not be distinct designations.
- Satellite evidence time is the retained scene observation instant, not the search
  interval. Available spectral cells can include cloud and shadow.
- Weather evidence time is the requested inclusive daily interval, including missing
  days. Availability counts report present/expected periods per variable. A point
  query never establishes surrounding grid or parcel coverage.
- Vector publication/observation dates and local composite-LIDAR survey dates remain
  unknown. They are excluded by evidence-date filters; capture-time filters use the
  completion instant without changing evidence dates.
- Missing catalogue results are not evidence of absence. Neither capture success nor
  availability establishes accuracy, predictive confidence or model suitability.

## Files changed

- `backend/acquisition_catalogue.py`: typed read projections and bounded filters/pagination.
- `backend/api.py`: authenticated GET routes and sanitized error boundary.
- `tests/test_acquisition_catalogue.py`: contract, isolation, integrity and read-only regressions.
- `docs/CURRENT-STATE.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`: durable implementation boundaries.
- This report and `docs/verification/acquisition-catalogue-2026-09-15.json`: acceptance record.

## Verification

All **41 new tests** pass. The **273-test affected suite** passes on both SQLite
and disposable PostgreSQL/PostGIS, covering the new catalogue, all independent
acquisition families/coverage versions and existing Site reasoning API contracts.
Python compilation and `git diff --check` pass.

Checks include missing/invalid/expired/wrong-audience/wrong-issuer JWTs, missing or
invalid organization claims, forged signatures, tenant isolation, foreign cursors,
unknown parameters, bounded scans, tied timestamps, empty filtered pages, hole-aware
intersection, point non-expansion, leap-day/date edges, unknown evidence dates,
actual satellite observation dates, exact attempts and private-field omission.
Local RSA keys replace only JWKS retrieval, allowing the real production token
validation dependency to execute; this is not a hosted authentication test.

Corrupt request hashes, absent terminal attempts, damaged manifests, mismatched
source/geometry envelopes and invalid counts fail closed. Damaged artifacts remain
explicitly unchecked on catalogue browse and fail exact detail reads. Instrumented
GET checks allow only SELECT statements, prohibit object writes and provider-client
construction, and reproduce the original capture summary. OpenAPI exposes typed
GET-only contracts.

## Real-data verification

Read-only route checks against existing local retained provider captures verified:

| Family | Successful captures | Locations |
| --- | ---: | --- |
| SSSI vectors | 5 | Oxford, western Norfolk, Broads v2, Edinburgh, Unst |
| EA DTM/DSM | 4 | Oxford and East Anglia, one of each raster type |
| Sentinel-2 | 2 | Oxford and Edinburgh |
| Historical weather | 4 | Oxford, Edinburgh, Cardiff and Belfast |

All **15 successful captures** appear under the correct owning organization, retain
exact IDs/hashes and pass detail artifact checks. Location/date behavior is checked
for every entry, including unknown-date exclusion and weather point non-expansion.
All **16 original summaries**, including the earlier failed Broads capture, replay
unchanged. Database and object-file hashes are unchanged before/after verification.

The API organization dependency was overridden to the original verification tenants
for these real-data checks. No new provider fetch, hosted JWT session or frontend
interaction was performed. The sanitized [acceptance record](verification/acquisition-catalogue-2026-09-15.json)
contains exact capture references and checks, with no raw artifacts or databases.

## Historical / compatibility impact

No migration, dependency, source adapter, request default, stored manifest, object,
assessment, Evidence Snapshot or ModuleRun was changed. Existing operator readers
and historical failures remain available unchanged. Catalogue/detail versions are
new read projections over the existing persistence model.

## Known limitations

The frontend does not consume the catalogue yet. The routes do not initiate
acquisition, return raw evidence values or serve raster tiles/artifact downloads.
No production deployment or customer workflow acceptance was performed. Catalogue
browsing checks metadata only; detail may read substantial retained raster data.
A bounded application scan is not a national spatial index, and large inventories
will need an indexed metadata projection. Polygon source coverage and all original
source-specific limits remain unchanged. Wales/NI designation acquisition is still
deferred; their retained weather does not imply designation support.

## Git

Branch: `feat/acquisition-catalogue`, based on the completed weather acquisition
commit `88e0af4`. One coherent feature commit contains implementation, tests and
acceptance documentation; see repository history for its final identity.

## Recommended next task

Build a read-only acquisition browser consuming these contracts: location/source/
date filters, truthful empty/continued pages and exact capture inspection. Preserve
weather points and unknown evidence dates. Raster imagery rendering, new providers,
acquisition controls and climate models remain separate bounded tasks.
