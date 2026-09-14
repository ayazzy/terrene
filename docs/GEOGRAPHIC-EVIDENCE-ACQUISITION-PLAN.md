# Geographic evidence acquisition — first iteration

## Status and objective

Scoped on 14 September 2026 against repository baseline `bf6e927`. This document
records a proposed implementation following the approved intelligence-platform
direction. No acquisition contract or new integration is implemented by this plan.

**Primary outcome:** acquire and integrity-read one existing vector source for an
explicit supported area without creating an assessment, running a model or
changing the legacy Oxford source catalogue. Demonstrate the same implementation
in Oxford and a second bounded area outside the pilot rectangle.

**Near-term delivery target:** the whole UK: England, Scotland, Wales and Northern
Ireland, including their islands. The founder clarified this after approving the
first plan. The first source remains an England proof; four-nation expansion is
the immediate follow-on priority, not an indefinite future extension. No calendar
deadline has been specified.

This improves Terrene's ability to represent reality by making evidence collection
reusable across geographies and independent of a particular analytical workflow.
It is an architectural proof, not validation of a customer or scientific model.

## Implementation findings that determine scope

| Existing surface | Verified behavior | Consequence for this iteration |
|---|---|---|
| [Reference importer](../backend/import_data.py), `fetch()` / `run()` | Already runs without an assessment. ArcGIS queries use `core.PILOT`; flood uses its own bounded extract; OpenMap uses its pinned Oxford support. | Add explicit geographic acquisition for one source; do not describe all existing collection as assessment-coupled or generalize every adapter together. |
| [Dataset selection](../backend/core.py), `latest()` | Selects the newest dataset by source key without geography or organization. | New regional results must remain outside the legacy `datasets`/`features` catalogue. A new key is insufficient: the legacy assessment selects every key. |
| [Assessment API](../backend/api.py), `submit()` | Pins `latest()` dataset IDs and a wetland model specification. | Keep this compatibility route unchanged. New acquisition must not create a dummy assessment. |
| [Worker](../backend/worker.py) and [analysis](../backend/core.py), `analyze()` | Worker claims assessment rows; analysis invokes nature assessment after overlay processing. | Do not repurpose the assessment queue or run analysis to obtain source evidence. |
| [Environment enrichment](../backend/environment.py), `enrich_state()` | Acquires terrain/environment inputs and retains an assessment-keyed snapshot for retries. | Raster/environment migration is later work; preserve the current retry and historical behavior. |
| [Land Evidence store](../backend/land_evidence_store.py) | Stores Site/boundary-linked projections; the legacy creation helper projects saved assessment results. | An area acquisition result is a separate contract, not automatically a `land_evidence_v1` snapshot. |
| [Boundary validation](../backend/core.py), `boundary()` | Enforces bounded polygon input and a broad England-area coordinate envelope, with pilot wording. | Reuse validation principles without changing Site semantics or treating a coordinate envelope as verified source coverage. |

## First source and delivery surface

Use the existing Natural England **SSSI** vector inventory. Its current adapter
already performs exhaustive ArcGIS object-ID retrieval, batched feature reads and
preservation of assembled source geometry before normalization. It avoids adding
a new provider, raster processing or a model to the first proof.

Confirm the live endpoint, schema, access terms and coverage during implementation.
Support the provider's current publication only in v1. An acquisition date does
not establish when a designation first existed, and the current endpoint must not
be presented as a historical archive.

Expose a typed backend service and an operator CLI accepting a request file and
explicit organization context, plus an integrity-checked result read operation.
The CLI is a trusted operator surface, not customer authentication. HTTP submission,
background scheduling and map/UI integration are separate iterations; a synchronous
bounded command is sufficient for this first acquisition proof.

## Request and source capabilities

The request must have a versioned schema and include:

- An explicit WGS84 Polygon/MultiPolygon area, with a stable geometry fingerprint.
  A Site or Project record is not required. Validate finite coordinates, topology,
  coordinate count, payload size and area limits; never repair the user's geometry.
  Shared validation must accommodate valid areas across all four UK nations,
  including Northern Ireland and northern Scottish islands. Do not reuse the
  legacy `boundary()` England envelope or assume EPSG:27700 for every source or
  area calculation. Record native CRS and use an appropriate explicit method.
  Separate valid geometry from unsupported source coverage: a Scottish area is
  not invalid merely because the first adapter serves England.
- A registered source identifier and adapter/capability version. Resolve endpoints
  from server-owned configuration; do not accept arbitrary fetch URLs.
