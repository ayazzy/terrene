# Sprint 004 Task 3 — Unified infrastructure entity map

## Outcome

Completed 14 September 2026. One persistent primary MapLibre scene is now the
spatial index for Terrene's current authorized entity graph across geographic
overview, Site investigation and Project Intelligence modes.

The map is no longer a portfolio backdrop. It retains exact Site boundaries,
selected Site assessment overlays and built-world context while entity search,
roster selection, map selection, command context, URL state and the existing
feature workspace all resolve through the same entity controller.

## Implementation and architecture

`infrastructure-entities.ts` creates a presentation-only union of authorized
Sites and Project Subjects. Site evidence state comes from the saved assessment
state. Project evidence state comes from existing immutable run summaries.

Project geography follows one rule: an authorized Project Subject is spatial
only when its exact `site_id` resolves to an authorized Site with saved
geometry. The Site boundary remains the geographic object; a distinct project
marker uses a display anchor derived from that exact Site envelope. A subject
with no Site, or an unavailable linked Site, has `geometry: null` and appears in
the `Unlocated intelligence` roster. Its name is never geocoded and selecting
it leaves the current camera unchanged.

The existing analytical map now also renders all current Site boundaries,
Site-linked Project markers and a searchable entity roster. Its layer manager
contains Site boundaries, Project Subjects, environmental evidence and Terrene
Earth built-world context. Existing available, mapped-zero, partial,
unavailable and unsupported wording is preserved. Selecting historical Site
evidence changes the selected boundary/evidence envelope without remounting the
primary map.

The former primary `PortfolioMap` path is no longer mounted. The existing
`SiteMap` module owns one stable primary instance plus the deliberately isolated
boundary editor. Full Site/Project content convergence remains Task 4; this task
only positions the existing workspaces beside the continuous map.

## Verification

- Frontend regression suite: **63 passed**.
- TypeScript: `npx tsc --noEmit` passed.
- Focused lint passed for the new/refined map, entity, read-state, shell and test
  modules.
- `app/page.tsx` retains its existing **19** diagnostics; this task added no page
  diagnostic.
- Production build passed with the existing large-chunk advisory.
- Browser QA at the available 1199 px desktop viewport covered Site selection,
  analysis collapse/reopen, global cross-entity search, Project evidence-section
  navigation and truthful layer state.
- Browser QA at **390×844** covered the map/entity roster and unlocated Project
  dossier split. The document and viewport were both exactly 390 px wide.
- DOM checks found exactly one primary operating-picture map and one MapLibre
  canvas.

The live verification database contained one saved Site and the real Site-less
Beacon Fen subject. One clearly labelled `Synthetic linked map QA project` was
added with an explicit relationship to that Site to verify the linked marker,
roster state and empty intelligence-run state. It makes no real-world claim.

Backend and PostgreSQL suites were not rerun because this task changes no API,
authorization, persistence, evidence or reasoning contract.

## Historical and compatibility impact

The interface performs authenticated GETs against existing Sites, Project
Subjects, Project Intelligence and Screening Context contracts. It adds no
generic entity table and changes no persisted evidence, reasoning identity,
hash, source, assessment or run. Existing meaningful hidden-layer IDs remain
URL-addressable. Legacy `CRC`/`crc` compatibility identifiers are unchanged.

The browser QA subject is an additive local synthetic record created through
the existing immutable Project Subject contract. It does not alter any Site,
evidence bundle or intelligence run.

## Known limitations

- The Site and Project feature workspaces retain their existing internal
  information architecture. Task 4 will migrate them to one consistent dossier
  component.
- Project evidence-state indexing currently reads each authorized subject's run
  summaries separately; pagination and a bounded aggregate read contract may be
  needed for materially larger portfolios.
- The legacy `portfolio-map.tsx` implementation remains in the repository for
  removal during Task 5 parity cleanup, but it is no longer a mounted primary
  map.
- Map camera state remains session-local and intentionally does not round-trip
  through the URL.

## Next task

Sprint 004 Task 4: dock the existing Site and Project Intelligence content into
one consistent entity-dossier pattern without changing its evidence, reasoning
or historical semantics.
