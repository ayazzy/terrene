# Stage 3 — map-first Sites home

Implemented 8 September 2026. This is a frontend-only extension of the existing Stage 1 shell and Stage 2/2.1 analysis work. Existing uncommitted work was preserved.

## Implemented

Sites opens in Map mode. A compact Map/List switch retains the existing Sites table, search, review filtering, comparison checkboxes, metadata and team decisions. List state survives mode switches within the running workspace. Comparison's Choose sites action explicitly returns to List, where its existing checkboxes live.

The overview uses a dedicated dynamically loaded MapLibre component. It reuses the configured `NEXT_PUBLIC_BASEMAP_URL` (OpenStreetMap by default) and exact projected SVG architecture. Only the overview basemap canvas is desaturated, inverted and contrast-restrained; the analytical map is untouched. The existing graphite sidebar joins a dark portfolio header. Pale stone boundary outlines, low-opacity fills, compact numbered locators and moss selection provide hierarchy without glow or decorative animation. Attribution remains visible and unfiltered.

Every footprint uses the current saved site's `geometry`, including MultiPolygon components and holes. Historical assessment geometry never supplies portfolio locations. Locator anchors are actual boundary vertices. Missing geometry receives no invented location and remains accessible through the picker and List. Initial framing and Fit to saved sites use all saved positions; the empty workspace uses the existing Oxfordshire regional starting view.

Click a boundary or numbered locator, or use the keyboard-accessible saved-site picker, to select a site. Its small card shows name, current boundary version and team review state. Open site analysis calls the existing `openSite` handler. Map controls are limited to fit and zoom. Rotation and visual-effect animations are disabled. The New site action reuses `startNew`, the existing dialog, drawing and GeoJSON upload.

The only portfolio summary is Oxfordshire pilot, the live site count and the count marked Investigate. Pilot naming follows the existing application shell; organization/portfolio administration was not added.

## Verification

- Frontend tests: `node --experimental-strip-types --test tests/*.test.mjs` — **13 passed**, including four new geography tests. They cover current versus historical geometry, union bounds, holes and disconnected components, missing/invalid positions, and geometry collections. Existing evidence and read-failure tests also pass. Node's existing experimental type-stripping warning remains.
- TypeScript: `npx tsc --noEmit` — passed.
- Focused lint: `npx oxlint app/portfolio-map.tsx app/portfolio-geometry.ts tests/portfolio-geometry.test.mjs` — passed. Including the existing `app/page.tsx` reports 20 inherited diagnostics (explicit-any, existing effect-state, fetch-options and status-element rules); no suppressions were added. The new page integration introduces none of those patterns.
- Production build: `npm run build` — passed. Existing large-chunk and Vinext route-classification notices remain.
- `git diff --check` — passed.
- Backend tests were not rerun: this iteration changes no backend, calculations, APIs or persistence code.

### Browser QA actually performed

Used the in-app browser against the actual local API/PostGIS records. Inspected the default browser viewport and viewport overrides of 1440×900, 1024×768 and 390×844 (the browser's existing display scaling remained in effect).

1. Confirmed a fresh reload defaults to Map, with all three existing sites visible in the Oxfordshire region: Test Plot near Woodstock; Port Meadow — public reference site north of Oxford; Synthetic drawing — workflow example west/northwest of Port Meadow. The existing synthetic record is shown exactly as stored; no additional geography or records were created.
2. API boundary bounds: Test Plot (-1.400324, 51.859904)–(-1.369120, 51.866986); Port Meadow (-1.297523, 51.761316)–(-1.272981, 51.785485); workflow example (-1.315342, 51.783956)–(-1.299687, 51.792026). Current boundary versions are 1, 1 and 2 respectively.
3. Selected Port Meadow with its locator, Test Plot by clicking its footprint, and the workflow example through the saved-site picker. Opened all three through Open site analysis and returned through All sites. Confirmed Port Meadow's neutral analytical basemap and existing evidence workspace remain intact.
4. Exercised map panning over a footprint, zoom in/out, Fit to saved sites, selection clearing, Map/List switching and reload. Fixed a stylesheet specificity issue found during the first map render, and a selected-value label issue found in the picker.
5. Inspected desktop and narrow List views. Searched Port Meadow; verified search survives Map/List switching; cleared search; selected two comparison checkboxes; opened the existing comparison and returned through Choose sites. Filtered by Investigate and obtained only Port Meadow. Existing decisions were not changed.
6. Opened New site from Map. Staged the existing Port Meadow GeoJSON and saw MultiPolygon ready for validation. Entered the drawing workspace, placed three vertices, undid to two (Finish disabled), added a third, and finished back to the dialog with a Polygon ready for validation. Closed without saving. The initial hidden-input browser automation attempt timed out; using the visible Upload GeoJSON control succeeded.
7. On narrow screens, verified no horizontal document overflow in Map or List. The table scrolls inside its own container. Fixed tab-container flow and framing padding found during QA. With a selected site, all boundary footprints end above the bottom picker/card, with the controls remaining accessible.
8. The final clean-reload interaction pass covered zoom/fit, selection, analysis opening, Map/List and New site; the browser console returned **zero warnings and errors**. Earlier local-service unavailability was resolved before this pass. Development hot reload also emitted server-side renderer notices and one map fit/padding warning during a transient resize; these were absent from the final clean reload and are distinct from its console result.
9. Full API read-back before/after QA matched exactly: all three site records, geometries, boundary versions, review states, assessment IDs and result objects were unchanged.

## Preserved and deferred

The detailed site-analysis information architecture, layer controls, history, evidence lineage, reports, model calculations, APIs, ingestion and team-review semantics were not changed. No globe, satellite feature, environmental-layer expansion, comparison redesign or additional dataset was introduced.

The raster basemap retains its source's labels and road density; independent label/water styling would need a separately styled basemap. This overview is for the current small portfolio; clustering and large-portfolio pagination remain deferred. Map/List preference is session state and fresh reloads intentionally start in Map.

### Narrow hierarchy polish

The configured overview source remains a pre-rendered raster tile. MapLibre can therefore change only whole-image properties (opacity, saturation, contrast and tone): CRC cannot independently suppress minor roads, road shields, POIs, minor settlements or land-use detail, nor preserve only water, major settlements and major transport, without moving the overview to a vector style/source. The portfolio raster is now globally lower-contrast and partially transparent over the existing dark ground so broad Oxfordshire context remains legible while saved boundaries lead. The detailed analysis map is unchanged.

Desktop chrome was reduced without removing controls: Map/List is smaller and quieter, the saved-site picker is narrower and shorter, the map buttons are slightly smaller, and the pilot summary has marginally less padding. New site retains the established primary treatment.

Numbered locators remain minimal. Hover, keyboard focus, click/tap selection now reveals a compact context label using the saved record's name, current assessment area when available, and review status. Selection keeps that label visible until another site is selected or the selection is cleared; the existing selected-site card and analysis-opening action remain unchanged.

Sites hosting was checked: the reservation remains private and unpublished, with no production environment variables and no hosted `CRC_API_URL`. Publishing an API-disconnected frontend would not produce a functioning CRC application. No deployment, credential/configuration change or source publication was performed. Local QA services started for this work were stopped after validation.

## Recommended next UI iteration

Evidence-aware multi-site comparison: bring the separate physical, ecological and feasibility dimensions, missing inputs, assessment/boundary dates and human review decisions into the existing side-by-side workflow without a universal ranking. Not implemented here.
