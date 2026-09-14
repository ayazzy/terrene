# Sprint 004 Task 4 — Docked entity dossiers

## Outcome

Completed 14 September 2026. Sites and monitored Project Subjects now use one
consistent right-hand entity dossier beside the persistent Infrastructure
Operating Picture map.

The shared dossier identifies the selected entity, its defensible geography,
the exact assessment or intelligence-run envelope, evidence time and
historical state. It can collapse without clearing the entity, section or
historical artifact. Reopening restores the same investigation context.

## Implementation and architecture

`entity-dossier.tsx` owns the common dock identity band, map-layer access,
collapse control and historical-envelope banner. Existing Site Overview,
Evidence, Models and History content is mounted inside it without changing its
source or reasoning semantics. Project Intelligence uses the same shell and no
longer repeats a second Project Subject list; the persistent map roster and
global search remain the entity index.

Project conclusions, conflicts and unresolved questions now expose their claim
references as controls. Selecting one opens and focuses the exact retained
source assertion, including passage, source version, publication/recording
time and correction relationship. Source assertions and Terrene conclusions
remain explicitly labelled as different kinds of information.

Selecting an earlier Site assessment or Project Intelligence run updates the
complete dossier evidence envelope and displays a prominent historical state
with a return-to-latest action. Site historical selection continues to update
the exact boundary and mapped evidence together. Site-less Project Subjects
remain unlocated and do not move the map.

The dossier can open the primary map's existing layer manager. The entity roster
is hidden while that manager is open so the two map controls cannot obstruct
one another.

## Verification

- Frontend regression suite: **68 passed**.
- TypeScript: `npx tsc --noEmit` passed.
- Focused lint passed for the shared dossier, Project Intelligence and map
  modules. `app/page.tsx` retains its existing **19** diagnostics and gained no
  new diagnostic.
- Production build passed with the existing large-chunk advisory.
- Desktop browser QA at the available 1254 px viewport covered the mapped Site
  brief, the Site-linked synthetic empty-run subject, Beacon Fen's supported
  consent and insufficient construction/grid evidence, exact claim navigation,
  the layer-manager handoff, dossier collapse/reopen and a historical synthetic
  Project Intelligence run.
- Headless Chrome QA at **390×844** with software WebGL covered both the Site and
  Project Subject map/dossier split and the two-row Project section navigation.

Backend and PostgreSQL suites were not rerun because this task changes no API,
authorization, persistence, evidence or reasoning contract.

## Historical and compatibility impact

No Site, boundary, assessment, Evidence Snapshot, Project Evidence bundle,
binding, ModuleRun or Project Intelligence run is created or changed by this
interface work. Historical selection remains GET-only and exact. Existing
`CRC`/`crc` compatibility identifiers and Design Study persistence are
unchanged.

The local synthetic linked Project Subject created during Task 3 remains only a
clearly labelled browser-QA record and has no evidence or intelligence run.

## Known limitations

- Project Subjects still have map geography only through an explicit Site
  relationship; Beacon Fen is correctly unlocated.
- The current map roster can dominate the short map region on narrow screens;
  compact mobile roster treatment remains a later refinement.
- Project evidence-state indexing still performs one run-summary read per
  Project Subject.
- Versioned Design Studies remain API-only and are not linked into either
  dossier.

## Next task

Sprint 004 Task 5: remove superseded presentation paths, close parity and
responsive defects, and certify the complete Infrastructure Operating Picture.
