# Versioned designation coverage correction

The second acquisition iteration corrects the high-water clipping problem found
in the first live Broads request. Its bounded outcome is a new England coverage
policy with preserved historical behavior; adding another national publisher is
a separate next iteration.

## Cause and change

The first adapter used ONS December 2024 BFC country geometry. BFC is clipped to
mean high water, so its apparent inland extent can exclude tidal river water.
A rectangle over the Broads was therefore declined even though the area was in
England. This was an operational coverage restriction, not missing SSSI evidence.

The new `sssi_arcgis_v2` adapter uses capability `england_current_vector_v2` and
pins `ons_england_dec2024_bfe_v1`. It uses the official ONS **BFE extent-of-realm**
England polygon without filling holes, buffering, clipping or repairing it.
According to [ONS boundary guidance](https://www.ons.gov.uk/methodology/geography/geographicalproducts/digitalboundaries),
BFE generally extends to mean low water, sometimes farther to include islands.
It is an administrative supported footprint, not proof of complete marine or
legal designation coverage.

The [registered ONS item](https://www.arcgis.com/home/item.html?id=2d18d8d4d0b341dfbddebd39d66dbe79)
and its FeatureServer endpoint are fixed in server configuration. Preparation
verifies the item owner, item identity, service URL/type, native CRS, returned
GeoJSON CRS, England country code and valid polygon topology. It also verifies
that service metadata did not change during retrieval. The retained profile
includes source/item metadata, before/after metadata and response checksums.
ONS supplies these digital boundaries under OGL v3 with ONS/OS attribution;
item licence metadata is retained with the private geometry.

## Contract and historical behavior

The existing request envelope accepts an explicit adapter version of either
`sssi_arcgis_v1` or `sssi_arcgis_v2`. Each adapter accepts only its corresponding
profile version. A mismatch produces `coverage_version_mismatch` before SSSI
network acquisition. Whole-area support remains required; cross-border and
unsupported areas are not silently clipped or converted into empty evidence.

The SSSI endpoint, native `REF_CODE`/publication `OBJECTID`, candidate retrieval,
feature normalization, source-time meanings, limits and immutable persistence
contracts are unchanged. The coverage change receives its own adapter/capability
identity in every new attempt manifest. There is no schema migration, new
runtime dependency, model change, new national publisher or UI change.

Existing v1 profiles, requests, successful captures and rejected attempts remain
readable with identical content. CLI defaults remain v1 for compatibility.
Moving to v2 requires an explicit version, a newly prepared BFE profile hash and
a new idempotency key. Reusing a v1 key with changed input conflicts. Both
versions' successful reads check their pinned profile version and hashes.

## Operator use

Use the same trusted database/private-storage setup as the
[first acquisition iteration](GEOGRAPHIC-EVIDENCE-ACQUISITION.md).

```sh
.venv/bin/python -m backend.acquisition sources --adapter-version sssi_arcgis_v2
.venv/bin/python -m backend.acquisition prepare-coverage --adapter-version sssi_arcgis_v2
```

In a new request file, set `adapter_version` to `sssi_arcgis_v2`, use the returned
`coverage_profile_sha256`, and choose a new `idempotency_key`. Keep the source ID
`natural_england.sssi`, the explicit polygon and temporal selection.

```sh
.venv/bin/python -m backend.acquisition acquire --org YOUR_ORG --request /private/path/request-v2.json
.venv/bin/python -m backend.acquisition read --org YOUR_ORG --id ACQUISITION_ID
.venv/bin/python -m scripts.verify_geographic_acquisition --org YOUR_ORG --id ACQUISITION_ID
```

The final command independently queries the live provider using polygon
intersection, comparing it with the adapter's envelope candidates and local
selection. It never substitutes synthetic data. Coverage setup remains a large,
bounded one-time download per profile; existing byte/time limits are unchanged.

## Verification

The exact Broads polygon declined under v1 now returns **two SSSI features** under
v2, matching a fresh independent provider polygon query. Oxford and a St Mary’s
island interior sample are supported by the new profile. The tested other-nation,
England–Wales border and offshore areas are rejected. A separate coastal sample
near Scilly remains outside the profile; the correction does not claim every
coastal area is supported. All three prior live summaries/manifests remain
unchanged, and v2 readback matches after a fresh process reload. The isolated
live database still contains zero legacy datasets, features, Sites, assessments,
Evidence Snapshots or ModuleRuns.

- Combined acquisition/version suites: **62 passed on SQLite and PostgreSQL/PostGIS**,
  including 17 new tests for tidal support, historical preservation, profile/version
  mismatches, other nations/borders/offshore rejection, source consistency and CLI
  compatibility.
- Legacy assessment and snapshot reasoning checks: **35 passed on SQLite**.
- Python compilation and `git diff --check` passed. Existing Starlette and
  PostgreSQL geometry-reflection warnings remain.

See the [live verification record](verification/geographic-coverage-v2-2026-09-14.json)
for exact geometry, source identities, checksums, feature counts, independent
provider comparison, geographic acceptance/rejection checks and old-record parity.
Raw country geometry, SSSI features and databases remain outside Git. The first
boundary-download attempt failed with a network error; the bounded retry succeeded.
No hosted R2/Supabase integration, browser QA or frontend build was run because
those surfaces are unchanged.

## Next bounded task

Connect and independently verify the first additional national designation
publisher using an explicit publisher-specific source identity and coverage
policy. The England BFE profile must never be reused as another nation's support.
Cross-border composition, complete marine coverage, and authenticated application
access remain separate work. SSSI and Northern Ireland ASSI must retain their
native meanings. Geometry support across the UK is not four-nation data coverage.
