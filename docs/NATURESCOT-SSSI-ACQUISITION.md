# NatureScot SSSI geographic acquisition

This iteration adds one national source to the independent acquisition service:
`naturescot.sssi` / `naturescot_sssi_arcgis_v1`. It improves reusable geographic
representation while preserving England v1/v2, legacy assessments and model inputs.
It does not add an HTTP endpoint, map layer, cross-border composition or model.

## Source identity and evidence meaning

The [Scottish dataset catalogue](https://www.data.gov.uk/dataset/d64bf689-4ce8-465b-b00e-6a57dec94a22/site-of-special-scientific-interest-scotland)
links to [NatureScot's published SSSI map](https://opendata.nature.scot/maps/sites-of-special-scientific-interest).
That map uses the [registered ArcGIS layer](https://services1.arcgis.com/LM9GyVFsughzHdbO/arcgis/rest/services/Sites_of_Special_Scientific_Interest/FeatureServer/0),
whose [service item](https://www.arcgis.com/home/item.html?id=b243da0bc2164849b80f9c8b347edd18)
is owned by `SNH_Maps` in NatureScot's organization. Its OGL v3 terms and
attribution are retained verbatim. Historical SNH identifiers and the publisher's
attribution year are preserved, not rewritten to match capture time.

This is the current Scottish SSSI publication. It retains:

- `OBJECTID`: one mapped component within this publication; not a durable
  cross-release entity identity.
- `PA_CODE`: native designation identity. Multiple components can share it.
  `feature_count` counts selected components; `designation_count` counts distinct
  represented `PA_CODE` values. Neither measures the complete area of a designation.
- `TYPE`: geological, biological or mixed interest, **not** designation type.
- `STATUS`: provider designation status. This version supports `Current` and
  rejects unknown statuses or interest classes explicitly rather than filtering.
- `UPDATED`: provider record-update value, preserved including null. It is not
  copied to observation time, publication time or designation date.

`native_feature_ids` contains the selected publication `OBJECTID` values;
`native_designation_ids` separately contains distinct `PA_CODE` values. The
normalization lineage links both identities to each retained component. Original
and normalized artifacts keep all provider attributes. England's `REF_CODE`
semantics remain unchanged. No ecological condition, confidence or scientific
measurement is inferred from these inventory records.

## Acquisition and coverage

The typed request binds the registered source to its adapter version before
persistence. Wrong source/adapter pairs fail validation. A Scottish request must
pin `ons_scotland_dec2024_bfe_p10_v1`, containing the official ONS December 2024 BFE
Scotland feature (`S92000003`). England profiles cannot establish Scottish coverage.
Source/time/whole-area capability validation happens before any NatureScot call.
Other nations, cross-border requests and areas outside the pinned footprint fail
explicitly. Supported temporal mode remains `current_publication` only.

The [ONS BFE definition](https://www.ons.gov.uk/methodology/geography/geographicalproducts/digitalboundaries)
is an administrative extent-of-realm boundary, usually to mean low water.
It is an operational footprint, not complete marine or legal SSSI coverage.
Remote/offshore areas outside it remain unsupported even when a publisher's
service extent is broader. The common WGS84 request contract supports northern
islands; no England coordinate envelope is reused.

The adapter reuses exhaustive envelope ID retrieval, bounded batches and local
polygon selection. Full selected source features are retained without clipping.
The Scotland path additionally retains before/after publisher item metadata,
checks owner, organization, endpoint, item identity and OGL terms, and verifies
required attribute types. Changed metadata/items/IDs, pagination errors and
invalid source identities remain explicit failures. Native source coordinates
are EPSG:27700; requested provider GeoJSON is longitude/latitude in EPSG:4326.

Private immutable manifests, retries, organization isolation and integrity reads
use the existing tables. Scottish successful reads additionally require the two
publisher-item artifacts and the matching coverage profile. Processing is pinned
as `naturescot_sssi_polygon_selection_v1`. No database migration or new dependency
is required; no new data enters legacy `datasets`/`features` or model bindings.

Evidence acquisition retains the existing 2,000-candidate, 20 MB response,
60 MB total and 180-second network limits. Explicit Scottish coverage preparation
has a separate 160 MB response / 170 MB total / 480-second network budget with a
75-second per-request timeout. The first attempt exceeded the previous 240-second
setup budget. Subsequent transfers were truncated after 48 MiB at default
precision and 40 MiB at 12 decimal places; the cutoff was not consistent. The
Scottish profile therefore requests explicit
[`geometryPrecision=10`](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/)
in WGS84 degrees, checks the returned coordinate precision,
and records that method in the profile identity and provenance. This is numerical
output precision, not measurement accuracy; no vertex generalization is requested.
England profiles, SSSI feature downloads and user geometry are unchanged. Once a
profile is prepared, regional acquisitions read it privately
without repeating the national download. Memory and read costs of this large
profile remain a limitation; no new cache or national tiling system is implemented.

## Trusted operator workflow

Use the [existing private database/storage setup](GEOGRAPHIC-EVIDENCE-ACQUISITION.md).
CLI defaults remain England v1 for compatibility; choose Scotland explicitly:

```sh
.venv/bin/python -m backend.acquisition sources --adapter-version naturescot_sssi_arcgis_v1
.venv/bin/python -m backend.acquisition prepare-coverage --adapter-version naturescot_sssi_arcgis_v1
```

In a new request, set `source_id` to `naturescot.sssi`, `adapter_version` to
`naturescot_sssi_arcgis_v1`, and use the returned Scottish profile hash. Supply an
explicit WGS84 Polygon/MultiPolygon, current-publication temporal mode, and a new
idempotency key. The existing acquire/read commands accept that request:

```sh
.venv/bin/python -m backend.acquisition acquire --org YOUR_ORG --request /private/path/scotland-request.json
.venv/bin/python -m backend.acquisition read --org YOUR_ORG --id ACQUISITION_ID
.venv/bin/python -m scripts.verify_geographic_acquisition --org YOUR_ORG --id ACQUISITION_ID
```

The independent verifier resolves the registered publisher endpoint and makes a
fresh polygon query. For Scotland it compares both publication component IDs and
distinct native designation IDs, with before/after publisher editing metadata.
It does not merely re-read the adapter's cached selection or substitute fixtures.

## Real-data verification

On 14 September 2026, the production acquisition path retained two real captures
in isolated private storage, with successful independent live polygon queries:

| Requested area | Retained components | Distinct SSSIs (`PA_CODE`) |
| --- | ---: | --- |
| Edinburgh, Arthur's Seat / Duddingston area | 4 | 2 (`91`, `547`) |
| Unst, sample near Keen of Hamar | 2 | 2 (`827`, `1315`) |

Both component IDs and designation IDs match the independent queries. The
successful pinned profile is `ons_scotland_dec2024_bfe_p10_v1`, SHA-256
`cc02feae231e635cf0d7f136a79f872451d78bbe3fb49553671833e13e5f2b5e`.
The retained valid MultiPolygon contains 2,699 polygon parts and 3,791,978
coordinates, all passing the 10-decimal precision check.
Its whole-area check rejects the tested England, Wales, Northern Ireland,
England–Scotland border and Rockall offshore polygons. These samples verify a
mainland and northern-island path, not complete national/marine coverage.

The four previous England acquisition summaries and verified manifest identities
remain unchanged: Oxford, western Norfolk, the original Broads v1 rejection and
the successful Broads v2 capture. Isolated legacy Site, assessment, dataset,
feature, Evidence Snapshot and ModuleRun tables all remain empty. No acquisition
silently publishes into those tables.

A fresh process reads both Scottish summaries unchanged and reuses each
successful acquisition with network access disabled. The cross-border sample
was separately confirmed to intersect both retained national profiles.

See the [small verification record](verification/naturescot-sssi-2026-09-14.json)
for request areas, acquisition/manifest/artifact identities, independent matches
and coverage checks. No national geometry, source features or database is tracked.

## Regression verification

The combined acquisition suites pass **91 tests on SQLite and 91 on disposable
PostgreSQL/PostGIS**. These cover source/adapter/profile isolation, native
component and designation identities, known empty versus failed selections,
provider changes, missing IDs, terms/schema failures, immutable retries and
England history. Coverage preparation checks the Scottish country code and
requested coordinate precision. Independent-verifier tests detect mismatched
designation codes. The existing legacy assessment/reasoning checks pass **35
tests on SQLite**. Existing dependency deprecation and PostGIS reflection warnings
remain unchanged.

No UI, authenticated acquisition API, model binding, database migration or new
dependency is introduced. Hosted storage/database acceptance has not been run.

## UK delivery position

| Nation | Independent designation acquisition | Remaining qualification |
| --- | --- | --- |
| England | Natural England SSSI v1/v2 | Explicit pinned coverage; historical v1 restrictions retained |
| Scotland | NatureScot SSSI v1 | Explicit Scottish footprint; component/designation counts differ |
| Wales | Not connected to this service | Separate official publisher adapter and verification required |
| Northern Ireland | Not connected to this service | Preserve ASSI meaning and verify separate publisher coverage |

All entries concern this designation family only. Cross-border composition,
user-facing acquisition and map/evidence assembly remain separate tasks.
These source integrations create reusable intelligence inputs. The next bounded
task is the Welsh publisher adapter, followed by Northern Ireland.
