# Sprint 005 Task 3 — Dark spatial operating picture

## Outcome

Terrene's native infrastructure scene now has a dark, operator-grade visual and interaction system. The map remains the full-canvas analytical surface, while scene availability, source time, object class, selection and building-height eligibility stay explicit and evidence bounded.

This iteration improves Terrene's ability to represent and inspect reality. It does not add evidence, change an immutable scene contract or imply that a visually prominent feature is more certain than its source state.

## Basemap architecture

`NEXT_PUBLIC_BASEMAP_STYLE_URL` is the preferred MapLibre vector-style configuration. `NEXT_PUBLIC_BASEMAP_URL` remains supported as a legacy raster tile template. With neither set, local development uses attributed OpenFreeMap Dark. Because the public service has no SLA, production does not inherit it silently: an unconfigured production build uses a dark blank base, retains Terrene semantic layers and displays a configuration warning.

The former grayscale/invert raster treatment has been removed. GeoLibre remains a design and style-authoring reference; it is not bundled, embedded or treated as an evidence source.

## Interaction and visual system

- Near-black chrome and dark green-grey panels preserve contrast without competing with mapped evidence.
- Site boundaries use cyan; active selection uses amber; buildings use slate; functional sites use teal; stations use high contrast. Railway colours come only from exact retained classifications.
- Search/roster, Layers and Legend are mutually exclusive left-side surfaces. The selected-entity inspector remains the sole right-side surface on desktop and uses the existing bottom-sheet behavior on narrow screens.
- The scene opens in 2D. Perspective is offered only when the selected scene contains valid height evidence; it moves to 55 degrees and reveals only height-backed building extrusions. Returning to 2D restores pitch zero.
- The hierarchical layer manager and generated legend expose unavailable, partial, mapped-zero and unsupported states instead of treating missing data as zero.
- The legend identifies flat versus height-backed buildings, exact railway classifications, keyboard-selectable objects and visible source/retrieval timestamps. Map hover labels remain concise and source bounded.

## Evidence and compatibility

No historical assessment, Evidence Snapshot, ModuleRun, registry, wetland result, map-scene response or Screening Context response changed. Missing height still produces a flat outline and never a default extrusion. Basemap choice, camera pitch and presentation colour are not Earth facts.

## Verification

- Frontend Node regression suite: 75 passed.
- TypeScript: passed with `npx tsc --noEmit`.
- Focused lint on the changed map, scene, workspace, inspector and shell modules: passed.
- Production build: passed with the existing large-chunk advisory.
- Live browser QA confirmed the dark vector basemap and attribution, mutually exclusive Legend/Layers surfaces, truthful unavailable scene copy and keyboard-reachable controls.
- Software-WebGL captures covered 1440×1000, 1280×900, 1024×768 and 390×844. Exact DOM measurements at every width matched the requested viewport width and reported no horizontal overflow.
- Backend and PostgreSQL suites were not rerun because this task changes frontend presentation and environment configuration only.

## Known limitations

The normal local database still has no committed Oxford Station Evidence Snapshot, so this task cannot demonstrate Oxford objects or height-backed Perspective in the current development UI. Sprint 005 Task 4 must provision an isolated QA database from retained evidence without committing that database or duplicating raw evidence.

OpenFreeMap's public service is suitable for local development and evaluation, not an SLA-backed production basemap. A production operator must configure an approved vector style or legacy tile endpoint.
