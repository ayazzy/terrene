# Selectable retained terrain in the operating map

15 September 2026

## Outcome

The existing Layers panel can search retained EA bare-earth terrain over the
current map view or across the organization, select one exact capture, toggle
its image, remove it or intentionally fit its extent. The elevation legend and
source/capture disclosure explain what the image represents. This improves
Terrene's ability to represent retained physical evidence geographically.

Implementation, desktop and narrow-screen acceptance are complete. After explicit
browser-access approval, the final responsive checks passed at 390 × 844 and
320 × 740.

## Implementation / architecture

The UI consumes the established `terrain_preview_v1` GET contract. It reuses the
organization-scoped acquisition catalogue with the EA DTM source filter. View
search fixes the query bounds at click time, and an empty filtered batch can
still offer continuation. Browse all removes the geographic filter. A new search
clears the current terrain selection. Nothing acquires new provider data.

The client validates the exact selected acquisition, attempt and manifest;
source/adapter, requested geometry, native CRS/units/count semantics, renderer,
image placement, grayscale range and missing alpha. It checks PNG dimensions,
RGBA8 header and SHA-256 before passing the image to MapLibre. Native evidence
verification remains the server's responsibility. The client checks the returned
fingerprint's format; it does not independently reproduce the server's canonical
metadata fingerprint or decode scientific measurements from preview colours.

Independent request versions, AbortControllers and 20-second timeouts protect
catalogue and preview state. Selection immediately removes an old image. Late
responses cannot restore a superseded, removed or disposed preview. Hiding during
a pending read stays hidden. Access failures clear retained selection; session
changes are checked during reads and on React updates, window focus and storage
events. Failures provide explicit recovery controls.

One fingerprint-keyed MapLibre image source owns one raster layer below the
Terrene entity/evidence layers. Placement and nearest-neighbour sampling come
from the contract. Renderer errors are isolated from basemap degradation, timed
out/failed images are removed, and style reload restores the selected source.
Show/hide and style reload do not move the camera. Only Fit terrain extent does.
Attribution is HTML-escaped before assigning the source's public attribution
field; it appears in the existing MapLibre attribution control.

On small screens, opening Layers temporarily hides the preserved dossier and
lets the map occupy the available height. The panel sits above the wrapped map
toolbar; closing it restores the same dossier. Capture metadata stacks vertically.
No dependencies, backend routes, persistence or model changes were introduced.

## Source

Environment Agency 1 m bare-earth DTM composite, source
`environment_agency.lidar_dtm_1m`, adapter `ea_lidar_dtm_wcs_v1`.
The display renderer is `ea_dtm_grayscale_web_mercator_v1`.
Original licensing and attribution are supplied by the verified capture.

## Evidence semantics

- A retained capture date is separate from the unknown local survey dates.
- Native EPSG:27700 1 m elevations use metres relative to Ordnance Datum Newlyn.
- The bounded EPSG:3857 image is a display derivative, at most 512 pixels per edge.
- The grayscale legend uses the valid native range inside the request. It is
  local to that capture; colours cannot be compared as measurements across captures.
- Transparent pixels are missing or outside the request. Native coverage and
  visible preview samples remain distinct; no visible samples does not imply
  that no native data exists.
- No search match establishes only that no retained capture matched. A read or
  image failure is unavailable evidence, never zero terrain.
- This layer is independent evidence and is not added to the saved assessment,
  its Evidence Snapshot, building heights or any flood/wetland interpretation.

## Files changed

- `app/terrain-preview.ts`: typed contract, validation and authenticated read.
- `app/terrain-layer-state.ts`: selection, paging, request cancellation and recovery.
- `app/terrain-map-source.ts`: image/layer lifecycle, placement and attribution.
- `app/terrain-map-layer.tsx`: hook, controls, source disclosure and elevation legend.
- `app/terrain-map-layer.module.css`: panel layout, wrapping and focus states.
- `app/infrastructure-map.module.css`, `app/operating-shell.module.css`: usable
  mobile Layers height and stacking while preserving dossier state.
- `app/map.tsx`: existing map integration and terrain-specific error isolation.
- `tests/terrain-map-layer.test.mjs`: contract, state and map lifecycle regressions.
- `docs/CURRENT-STATE.md`, `docs/ARCHITECTURE.md`, this report: implemented state.

## Verification

- All **149 frontend tests passed**, including **13 new terrain tests**.
- TypeScript `npx tsc --noEmit` passed.
- Focused oxlint passed for all six affected TypeScript files and the new test.
- `npm run build` passed, retaining the existing large-chunk advisory and Vinext
  route-classification notice.
- Tests cover corrupted identity/bytes/placement, null versus zero, authenticated
  no-store reads, changed sessions, late reads, selection/hide/removal, empty-page
  continuation, access failures, timeout/disposal, source order, style restoration
  and isolation from unrelated map errors.
