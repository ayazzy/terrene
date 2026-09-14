# Sprint 004 Task 2 — Modern operating shell

## Outcome

Completed 14 September 2026. Terrene now presents the portfolio map, Site
investigation, Project Intelligence, comparison and source-register modes
inside one compact Infrastructure Operating Picture shell.

The default desktop navigation is a 60 px rail, leaving the geographic overview
as the dominant surface. Expanded labels and accessible compact-state tooltips
retain navigation clarity. At narrow widths the rail becomes an explicit
overlay with a close control, Escape handling and deterministic focus return.

## Implementation and architecture

`operating-shell.tsx` owns the global rail and command bar. Its CSS module owns
the shell's graphite/terrain tokens, layout, bounded feature-surface alignment
and responsive behavior. This avoids another appended override generation in
`globals.css`; legacy feature styles remain in place until their owning Sprint
004 iterations migrate them.

The command bar contains:

- globally positioned saved-Site search with exact retained Site results;
- the configured Oxfordshire pilot scope;
- actual available/total source-record counts from `/api/datasets`;
- the newest recorded retrieval date present in those authorized source
  records, or explicit loading/unavailable language; and
- the exact selected Site name or Project Subject kind and identifier.

It does not claim live telemetry, system readiness, sensor state, confidence or
latency. Project Intelligence retains its distinct evidence-binding as-of time
inside its evidence workspace; the command bar's date is explicitly labelled
`Source records`.

The former portfolio hero is now a compact infrastructure Site roster/status
strip. Existing Site and Project evidence distinctions, loading/error/empty
states, and all write controls are retained unchanged. The browser metadata and
remaining empty-state language now identify Terrene as infrastructure
intelligence rather than generic land intelligence.

## Accessibility and responsive behavior

Visible focus uses the existing high-contrast focus token. Closed mobile
navigation is visibility-hidden so its controls do not precede the menu button
in keyboard order. Opening the drawer focuses its close control; Escape or the
close control returns focus to the menu button.

The Task 1 dossier defect is closed: collapsing the Site analysis panel moves
focus to `Open analysis`, and reopening moves focus to `Collapse analysis
panel`. Reduced-motion rules cover the new rail and tooltip transitions. Source
states remain readable as text and never depend on colour alone.

At 390 px the command bar keeps scope and source-record date in its compact
context line, search on its own row and selection alongside the active view.
The tested document width remained 390 px with no horizontal page overflow.

## Verification

- Frontend regression suite: **60 passed**.
- TypeScript: `npx tsc --noEmit` passed.
- Focused lint passed for the shell and changed regression modules.
- `app/page.tsx` retains the existing **19** diagnostics; this task added no page
  lint diagnostics.
- Production build passed with the existing large-chunk advisory.
- Browser snapshots covered the populated geographic overview at **1440×900**,
  **1024×768** and **390×844**, plus the Site roster, Site dossier and Project
  Intelligence surface.
- Browser interaction covered saved-Site search and selection, narrow rail
  open/close, Escape focus return, keyboard order and Site dossier
  collapse/reopen focus transfer.
- Final browser logs contained no warnings or errors.

The retained conditional UI paths and read-state tests continue to distinguish
loading, empty, partial, unavailable and authorization states without removing
the shell. Backend and PostgreSQL suites were not rerun because this task does
not change an API, authorization, persistence, evidence or reasoning contract.

## Historical and compatibility impact

No Site, boundary, assessment, Evidence Snapshot, ModuleRun, Project Subject,
Project Evidence bundle or Project Intelligence run is created, recalculated or
rewritten by this shell. Existing APIs and tenant boundaries are unchanged.
Source dates and counts are projections of the records already returned to the
authorized frontend.

Legacy `CRC`/`crc` technical identifiers remain unchanged. The portfolio and
Site maps also remain separate; Task 2 deliberately changes their surrounding
shell without claiming persistent geographic context.

## Known limitations

- Command-bar search currently indexes saved Sites only. Project Subjects join
  the entity roster in Task 3, where location state can be represented
  truthfully.
- `PortfolioMap` and `SiteMap` still have separate MapLibre lifecycles.
- Project Intelligence still replaces geography, including for a Site-linked
  Project Subject.
- Legacy feature rules remain in `globals.css`; this task only establishes the
  bounded ownership destination for incremental migration.

## Next task

Sprint 004 Task 3: implement the unified infrastructure entity map, preserving
exact Site boundaries and representing Site-less Project Subjects as unlocated
without fabricated pins. Do not begin the Task 4 dossier migration.
