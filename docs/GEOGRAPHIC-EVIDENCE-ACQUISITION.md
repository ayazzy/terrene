# Independent geographic evidence acquisition

Implemented 14 September 2026 on the approved [first-iteration scope](GEOGRAPHIC-EVIDENCE-ACQUISITION-PLAN.md).
This establishes reusable area-based evidence collection. It does not validate a
customer workflow, an environmental model or product–market fit.

## Implemented contract

`backend.acquisition.acquire(org, AcquisitionRequest)` collects the current
Natural England SSSI publication for an explicit supported WGS84 Polygon or
MultiPolygon. A trusted operator CLI exposes source discovery, coverage setup,
acquisition and integrity-checked readback. No Site or assessment is required.

Shared geometry validation accepts areas across all four UK nations and their
islands, with finite 2D positions, explicit closed rings, valid topology, a
500 KB request limit, 10,000 positions and a 100,000 ha maximum. Area is calculated
on the WGS84 ellipsoid; request coordinates are not repaired or rounded. Canonical
ring/component ordering produces a stable geometry fingerprint. Antimeridian
requests are explicitly unsupported. This is geometry acceptance, not source
coverage certification or a promise that one request can cover the whole UK.

Only registered source `natural_england.sssi` / `sssi_arcgis_v1` exists in this
iteration. Its current-publication contract rejects historical intervals before
network acquisition. The source descriptor states jurisdiction, native and
retrieved CRS, identifiers, terms, unknown resolution and bounded limits.

## Source and operational coverage