- Backend suites were not rerun: this task changes no backend or scientific code.
  The preceding terrain-contract report records its own backend and pixel checks.

## Real-data verification

The live local browser selected acquisition
`11051877-6624-4e58-9b71-4f252eaa7465`, attempt
`9b0eeb7e-96e1-4499-afed-14bd063cfbdc`, for the retained Oxford terrain window.
The verified image displayed **511 × 512 pixels**, **1,000,000 / 1,000,000**
valid native cells, and **54.30–76.36 m ODN**. Environment Agency attribution
appeared in both the disclosure and map attribution. The UI explicitly labelled
survey dates unknown and the raster a historical composite.

These are readings of an existing capture. No new provider acquisition or
scientific measurement was performed in this task.

## Browser QA

At **1280 × 720**, an isolated in-app-browser tab opened the original Oxford
Station Site and its completed assessment. The following were exercised:

1. Layers → Search this view returned the retained EA DTM capture.
2. Selecting it reached “Terrain layer on · files verified.” The layer count
   increased from five to six and the source attribution appeared.
3. Fit terrain extent closed Layers and displayed the full grayscale request
   beneath the existing boundary, buildings, functional sites and railway.
4. The separate Legend panel included the terrain elevation range.
5. Hide terrain removed the image and its map attribution, reduced the layer
   count to five and retained the selected capture with “Terrain hidden.”
6. The Oxford dossier remained on its completed saved assessment, displaying
   its existing 92.9% built-up context and 279.3 m railway intersection.

Automated tests cover retries and style restoration; these were not additionally
exercised in the live browser. Browser access was temporarily rejected after a
usage-limit interruption. The user explicitly approved resuming localhost browser
access, and the following acceptance checks then completed:

- At 390 × 844, the original panel had only 124 px of usable height beneath the
  open dossier, and the wrapped toolbar covered part of it. The inherited button
  layout also squeezed capture metadata into columns.
- The responsive fix gives Layers 714 px of scrollable height, places it above
  the toolbar and temporarily hides the preserved dossier. Capture metadata now
  stacks vertically. No entity or assessment selection changes.
- Search this view and Browse all terrain returned the real Oxford capture.
  Selection rendered the verified image with the same 511 × 512 preview,
  one-million-cell availability and 54.30–76.36 m ODN legend.
- Source references expanded without horizontal overflow: document 390/390 px,
  panel 350/350 px and each reference 322/322 px client/scroll width.
- Hide/show and removal worked. Fit terrain extent closed Layers and restored
  the same Oxford dossier. The normal Close action also restored it.
- At 320 × 740, selection rendered successfully; the document measured 320/320 px
  and panel 294/294 px client/scroll width, with 610 px of scrollable panel height.
- Browser console inspection returned no warnings or errors. Restoring the normal
  1280 × 720 viewport restored the desktop dossier beside Layers. The temporary
  QA tab was closed and the viewport override reset.

All 149 frontend tests and the production build passed again after the CSS-only
fix. TypeScript and focused TypeScript lint results above apply to the unchanged
TypeScript implementation; they were not redundantly rerun for CSS changes.

## Historical / compatibility impact

This is a read-only presentation addition. It introduces no database writes,
source/version changes, new assessments, Evidence Snapshots or ModuleRuns. The
original Oxford Site, saved assessment and existing evidence remain accessible.
No raw rasters, previews, local databases, credentials or generated build output
are included in the commit. Existing CRC persistence identifiers remain intact.

## Known limitations

One EA DTM capture can be displayed at a time. Selection is session-local and is
not deep-linked or restored after reload. There is no hillshade, 3D terrain mesh,
elevation query, opacity control, national tile service or analytical raster use.
The catalogue remains a bounded live scan of retained captures, not a national
spatial index. DSM, satellite and weather are not rendered by this layer.
Physical-device touch and assistive-technology testing were not performed.

## Git

Branch: `feat/terrain-map-layer`, based on the required preview-contract commit
`f28453e`. Implementation commit subject: `feat: display retained terrain on the operating map`.
Implementation commit: `f28d20a`. The responsive follow-up is committed with
subject `fix: keep terrain controls usable on narrow screens`. No merge or
deployment is included.

## Recommended next task

As a separate implementation iteration, establish an exact-capture Sentinel-2
true-colour preview contract with calibrated retained RGB bands, pinned observation,
bounded placement, attribution and explicit cloud/nodata semantics. Its map UI
should follow only after that contract is verified.

## Root cause

The pre-existing mobile map height shrank around the open dossier, while Layers
retained a desktop-style top offset and a maximum-height deduction. A toolbar
wrapping onto two rows overlapped that panel. The new capture buttons also
inherited the application's flex layout. The follow-up changes only presentation:
mobile panel height/stacking, temporary dossier visibility and vertical capture
metadata. No historical or scientific state is modified.