- An explicit temporal selection. V1 supports current publication. A supplied
  historical interval must produce an unsupported-time result before collection;
  do not silently drop it or substitute current data.
- An idempotency key for the logical acquisition request, scoped to the organization.
  A changed payload with the same key must conflict.

The source descriptor declares its vector data family, supported spatial and
temporal requests, publisher and access requirements, attribution/usage terms,
known scale or resolution, and acquisition limits. Unknown resolution stays
unknown. Distinguish publisher coverage, the area we retrieved and completeness
of this retrieval; none establishes a complete real-world inventory.
Source identity includes publisher/jurisdiction and native feature identifiers.
Do not require a single nation per request: a cross-border area is valid geometry,
although v1 may explicitly decline it if its selected source lacks full support.

Keep this contract narrow. It must have an extension path for dated imagery and
time series without implementing pretend raster, stream or paid-provider adapters.

## Acquisition and persistence

1. Validate source capabilities and the requested area/time before network work.
   Select explicit conservative area, feature, byte and timeout limits and record
   them in the adapter configuration. Reject requests outside supported coverage
   rather than silently clip them.
2. Retrieve a complete bounded feature selection using the existing exhaustive
   object-ID/batch approach. If the provider is queried by the area's bounding box,
   record that acquisition envelope and any subsequent polygon selection separately.
   Preserve complete selected source features and stable provider feature IDs.
3. Retain the assembled original provider features before any geometry repair,
   provider metadata and a separate normalized artifact. Describe hashes accurately:
   a hash of assembled JSON is not a hash of the original HTTP response bytes.
   Reuse immutable object-storage primitives and record normalization provenance.
4. Publish an immutable manifest and additive organization-scoped acquisition
   records. Keep raw objects private and omit storage locations from public-safe
   summaries. No writes to legacy `datasets`, `features`, assessment, Site, snapshot
   or ModuleRun records are needed.
5. Read by exact acquisition identity, verifying manifest/artifact hashes and the
   relational envelope after a process/database reload. Source artifacts must remain
   discoverable without rerunning the network request.

The result records the exact request, source/adapter identity, available publisher
version/edit metadata, capture times, acquired support, feature count, artifacts,
checksums, limitations and outcome. Where the provider supplies no immutable
release identifier, retain content identity and available metadata without
inventing an official release. Publication time may be unknown; observation time
must not be copied from retrieval time.

An acquisition result is retained provider evidence. Creating canonical parcel
observations, a Site Evidence Snapshot or a model binding from it is later work.

## Failure, retry and freshness semantics

- A complete successful query with zero selected features is a known empty result
  for that source/selection, not proof of no real-world constraints.
- Unsupported geography/time, incomplete pagination, changed/inconsistent provider
  responses, network failure, invalid source geometry and storage failure remain
  explicit. V1 must not publish a truncated retrieval as successful or convert an
  error into an empty collection.
- Failed execution attempts retain their available diagnostic/provenance records.
  Retries append attempt history rather than overwrite it; raw secrets and private
  paths must not appear in exported diagnostics.
- An identical completed request retried with the same idempotency key reuses its
  recorded result and does not refetch. A deliberate refresh uses a new key and a
  new acquisition attempt, even for the same area/source. Identical artifact bytes
  may be reused, but new capture history is retained.
- A failed refresh does not silently substitute an earlier success. Previously
  committed results remain readable by their exact identities.
- Concurrent identical requests must not publish contradictory results. Define a
  bounded claim/recovery mechanism for the synchronous service, including interrupted
  publication, without introducing a general scheduler in this iteration.

## Acceptance and verification

The implementation is complete only when:

1. The same typed service acquires the current SSSI publication for two explicit
   bounded areas, one in Oxford and one outside `core.PILOT`, with no constant edits
   between runs and no created Site, assessment or model run.
2. Synthetic tests cover valid/invalid requests, source capability rejection, an
   empty successful selection, pagination/byte limits, normalization lineage,
   failed acquisition, idempotency, concurrent publication and interrupted retry.
3. Cross-organization reads and idempotency-key reuse are isolated. Exact manifest
   or artifact corruption fails integrity checks; process reload preserves identity.
4. A regression proves new acquisitions leave `latest()` output, a newly submitted
   legacy assessment's selected dataset IDs and retained Oxford results unchanged.
5. Focused tests pass on SQLite and disposable PostgreSQL/PostGIS where persistence
   behavior is affected, including the additive migration. Run relevant legacy
   import, assessment and snapshot regressions; no frontend build/browser QA is
   required unless the implementation scope is explicitly changed.
