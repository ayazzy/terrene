# Retained capture browser

Implemented 15 September 2026.

## Outcome

Data sources now offers a read-only browser for independently retained captures.
Users can filter by source, requested location and evidence/capture dates, continue
a bounded search, and open an exact successful capture for file verification,
availability, source caveats and immutable references. The existing assessment
source library remains available in its own disclosure below the browser.

## Implementation / architecture

`app/acquisitions.ts` models and checks the existing versioned catalogue/detail
contracts. Reads use same-origin authenticated GETs, AbortSignal and no-store caching.
Detail URLs are constructed from the selected acquisition/attempt IDs, never from
an untrusted response URL. The detail must match the selected source, adapter,
request, geometry and manifest identities. Unusable shapes, dates, counts, paging
or versions fail with an explicit error. Session changes during a read are rejected.

`app/acquisition-browser-state.ts` owns the read lifecycle independently of React.
New searches clear old results and selection. Selection changes clear previous
detail immediately. Aborts plus version fences reject late responses even if a
transport ignores abort. Continuation is single-flight, de-duplicates exact captures
and preserves the applied query. A failed continuation can retry its same cursor;
a non-advancing cursor fails explicitly. Access failures clear both list and detail.
Unmounts cancel and fence pending reads. There is no background acquisition/polling.

`app/acquisition-browser.tsx` consumes this state using `useSyncExternalStore`.
The existing Data sources view mounts it. The form distinguishes editable filters
from applied search context. It offers all retained locations, a UK bounding extent,
Oxford/Edinburgh/Cardiff/Belfast area presets and custom WGS84 bounds. These presets
are rectangles, not administrative/source-coverage boundaries. Searching submits
one bounded page; users explicitly continue, including through empty batches.

Selecting a capture focuses the detail heading; closing returns focus to its result.
Detail exposes availability only after retained-file verification succeeds. Original
source-specific caveats remain beside the counts; technical IDs and artifact hashes
are progressively disclosed. Desktop uses list/detail columns and narrow layouts
stack them, with long references wrapping within the page.

The same-origin proxy forwards upstream Cache-Control so authenticated catalogue
responses retain the backend's no-store policy. The command bar's data-view source
count and mobile context are labelled as the assessment registry, avoiding a false
claim that its count or Oxford pilot scope describes independent captures.

## Source

The browser consumes the six existing independent sources: England/Scotland SSSI,
EA DTM/DSM, Sentinel-2 and NASA POWER/MERRA-2 weather. It adds no provider or expanded
coverage and does not copy verification captures into the operational tenant.

## Evidence semantics

- Location filters intersect original requested polygons or points. Weather query
  points do not establish grid or parcel coverage; polygon bounds are labelled as
  bounds rather than full source/valid-cell geometry.
- Search dates are inclusive UTC days. Evidence dates preserve satellite instants,
  weather daily intervals and unknown vector/LIDAR dates. Capture dates are a
  separate filter and never substitute for survey/observation time.
- A one-day search matching a month-long capture still shows that original interval
  and its full availability counts. No clipping, resampling or new inference occurs.
- Metadata-checked list entries explicitly require opening to verify retained files.
  File verification is integrity, not scientific accuracy or predictive confidence.
- Zero present days is retained as zero; missing/invalid contract counts fail rather
  than becoming zero. Empty batches with continuation are distinct from completed
  searches with no matches, and neither establishes real-world absence.

## Files changed

- `app/acquisitions.ts`: client contracts, readers, identity checks and display helpers.
- `app/acquisition-browser-state.ts`: cancellable search/continuation/detail state.
- `app/acquisition-browser.tsx` and its CSS module: browser and responsive detail.
- `app/page.tsx`: Data sources integration and separate assessment registry disclosure.
- `app/operating-shell.tsx`: optional source/context labels; other views retain defaults.
- `app/api/[...path]/route.ts`: preserve upstream Cache-Control.
- `tests/acquisition-browser.test.mjs`, `tests/operating-shell.test.mjs`: new behavior
  checks and adjustment of the existing label regression.
- Current State, Architecture, this report and its compact QA record.

## Verification

All **136 frontend tests pass**, including **15 new tests** for contract rejection,
exact detail identity, zero availability/leap-day display, late response fencing,
empty continuable pages, single-flight pagination, duplicate suppression, retry,
non-advancing cursors, closing/unmounting, access-failure clearing, bearer/no-store
requests, session changes, safe detail URL construction and cache-policy forwarding.

