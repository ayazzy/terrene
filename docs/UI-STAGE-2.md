# Stage 2 — map and individual-site analysis

Implemented 8 September 2026. This iteration changes the frontend only. Stage 1 tokens, shell, navigation, evidence badges, Tabs, Accordion, Sheet and boundary dialog remain in use. No dependencies, datasets, API contracts, database schema, model calculations, thresholds, coverage formulas or immutable assessment records were changed.

## Information architecture

- **Overview:** physical potential, restoration need and implementation feasibility are separate categories. Required-input availability, unvalidated model confidence, key observations, ecological designation context and next evidence gaps are shown independently. Current team review stays in the compact workspace header; notes remain accessible from Overview.
- **Physical:** physical potential and hydrological relevance, supporting reasons, input observations, missing inputs and expandable calculations.
- **Ecology:** mapped cover, habitat-condition availability, restoration need, optional ecological opportunity and saved habitat/designation intersections. Mapped cover is not treated as a condition survey.
- **Constraints:** implementation feasibility, development/infrastructure evidence, model review flags and designation observations. A designation is not automatically scored as an exclusion.
- **Evidence:** the model's own required-input coverage, named gaps with reasons/roles, all normalized and derived observations, an availability filter, source-quality/model-method details and the original full evidence JSON export. Additional context gaps are distinguished from the required-input counter.
- **History:** immutable assessment selection updates both the map and model. Historical boundary versions and the current version are identified separately. Legacy runs remain accessible, with their reference observations under Evidence.

## Map and evidence interaction

MapLibre and the existing exact projected SVG overlap architecture remain. The map occupies the larger desktop workspace area. A collapsible analysis panel becomes a vertically stacked, independently scrollable panel below the map on narrow screens.

The compact Layers control groups the actual saved datasets into hydrology and ecology/designations. Basemap and each displayable intersection can be toggled independently. Colors, overlap values, no-overlap and unavailable states are explicit. Disabled geometry controls retain accessible evidence inspection. The boundary stays visible above the translucent overlaps. Scale, coordinates and a fit-boundary control support spatial inspection.

Observation-to-map links require exact pinned dataset IDs in the observation's raw lineage. No layer is invented for terrain, rivers or WorldCover observations. These are explicitly labelled as parcel observations without a retained displayable layer. Source details list derived observations using the selected dataset. Clicking a footprint opens its source evidence; click hit-testing preserves map dragging over that footprint.

The inline environmental inspector retains provider/dataset, observation and retrieval dates, source version, spatial resolution/support, method, uncertainty, provider-selection notes, parent observations and raw asset references/checksums. Numeric internal indices and calculation rules remain inspectable without presenting a universal restoration score.

## Boundary and review behavior

Drawing, undo, finish, WGS84 upload validation, replacement boundaries, notes, optimistic version checks and saved history use the existing workflow. Drawing an edit can display the current boundary as spatial context. Staged/reference boundary labels distinguish it from assessment geography.

The team decision control remains an editable current-site decision, including while viewing historical model evidence. It is never labelled as a model recommendation. Reports still use the existing saved-report endpoint and format.

## Verification performed

- **Backend regression suite:** `.venv/bin/python -m pytest -q` — 98 passed on the isolated default SQLite test configuration. Existing dependency deprecation warnings remain. PostGIS tests were not rerun in this UI iteration.
- **Frontend semantic regression tests:** `node --experimental-strip-types --test tests/site-evidence.test.mjs` — 5 passed. Covers categorical watercourse yes/no, null versus measured zero, partial derived evidence, null output/category handling, and exact pinned dataset lineage. Node prints its experimental type-stripping warning.
- **TypeScript:** `npx tsc --noEmit` passed.
- **Focused lint:** map, nature panel, evidence helpers, overlay component and new tests passed.
- **Repository lint:** `npm run lint` reports 40 pre-existing diagnostics: 21 in the retained page/API/state code (18 explicit-any declarations, effect-state, fetch-options and floating-promise rules) and 19 in untouched shared UI components/hooks. A HEAD copy of the page was checked to distinguish inherited diagnostics; no lint rules were suppressed.
- **Production build:** `npm run build` passed. Existing large-chunk and Vinext route-classification notices remain.
- **Diff validation:** `git diff --check` passed.

### Browser QA against the running local API

Performed in the in-app browser, using actual persisted records rather than mocked responses:

1. Opened **Port Meadow — public reference site**, its completed real assessment, and its incomplete wetland evidence: very high physical potential, restoration need/feasibility not established, 5/10 required inputs, mean slope 1.18°, watercourse intersection **Yes**, 97.04% flood overlap and 0.07% mapped development.
2. Inspected physical, ecology and evidence sections, named missing inputs, unavailable-observation filtering, full flood-source provenance, exact map linkage and source-to-derived-observation dependencies.
3. Inspected flood and SSSI overlays together; toggled SSSI independently, verified its SVG geometry disappeared and returned, toggled the basemap, highlighted flood evidence, panned over overlays and opened source details by clicking mapped geometry.
4. Opened older Port Meadow assessments and returned to latest. Opened **Synthetic drawing — workflow example** at current v2 and its historical v1; header, area (98.34 ha), map label and saved overlays changed to the historical boundary.
5. Staged the real Port Meadow MultiPolygon GeoJSON in the edit dialog; drew three vertices, undid to two (Finish disabled), added a third and finished back to the validation dialog. Cancelled the staged edit. Existing user boundaries were not overwritten. Saving/versioning/review mutations are covered by backend regressions rather than a new browser write to these reference records.
6. Submitted Run screening for Port Meadow. The existing deduplicated assessment was retained. Opened the saved report preview successfully.
7. Inspected the default desktop viewport, 1024×768, and 390×844. At 1024 the map measured 606 px against a 350 px panel; at 390 there was no horizontal page overflow. Collapsed/reopened analysis and reached History through the narrow tab strip. Restored the browser viewport afterward.
8. Checked the retained `list_crc_sites` WebMCP tool: valid input returned the three saved sites; unexpected input was rejected.
9. Console review caught a MapLibre style-loading exception during development hot reload. Added a style-ready guard and map-instance dependencies. The clean-reload pass covering site selection, history, exports, layers and responsive controls produced **no new browser warnings or errors**.
10. API read-back confirmed all three original boundaries, boundary versions, latest assessment IDs and saved result objects were unchanged after the browser workflows.

## Limitations and deployment

No terrain/rivers/land-cover display layers or new environmental data were added. The model remains unvalidated; missing soil, habitat and infrastructure evidence remains unknown. Evidence gaps include additional optional/context variables, so their count is deliberately not presented as the required-input denominator.

The existing Sites reservation was checked: it has no live publication and no production environment variables, including no `CRC_API_URL`. External API/auth/storage deployment remains unconfigured. This implementation was therefore validated locally; an API-disconnected frontend was not published as a finished product. The development session started for QA was stopped afterward. Use the existing `./scripts/dev.sh` workflow to reopen the local application.

## One recommended next UI work package

Evidence-aware multi-site comparison: carry the same separate dimensions, input gaps, assessment/boundary dates and human decisions into side-by-side investigation. Do not introduce universal ranking. This package was not implemented in Stage 2.