6. Real provider verification records exact request geometries, retrieval dates,
   source IDs/metadata, counts and checksums. Independently compare the returned
   feature selection with the provider's query results for both areas. A live test
   must not accept synthetic fallback or compare only two views of the same cached
   result. Service/credential blockers must be reported as incomplete verification.
7. Synthetic contract tests accept representative geometries in England, Wales,
   Scotland (including a northern island) and Northern Ireland at the geometry
   validation stage. The England source must return explicit unsupported coverage
   for non-covered areas, including a cross-border request, without acquisition or
   fabricated empty evidence. These tests establish contract flexibility, not live
   four-nation data coverage.

Choose and verify the second small England area during implementation; Norfolk is
a candidate, not a selected customer market or a claim of current retained coverage.
Keep downloaded data and local databases outside Git. Commit only permitted small
verification manifests/reports with exact provenance; test fixtures must remain
clearly synthetic. No live provider download was performed for this scoping task.

## Immediate follow-on: deliver UK coverage

Prioritize these bounded iterations before optional new data-family integrations:

1. **Four-nation designation acquisition:** implement the remaining national
   adapters sequentially against the proven contract. Preserve native designation
   types, publishers, identifiers, release dates and usage terms. Independently
   verify national coverage metadata and sample acquisitions, including islands
   and jurisdiction edges. Record missing feeds and access blockers explicitly.
2. **UK application access:** provide the authenticated acquisition/read and
   evidence-assembly contracts, then update Site creation and map availability in
   a separate UI iteration. Review the existing England-only validation before
   exposing the workflow; broad basemap coverage alone does not deliver evidence.
3. **Coverage completion review:** publish a matrix by nation and evidence family
   with source, supported extent, time support, resolution, acquisition status and
   verification date. The initial designation family is the first milestone;
   terrain, rivers, habitats, infrastructure, imagery and climate each need their
   own coverage plan. Confirm bounded on-demand acquisition works across supported
   extents without requiring a fresh national download for every request.

Candidate official routes for the first designation family, checked as discovery
references on 14 September 2026 (not newly connected or downloaded datasets):

| Nation | Publisher / native designation | Route to verify when implementing |
|---|---|---|
| England | Natural England / SSSI | Existing registered ArcGIS source in [the importer](../backend/import_data.py) |
| Scotland | NatureScot / SSSI | [NatureScot data services](https://www.nature.scot/information-hub/naturescot-data-services) and [SSSI metadata](https://www.data.gov.uk/dataset/d64bf689-4ce8-465b-b00e-6a57dec94a22/site-of-special-scientific-interest-scotland) |
| Wales | Natural Resources Wales / SSSI | [NRW spatial data and DataMapWales access](https://naturalresources.wales/evidence-and-data/maps/browse-map-of-data-about-the-natural-environment/?lang=en) |
| Northern Ireland | DAERA / ASSI | [ASSI digital datasets](https://www.daera-ni.gov.uk/publications/assi-digital-datasets) |

This is one comparable evidence family, not a claim of identical designation
semantics or complete environmental coverage. Preserve ASSI as ASSI. Recheck
endpoint currency, schemas, licences and CRS before each integration. Later
cross-border orchestration should assemble explicit per-source acquisitions,
retaining uncovered portions and component lineage rather than silently dropping
part of an area or erasing jurisdiction distinctions.

## Scope boundary and follow-on sequence

This iteration does not implement a customer-facing API, dynamic map layers,
imagery, weather, radar, climate projections, arbitrary provider URLs, paid data
ordering, monitoring schedules, entity resolution, scenario calculations, model
changes or generalized source migration. It requires no new runtime dependency
unless implementation demonstrates a concrete need.

After this proof, prioritize the UK coverage sequence above. Then introduce dated Sentinel-2
imagery and its presentation, followed by historical weather, in bounded iterations
with source-specific processing and validation. Preserve the distinction between
historical weather and future climate projections. Commercial access agreements,
production deployment and the eventual market remain separate decisions.

## Suggested next-task prompt

Implement the first geographic evidence acquisition iteration described in this
plan: a typed backend service and operator CLI for the current Natural England
SSSI inventory, explicit bounded geometry and temporal capability validation,
immutable organization-scoped acquisition records, and integrity-checked readback.
Make shared geometry and source-capability contracts accommodate all four UK
nations from the outset; source-specific England coverage remains explicit.
Keep results out of the legacy dataset catalogue and do not create assessments or
run models. Verify one Oxford area and one bounded area outside the pilot using
the same implementation, complete the focused acceptance checks, and report any
live-data blocker explicitly. Stop after this contract is implemented and verified;
do not begin imagery, weather or UI work.
