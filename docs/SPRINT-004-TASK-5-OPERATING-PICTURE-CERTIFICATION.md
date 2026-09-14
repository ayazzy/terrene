# Sprint 004 Task 5 — Operating Picture certification

## Outcome

Sprint 004 is complete. Terrene now has one primary Infrastructure Operating Picture map across geographic overview, Site investigation and Project Intelligence. The superseded portfolio-map implementation and its presentation rules were removed after parity was verified.

The entity roster is closed by default so it no longer obscures the geographic canvas. At widths of at least 1280 px the open dossier is capped at 40% of the available content width, preserving at least 60% as visible map. Site and Project dossiers continue to stack below the map at narrow widths.

## Implementation and defect closure

- Removed `app/portfolio-map.tsx`; the isolated boundary editor is the only additional MapLibre lifecycle.
- Reassigned map regression coverage to the persistent `SiteMap` operating scene and added a guard that the obsolete controller cannot return.
- Removed obsolete portfolio-map, pre-dossier Site and duplicate Project-list CSS while preserving the bounded operating-shell, infrastructure-map and entity-dossier ownership introduced during Tasks 2–4.
- Kept entity selection, layer visibility, dossier visibility, section and historical artifact in the existing URL-addressable controller.
- Added explicit local map readiness attributes based on the MapLibre load event. These support development measurement only and do not claim live or real-time telemetry.
- Preserved keyboard focus transfer between dossier collapse and reopen, stale-request fencing, canonical hidden-layer state and fail-closed URL reconciliation.
- Replaced the last user-facing “land opportunities” phrase and removed “Live changes” language from contextual read failures.

## End-to-end proof

The connected local application demonstrated:

1. The map reached its explicit ready state and remained mounted through Site and Project transitions.
2. A saved Site and a Site-linked synthetic Project Subject were directly selectable from the shared map roster/marker.
3. Beacon Fen remained in `Unlocated intelligence` with the explicit state `No verified geography`; it received no map marker and its dossier showed supported consent with construction and grid evidence unresolved.
4. The Beacon Fen source passage, source version and exact claim reference were inspectable while the map remained present.
5. The four-run synthetic North Fen history allowed an earlier three-bundle evidence envelope to be selected; the historical banner, bundle count and run identity changed together without rewriting the latest run.
6. The retained Ancient Woodland layer toggled from one rendered path to zero and back to one; the canonical URL gained and then removed `hidden=environment:woodland`.
7. The prepared built-world object/layer relationship remains covered by the deterministic map-feature and operating-map regression tests. The currently connected `test` assessment has no prepared built-world map evidence, and the interface truthfully reported that absence rather than substituting current objects.

## Browser QA

- Interactive in-app browser QA at 1086 px covered Site/Project selection, exact evidence navigation, conflicts and unknowns, historical run selection, retained-layer visibility, repeated dossier collapse/reopen and focus restoration.
- The map and MapLibre canvas remained the same full operating scene through panel transitions. At the available 1026 px content width the dossier occupied 48% and the document had zero horizontal overflow.
- Software-WebGL headless Chrome screenshots at 390×844 covered the Site and Beacon Fen Project dossiers. Closing the entity roster by default left the map visible above both narrow dossiers.
- Local ready-event observations ranged from 68 ms on initial inspection to 940 ms after hot reload. This is a development baseline only; it is not a production latency or real-time claim.

## Verification

- Frontend Node regression suite: **71 passed**.
- `npx tsc --noEmit`: passed.
- Focused `oxlint` for the changed map, shell and regression files: passed.
- Focused formatting check for the changed map, shell and regression files: passed.
- Production build: passed with the existing large-chunk advisory.
- `app/page.tsx`: retains the existing **19** lint diagnostics; this task added none.
- `git diff --check`: passed.

Backend and PostgreSQL suites were not rerun because this task changes no API, persistence, evidence or reasoning contract.

## Historical and compatibility impact

UI navigation continues to use authenticated GET reads. No Site, assessment, Evidence Snapshot, ModuleRun, Project Evidence bundle, evidence binding or Project Intelligence run was created, edited or deleted by this task. Historical selection remains a read-only change of the complete evidence envelope.

The Design Study `/api/projects` compatibility surface and all retained `CRC` technical identifiers are unchanged.

## Known limitations

- The local map remains visually sparse because the connected development records contain one saved Site and only one explicitly Site-linked synthetic Project Subject.
- Built-world objects require a prepared immutable Screening Context run. The currently connected Site assessment has none.
- The production bundle retains its pre-existing chunk-size advisory.
- Product workflow and customer value remain unvalidated; this sprint certifies the interaction architecture, not a commercial recommendation.