- Publisher: Natural England; native designation **SSSI**, native `REF_CODE`, and
  publication-local `OBJECTID`. The [official dataset metadata](https://www.data.gov.uk/dataset/5b632bd7-9838-4ef2-9101-ea9384421b0d/sites-of-special-scientific-interest-england3)
  describes notified sites and attribution requirements. Proposed sites, condition
  assessments and impact risk zones are separate evidence.
- Endpoint: [SSSI England ArcGIS layer](https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/SSSI_England/FeatureServer/0).
  Source CRS is EPSG:27700; requested GeoJSON uses longitude/latitude in EPSG:4326.
- Coverage gate: a privately retained, immutable [ONS December 2024 UK BFC England boundary](https://www.arcgis.com/home/item.html?id=d4f6b6bdf58a45b093c0c189bdf92e9d).
  Setup downloads the official England feature, metadata and item/terms metadata;
  the request explicitly pins the resulting profile hash. Subsequent acquisitions
  validate against that local object without re-downloading the national boundary.
- **This coverage gate is conservative.** BFC is full resolution but clipped to
  mean high water. It excludes some water areas inside an apparent inland bounding
  box. A Broads request was declined during live verification. The profile is an
  operational supported footprint, not a complete representation of Natural
  England's legal or published coverage. Areas must be wholly covered; there is
  no clipping, filling holes or silent empty substitution. A future coverage
  policy must use a new profile/capability version and preserve old acquisitions.
- The full England setup response was about 79 MB. Setup permits 100 MB per
  response / 110 MB total, a 240-second network budget and 75-second request
  timeout. Each evidence acquisition permits 2,000 envelope candidates, batches
  of up to 100 features, 20 MB per response / 60 MB total, a 180-second network
  budget and 25-second request timeout. These are bounded proofs, not national
  bulk-download infrastructure. Reading the full coverage profile currently has
  a material memory/CPU cost; no spatial cache is implemented.

## Persistence, integrity and history

Migration 9 adds `geographic_acquisitions` and
`geographic_acquisition_attempts`; PostgreSQL enables RLS and revokes browser-role
privileges. The CLI is a **trusted operator** interface: `--org` scopes persistence
and reads but does not authenticate a customer. Run it only with server/operator
credentials; an authenticated HTTP boundary is later work.

New records never enter legacy `datasets` or `features`. Legacy `latest()`,
assessment submission, worker behavior, Evidence Snapshots, ModuleRuns and model
specifications remain unchanged. An acquisition is not a Land Evidence Snapshot.

Each attempt retains a versioned manifest, request, source descriptor, capture
interval, publisher editing metadata, processing versions, diagnostics and artifact
checksums. The separate artifacts contain before/after source metadata, assembled
original envelope candidates, full normalized selected features and per-feature
repair/selection lineage. No provider feature is clipped to the requested area.
Artifact hashes describe canonical assembled JSON; recorded HTTP checksums
explicitly describe decoded response bytes. They are not compressed wire hashes.

Reads verify the manifest, relational envelope, all referenced artifact bytes and
successful captures' pinned coverage profile. Public-safe summaries omit private
object keys. Use an exact attempt ID to inspect a historical failure. Publisher
release, observation time and publication time stay unknown unless established;
retrieval time does not fill those fields.

Idempotency is organization-scoped. An identical successful request reuses its
recorded result without network IO; a changed payload with the same key conflicts.
A deliberate refresh requires a new key. Failures append an attempt on retry.
Concurrent requests use an optimistic claim and a 600-second lease; terminal
publication is fenced by token and lease. There is no scheduler or auto-retry.
After an expired lease, retry records the prior attempt as interrupted and starts
a new one. Interrupted publication may leave unreferenced immutable objects;
those objects are never exposed as completed evidence. Automatic orphan cleanup
is outside this iteration. Storage failures/interrupted processes retain explicit
relational diagnostics when no manifest could be committed.

Before/after metadata and ID-list checks reject detected provider changes,
missing/duplicate IDs and truncated selection. A complete zero-feature result is
known empty for this source/query. It is distinct from unsupported coverage,
network failure and missing evidence. The provider offers no atomic snapshot
transaction: an undetected mid-query edit remains a limitation.

## Operator usage

From the repository root, configure the normal database/private-storage settings.
For an isolated local run, set `CRC_ENV=development` and `CRC_DATA_DIR` to a private
directory outside Git. A deliberately configured `DATABASE_URL` overrides the
SQLite location. Never use an existing customer database for verification.

```sh
.venv/bin/python -m backend.migrate
.venv/bin/python -m backend.acquisition sources
.venv/bin/python -m backend.acquisition prepare-coverage
```

Use the returned hash in a UTF-8 request file:

```json
{
  "contract_version": "geographic_acquisition_request_v1",
  "source_id": "natural_england.sssi",
  "adapter_version": "sssi_arcgis_v1",
  "coverage_profile_sha256": "REPLACE_WITH_PREPARED_PROFILE_SHA256",
  "area": {
    "type": "Polygon",
    "coordinates": [[[-1.31, 51.75], [-1.26, 51.75], [-1.26, 51.79], [-1.31, 51.79], [-1.31, 51.75]]]
  },
  "temporal": {"mode": "current_publication"},
  "idempotency_key": "oxford-capture-001"
}
```

```sh
.venv/bin/python -m backend.acquisition acquire --org YOUR_ORG --request /private/path/request.json
.venv/bin/python -m backend.acquisition read --org YOUR_ORG --id ACQUISITION_ID
.venv/bin/python -m backend.acquisition read --org YOUR_ORG --id ACQUISITION_ID --attempt-id ATTEMPT_ID
.venv/bin/python -m scripts.verify_geographic_acquisition --org YOUR_ORG --id ACQUISITION_ID
```

The final command performs an independent **live polygon query** against the
provider and compares it with the retained selection. It does not reuse the
adapter's envelope-selection logic or substitute fixtures. A provider change or
mismatch fails verification. Standard acquisition/read commands return safe JSON
and a nonzero exit code for failure; diagnostics exclude exception strings and
private paths. Read the JSON state when coordinating operators; an in-progress
capture is not evidence readiness.

## Verification recorded on 14 September 2026

| Check | Result |
|---|---|
| Acquisition contract/adapter/persistence suite | 45 passed on SQLite and disposable PostgreSQL/PostGIS |
| Legacy assessment/import/environment/snapshot reasoning paths | 46 passed on SQLite and PostgreSQL/PostGIS |
| Explicit retained snapshot/wetland-run regressions | 21 passed on SQLite using local retained assets |
| Migration 9 applied twice | Passed on SQLite and PostgreSQL; new PostgreSQL tables have RLS enabled |
| Oxford `[-1.31, 51.75, -1.26, 51.79]` | 5 candidates, 5 selected SSSIs; independent live polygon IDs match |
| Western Norfolk `[0.5, 52.65, 0.55, 52.7]` | 1 candidate, 1 selected SSSI; independent live polygon IDs match |
| Original Broads request | Explicit `unsupported_geography`; no invented empty evidence |
| Fresh-process read and exact Oxford retry | Same saved summaries; no network access required |
| Live database legacy table counts | Zero Sites, assessments, datasets, features, snapshots and ModuleRuns |
| Retained Oxford result files | All 12 checksums unchanged |

Exact geometries, timestamps, native IDs, editing metadata, manifest/artifact
hashes, independent request parameters and compatibility checks are in the
[small verification record](verification/geographic-acquisition-2026-09-14.json).
Raw features, coverage geometry and local databases remain private and outside
Git. SQLite legacy execution also reported 9 expected skips before the separate
retained-data run. Existing Starlette deprecation and PostgreSQL geometry
reflection warnings remain. Python compilation and `git diff --check` passed.
No frontend/UI behavior changed, so browser QA and a frontend build were not run.
Hosted R2/Supabase access has not been verified.

## Recommended next bounded task

Resolve the designation coverage contract for national expansion, including the
observed coastal/tidal exclusion, then integrate and independently verify the
first additional national publisher. Preserve Scotland/Wales SSSI and Northern
Ireland ASSI identities and explicit gaps. Add national adapters sequentially;
authenticated application access and map integration follow in separate tasks.