TypeScript, focused lint and formatting pass. The production build succeeds with
the existing large-chunk advisory. `app/page.tsx` has its existing **19** lint
findings; no unrelated lint cleanup was attempted. `git diff --check` passes.
Backend/PostgreSQL suites were not rerun: their acquisition implementation, schema,
authentication and persistence are unchanged. The prior catalogue's backend
acceptance remains in [its report](ACQUISITION-CATALOGUE.md).

## Real-data verification

The frontend parser, UTC labels and geometry bounds accepted **15 existing real
captures across all six sources and four families**, read from their original
verification databases through read-only SQLite connections. This checks the new
client against retained backend output rather than only synthetic response fixtures.

A temporary loopback API used the existing weather verification tenant and a
read-only SQLite connection, with hosted authentication explicitly outside this QA.
The browser listed four real February 2024 weather captures. Oxford and Cardiff
were opened and verified; both retained 29/29 present days in all six variables,
with exact point, acquisition, attempt and manifest identities. No provider refresh,
new capture, data copying or historical identity rewrite was performed.

## Browser QA

- Normal development tenant: completed empty catalogue and separate retained
  assessment registry display correctly.
- Desktop, 1280 CSS pixels: location filtering, native date input, Oxford leap-day
  search, exact detail, original February interval/29-day counts, technical reference
  disclosure and close-to-result keyboard focus passed without horizontal overflow.
- Narrow, 390 CSS pixels: the actual app rendered in an isolated fixed-width iframe
  because the in-app browser's viewport override did not take effect. Filters stack;
  Cardiff search, selected detail, expanded long hashes and focus restoration work.
  Document width and scroll width are both 390 px; detail is 358 px wide.
- Stopping the temporary QA API makes the detail explicitly unavailable and removes
  the previous verified body. Restarting it and using Retry restores verified data.
- Temporary QA servers/tabs were closed. The running API was reconnected to the
  original Oxford database and the frontend was restored. Oxford’s original completed
  assessment, analyst brief, five retained scene sources and mapped infrastructure
  were opened successfully. Independent verification captures remain isolated.

The compact [QA record](verification/acquisition-browser-2026-09-15.json) records
these checks without raw evidence, databases, secrets or screenshots in the repo.

## Root cause of the temporary Oxford disappearance

The initial API restart used the repository's default test database instead of the
previously retained external Oxford QA database. No Oxford record was deleted.
The intact original database contained the completed assessment
`c10d373d-444d-5d04-9f3b-25c36a8f0d45`, one Evidence Snapshot and two ModuleRuns.
The runtime was reconnected to its original database/object directory, and only
`CRC_DATA_DIR` / `DATABASE_URL` were saved in the ignored local `.env`, preserving
other settings. The standard `scripts/dev.sh` reads these settings. Local paths
and database contents are not committed. Browser readback confirmed restoration;
no assessment was rerun or regenerated.

## Historical / compatibility impact

No backend contracts, sources, acquisitions, snapshots, assessments, model versions
or bindings changed. The only proxy change preserves cache policy. The library
renders retained projections and performs GETs only. Existing map/site/project
navigation defaults and the assessment source data are preserved.

## Known limitations

This is a library view, not a raster map layer, point-cloud viewer, source acquisition
control, forecast or climate model. Filters/selection reset when the browser unmounts
and have no dedicated deep links. Presets are bounding boxes; geocoding and exact
administrative-boundary search are absent. Backend bounded-scan/coverage limits remain.
Hosted end-to-end authentication and end-user workflow acceptance are unverified.

The standard local-development organization currently has **no independent
captures**, so its library is empty. Real-data UI checks used the separately retained
verification tenant; they are not a populated operational library. The assessment registry remains accessible below it. Oxford’s five map-scene
sources are retained with its assessment/snapshot and are not automatically
converted into independent acquisitions.

## Git

Branch: `feat/acquisition-browser`, based on verified catalogue commit `821ebb0`.
Implementation, tests and documentation form one coherent feature commit; repository
history records its final identity. Generated output and temporary QA data are excluded.

## Recommended next task

Acquire an explicit bounded area/date/source selection under the active development
organization using existing operator services and fresh immutable request identities.
This populates the operational library while preserving historical verification
ownership. New providers, raster map rendering and acquisition controls can then be
planned as separate bounded iterations.
