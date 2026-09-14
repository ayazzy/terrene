# Sprint 004 Task 1 — Operating-picture state and defect contract

## Outcome

Completed 14 September 2026. Terrene now has one typed, URL-addressable
interaction contract for operating mode, selected Site or Project Subject,
historical assessment or intelligence run, dossier section, dossier visibility
and meaningful layer visibility.

The contract is a navigation and presentation state only. It creates no
evidence, assessment, Project Intelligence run or other persisted domain record.
Map camera position remains session-local.

## State contract

The canonical selection is discriminated as one of:

- no selected entity;
- `site` with an exact Site identifier; or
- `project_subject` with an exact Project Subject identifier.

The canonical historical artifact is either a `site_assessment` or a
`project_intelligence_run`, and only the artifact kind compatible with the
selected entity survives normalization. Site and Project Subject dossier
sections are likewise normalized to their supported sets.

The URL parameters are:

| Parameter | Meaning |
| --- | --- |
| `mode` | `map`, `list`, `site`, `project`, `compare` or `data` |
| `entity` + `id` | exact `site` or `project_subject` selection |
| `assessment` | exact Site assessment identity |
| `run` | exact Project Intelligence run identity |
| `section` | active compatible dossier section |
| `dossier=closed` | collapsed dossier; omission means open |
| `hidden` | canonical comma-separated meaningful layer identities |

Parsing and serialization are pure and deterministic. Identifiers use a
bounded safe character set. Layer identities are validated, deduplicated,
sorted and bounded to 64 entries. Mutually inconsistent state is removed rather
than coerced into a different entity or artifact.

Authorized API results provide the second validation boundary. A missing,
deleted or unauthorized Site/Project Subject is treated as unavailable and the
selection is cleared. An artifact not present in the selected entity's
authorized history is cleared without showing data retained from an earlier
selection.

## Interaction ownership

`operating-picture-state.ts` owns normalization, parsing, serialization,
history transitions, availability reconciliation and selection projections.
`use-operating-picture-state.ts` adapts that pure controller to browser history.

The Site workspace and Project Intelligence read controller now consume this
navigation state rather than owning competing entity/artifact/tab/panel state.
User navigation pushes history; automatic defaulting and invalid-state cleanup
replace the current entry. Back, forward and reload therefore restore one exact
valid investigation without replaying writes.

Async Site-history and Project Intelligence requests use generation fences and
scope their visible results to the currently selected entity and artifact. A
late response or a run belonging to another Project Subject cannot become the
visible result.

## Defect register

This register separates defects closed by Task 1 from structural and
browser-only gates intentionally owned by later Sprint 004 tasks.

| ID | Pre-task reproduction / evidence | Task 1 certification | Disposition and gate |
| --- | --- | --- | --- |
| OP-001 Divergent Site selection | Select a Site on the portfolio map, then open or clear it; `selectedMapSite` and `active` were independent React states. | Pure projection test proves map and Site workspace derive from one discriminated selection. Browser selection produced one matching URL identity. | Closed. |
| OP-002 Lost reload/back context | Open a Site or Project Subject, change section, then reload or use Back; in-memory state returned to defaults. | Controller tests cover direct URLs, reload, Back/Forward, dossier visibility and exact historical artifacts. Browser QA restored Site Evidence and Project Evidence states. | Closed. |
| OP-003 Stale async selection | Change entity while its history/run request is unresolved; the earlier callback could update shared state. | Generation-fence behavior test rejects late work. Site histories, Project run lists and run details are also hidden unless their entity/artifact identities match current URL state. | Closed for current read paths; Task 5 must retain the race regression during shell decomposition. |
| OP-004 Layer visibility lost | Hide a Site/environmental layer and reload. Previous visibility lived only in `SiteMap`. | Meaningful hidden-layer identities round-trip through the URL. Browser QA restored a hidden boundary and kept an explicitly hidden environmental layer hidden until a new focus request revealed it. | Closed for the existing Site map. Task 3 must reuse the same contract in the unified map. |
| OP-005 Separate map remounts | Open a portfolio Site: `PortfolioMap` is replaced by a keyed `SiteMap`; changing historical assessment also changes the Site map key. | Confirmed through component ownership and browser navigation. This state task does not pretend the map is persistent. | Open, Task 3 blocker. Browser instrumentation must prove one primary MapLibre instance survives entity/dossier navigation. |
| OP-006 Project Intelligence removes geography | Choose Project Intelligence from the navigation; the full Project workspace replaces the geographic view. | Confirmed in the current component branch and browser flow. URL state now preserves exact Project Subject/run context ready for docking. | Open, Tasks 3–4 blocker. The linked-project and unlocated-project acceptance flows must keep the operating map mounted. |
| OP-007 Map resize after dossier transition | Collapse and reopen the Site dossier while watching the MapLibre canvas. | Not reproduced at the available 1040 px browser viewport: container and canvas widths changed together from about 432 px to 832 px and back, using the existing `ResizeObserver`. | Browser-only regression gate for Task 5 at 1440, 1024 and 390 px; test both directions and repeated transitions. |
| OP-008 Focus loss after collapse/reopen | Activate the collapse control, then the floating reopen control. Both controls disappear after activation. | Confirmed: after reopen, focus fell back to the document rather than a stable dossier target. | Open, Tasks 2/5 blocker. Keyboard QA must assert deliberate focus transfer to the reopen control and then dossier heading/close control. |
| OP-009 Narrow-layout overflow | Exercise map, tabs, dossier and long evidence identities at 390 px. | Not re-certified in Task 1 because the available in-app browser viewport was 1040 px. Existing CSS has several independently scrolling and absolutely positioned surfaces, so this remains an explicit risk. | Browser-only gate for Tasks 2 and 5 at 390×844: no horizontal document overflow, reachable controls and retained map return path. |

## Verification

- Frontend regression suite: **55 passed**.
- TypeScript: `npx tsc --noEmit` passed.
- Focused lint passed for the new/refined state, Site workspace, Project
  Intelligence, map and test modules.
- `app/page.tsx` retains its existing **19** lint diagnostics; Task 1 introduced
  no additional page diagnostics.
- Production build passed with the existing large-chunk advisory.
- Browser QA at the available 1040 px viewport covered Site selection, direct
  Site URL, Project Subject/run defaulting, Project Subject switching, Site and
  Project section history, dossier collapse/reopen, reload, Back, invalid Site
  and assessment cleanup, layer visibility persistence, explicit layer focus
  and map resize. A clean final reload produced no browser warnings or errors.

Backend and PostgreSQL suites were not rerun because this task changes only
frontend interaction state and consumes the existing authenticated read
contracts.

## Historical and compatibility impact

No API, database, tenant, evidence or reasoning contract changed. Existing
Sites, assessments, Evidence Snapshots, ModuleRuns, Project Subjects, Project
Evidence and Project Intelligence runs are read unchanged. Historical
selection is represented in navigation state and never recalculated or
rewritten.

The existing portfolio map and Site map remain separate in this task. Their
convergence is deliberately deferred to Sprint 004 Task 3 after the Task 2 shell
establishes stable layout ownership.

## Next task

Sprint 004 Task 2: build the modern operating shell around this controller,
including stable keyboard focus and explicit narrow-layout QA, without yet
merging the two MapLibre lifecycles.
