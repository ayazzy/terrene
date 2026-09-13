# Sprint 004 — Infrastructure Operating Picture

## Status

Active. Tasks 1–2 completed 14 September 2026. This sprint begins from GitHub `main` at `e40a9f4`, after the Beacon Fen Task 2 merge. Sprint 003 is closed incomplete; no practitioner or customer validation is implied.

## Repository basis

The current implementation has strong evidence and reasoning semantics but presents them through disconnected application surfaces:

- `app/page.tsx` is a 1,812-line client component that owns global navigation, map/list mode, site selection, assessment history, editing and several workflows.
- `app/globals.css` is 3,981 lines and contains multiple generations of shell, portfolio and analysis-workspace presentation rules.
- The portfolio uses `PortfolioMap`, while site analysis uses a separate `SiteMap`. Opening a site replaces and remounts the geographic context rather than preserving one operating picture.
- Project Intelligence is a separate full-page workspace. Entering it removes geography completely, even when a Project Subject is linked to a Site.
- `view`, `sitesView`, `selectedMapSite`, active Site, Project Subject and historical-run selection are independent in-memory states. Reload and browser back/forward do not restore the investigation.
- The default product language still leads with “Land opportunities” and an Oxfordshire pilot map, which understates the infrastructure-intelligence platform.
- Project Subjects may truthfully have no Site. The current UI cannot distinguish a verified map-linked project from an unlocated Project Subject in one spatial workflow.
- The current live interface changes visual systems between the dark portfolio map, light Site Analysis Workspace and document-like Project Intelligence workspace.

These are structural interaction problems. A darker palette alone will not solve them.

## Inspiration and limits

The sprint takes interaction inspiration from:

- [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view): one explorable spatial canvas, direct entity selection, modular layers, a compact intelligence HUD and scene state that can be handed off.
- [Anduril Lattice Command & Control](https://www.anduril.com/lattice/command-and-control): a common operating picture that presents operator-relevant entities and decision points rather than disconnected dashboards.
- [Palantir Gotham AI-enabled operations](https://www.palantir.com/assets/xrfr7uokpv1b/3A0y10xksgXENvRMNaAsUu/ed8f7f1ed534c0101f64536a85f7297b/Gotham_AI-Enabled_Operations_White_Paper.pdf): integrated historical and current information, inspectable operational context and durable chronology.
- [Stellaria](https://stellaria.ai/): dense but ordered source, reasoning and delivery states in one geospatial intelligence vocabulary.

Terrene will not imitate military classification markings, pretend to have live sensors, manufacture telemetry, add cinematic effects, or copy another product's source code or branding. The useful pattern is the operating picture: geography remains present while the operator selects an entity, inspects evidence, changes temporal context and decides what to investigate next.

## Sprint goal

In two weeks and five tasks, replace the disconnected portfolio/site/project navigation model with a coherent Infrastructure Operating Picture v1:

> Find an infrastructure entity → preserve its geographic context → inspect source evidence and Terrene conclusions → move through current and historical state without losing the investigation.

The map becomes the continuous primary interaction surface on desktop. Panels, lists and dossiers serve the map; they do not replace it. The architecture must remain truthful for both spatially linked and unlocated Project Subjects.

## Product principles

1. **Infrastructure entities first.** Sites are geographic areas of investigation; Project Subjects are monitored real-world projects; Design Studies remain a separate technical scenario contract. The interface must not collapse them into one ambiguous “project.”
2. **One operating picture.** Portfolio, Site evidence and map-linked Project Intelligence use one persistent MapLibre scene and one selection model.
3. **Truth before spectacle.** No Project Subject receives a pin unless its geometry comes from an authorized Site relationship. “No verified geography” is a first-class state.
4. **Evidence before recommendation.** Source assertions, Terrene conclusions, unknowns and conflicts remain visually and semantically distinct. No risk score, confidence bar or pursue/monitor/dismiss recommendation is introduced.
5. **Context survives navigation.** Selected entity, workspace section, historical artifact and meaningful layer state are URL-addressable and restore on reload and browser back/forward.
6. **Dense, not cluttered.** The desktop interface should feel like a modern professional operating console, while narrow layouts use deliberate sheets/drawers and retain a clear return to the map.
7. **No new provider dependency.** The sprint uses the existing MapLibre and basemap path. Photorealistic 3D, paid imagery and live external feeds are out of scope.

## Task 1 — Establish the operating-picture state and bug contract

**Allocation:** Days 1–2

**Status:** Completed 14 September 2026. See [Task 1 operating-picture state and defect contract](SPRINT-004-TASK-1-OPERATING-PICTURE-STATE.md).

Create the typed interaction foundation before changing the visual shell.

- Define one discriminated entity selection for `site`, `project_subject` and no selection.
- Define URL state for operating mode, selected entity, selected Site assessment or Project Intelligence run, active dossier section and meaningful layer visibility.
- Reload and browser back/forward must restore the same valid investigation state.
- Invalid, deleted, cross-tenant or mutually inconsistent URL state must fail to a safe unselected/unauthorized state; it must never display stale data from the prior entity.
- Map camera coordinates may remain session-local in v1, but entity focus and historical selection may not.
- Extract this state from `app/page.tsx` into a bounded controller with pure parsing/serialization helpers.
- Record and reproduce the current high-priority defects: separate map remounts, Project Intelligence removing geography, divergent Site selections, lost reload/back state, stale asynchronous selection responses, map resize after panel transitions, focus loss and narrow-layout overflow.
- Add behavior-oriented tests for the controller and every confirmed regression. Do not rely only on source-text regex assertions.

**Gate:** A deterministic state test matrix passes for direct URLs, selection switching, reload, back/forward, invalid identifiers, historical selection, stale responses and panel open/close. The confirmed defect register has reproduction steps and an executable test or an explicit browser-only gate for every item.

## Task 2 — Build the modern operating shell

**Allocation:** Days 3–4

**Status:** Completed 14 September 2026. See [Task 2 modern operating shell](SPRINT-004-TASK-2-OPERATING-SHELL.md).

Replace the three competing visual systems with one Infrastructure Operating Picture shell.

- Keep Terrene branding and use “Infrastructure intelligence” as the product context.
- Make the map the full-height base layer below the application chrome.
- Introduce a compact top command bar for global search, scope, data freshness and current selection context.
- Keep one narrow left rail for primary modes; labels appear through expansion or accessible tooltips without permanently consuming map width.
- Use a restrained dark graphite/terrain palette, crisp low-radius surfaces, fine borders and compact typography. Monospace is reserved for identifiers, time, coordinates and versioned artifacts.
- Replace hero panels and card grids with compact status strips, rosters and docked inspectors.
- Separate shell and feature styles into bounded modules rather than adding another global override layer to `globals.css`.
- Preserve WCAG-visible focus, readable contrast, keyboard order, reduced-motion behavior and non-colour state labels.
- Show only real state: actual evidence as-of time, source availability and stored status. Do not add fake “live,” sensor, confidence, latency or system-readiness telemetry.

**Gate:** The empty, loading, populated, partial, unavailable and authorization states share one coherent shell at 1440×900, 1024×768 and 390×844. Visual snapshots and keyboard QA confirm that the map remains the dominant surface and all status text is backed by existing data.

## Task 3 — Implement the unified infrastructure entity map

**Allocation:** Days 5–6

Make one persistent MapLibre scene the spatial index for Terrene's current entity graph.

- Render Sites as geographic areas of investigation using their exact saved boundary versions.
- Render Project Subjects through the geometry of their explicit `site_id` relationship only. Use a distinct project marker/label without duplicating or replacing the Site boundary.
- List Project Subjects without a Site in an “Unlocated intelligence” roster. Selecting one opens its dossier but does not move the map or create an approximate pin.
- Add one searchable entity roster spanning Sites and Project Subjects, with unambiguous type, evidence state and location state.
- Replace the separate portfolio and analysis map lifecycles with one operating-picture map. The boundary editor may remain an isolated task-specific map.
- Add a truthful layer manager for Project Subjects, Site boundaries, environmental evidence and built-world context. Available, mapped-zero, partial, unavailable and unsupported states must remain distinct.
- Selecting from the map, search or roster must drive the same entity controller and inspector.
- Preserve selection and layer state when opening or collapsing the inspector, switching dossier sections or choosing historical evidence.

This task must use existing authenticated Sites, Project Subjects, Project Intelligence and Screening Context read contracts. It must not introduce a new generic entity persistence table or infer Project geometry from names, promoter text or source references.

**Gate:** Tests and browser QA demonstrate a linked Project Subject, a Site without a Project Subject and the real Site-less Beacon Fen subject. Each appears in the correct spatial/unlocated state; no fabricated geometry is rendered; one click produces one selected entity everywhere in the interface.

## Task 4 — Dock evidence and intelligence onto the map

**Allocation:** Days 7–8

Turn the existing Site and Project Intelligence workspaces into entity dossiers within the continuous operating picture.

- A selected Site opens a right-hand dossier with its identity, boundary version, assessment state, Site brief, retained facts, known gaps, map layers, reasoning modules and assessment history.
- A selected Project Subject opens the same dock pattern with reported stage, evidence state, separate planning/construction findings, grid timing, conflicts, unresolved questions, exact source assertions and immutable run history.
- Source assertions and Terrene conclusions must use different, consistently labelled regions.
- Selecting a fact, gap, built-world object or mapped relationship focuses the exact retained geometry when one exists and leaves the map unchanged when it does not.
- Historical Site assessments and Project Intelligence runs update the entire dossier/map evidence envelope together and remain visibly historical.
- The dock can collapse without clearing the entity. Reopening restores its exact section and historical selection.
- Primary evidence is readable without opening a new page; deep provenance remains progressively disclosed.
- Existing Project Intelligence and Site Analysis semantics are migrated, not rewritten. No evidence editor, project editor, automated research or workflow recommendation is added.

**Gate:** An operator can inspect the complete supported-consent/insufficient-construction Beacon Fen result, a mapped Site brief and one historical artifact without the operating picture being replaced. Every displayed conclusion still resolves to its retained evidence references.

## Task 5 — Hardening, bug closure and end-to-end proof

**Allocation:** Days 9–10

Finish the sprint as a reliable interaction system rather than a visual demo.

- Remove the obsolete portfolio/site map path after parity is proved; do not leave two competing primary map controllers.
- Split the monolithic page and global stylesheet only along the new bounded ownership lines. Avoid unrelated refactors.
- Close the certified Task 1 defects and add regression coverage for selection races, panel transitions, layer visibility, map resize, keyboard focus, browser history and narrow layouts.
- Verify that reads remain side-effect free and no historical evidence, assessment or intelligence run is rewritten by UI navigation.
- Measure initial shell and map readiness against the current local build and prevent a material regression. Do not claim real-time performance from synthetic timing.
- Review every label for infrastructure-intelligence identity and remove leftover “Land opportunities,” generic dashboard or fake operational language.

End-to-end proof:

1. Land on the Infrastructure Operating Picture with the map ready.
2. Find and select a map-linked infrastructure Project Subject or Site in one action.
3. Inspect its identity, evidence state, unknowns and source chain while geography remains visible.
4. Toggle a retained evidence or built-world layer and inspect one mapped object/relationship.
5. Select a historical assessment or intelligence run and see the entire evidence context change without rewriting the earlier artifact.
6. Find Beacon Fen in the unlocated roster, see “No verified geography,” and inspect its supported consent and missing construction/grid evidence without a fabricated pin.
7. Reload and use browser back/forward to recover the same valid investigation context.

**Gate:** Frontend regression tests, TypeScript, focused lint, production build, desktop/narrow browser QA, accessibility checks, `git diff --check`, staged-content review and the full end-to-end proof pass. Backend tests are required only if a read contract changes; any such contract change must be split and verified before its UI consumer.

## Sprint acceptance criteria

The sprint is complete when:

- Terrene opens as an infrastructure-intelligence operating picture, not a land-opportunity dashboard.
- One persistent map remains the primary desktop surface across portfolio, Site and map-linked Project Intelligence work.
- At widths of at least 1280 px, at least 60% of the available content width remains geographic canvas with the dossier open.
- Sites and Project Subjects are visually and semantically distinct.
- A Project Subject is plotted only through an authorized Site relationship; unlocated subjects are explicitly represented without a pin.
- Map, roster, search, dossier and URL agree on exactly one selected entity.
- Reload and browser back/forward preserve valid entity, section and historical-artifact context.
- Current and historical evidence move as one immutable envelope.
- Source assertions, Terrene conclusions, conflicts, unknowns and mapped-coverage states remain explicit.
- All confirmed navigation, resize, stale-response, focus and narrow-layout defects are closed or named as acceptance blockers.
- The interface introduces no fake telemetry, live-source claim, confidence score, risk score or commercial recommendation.
- No new paid basemap, 3D engine, external live feed or generic entity persistence abstraction is added.

## Explicit exclusions

- 3D globe, terrain or photorealistic tiles.
- Satellite, drone, traffic, camera or other live feeds.
- AI chat, voice control or autonomous research.
- Alerting, monitoring automation or notifications.
- Risk/confidence scoring and commercial recommendations.
- Project Evidence editing or Project Subject lifecycle management.
- Design Study/Scenario authoring or consequence modelling.
- New scientific reasoning models or environmental datasets.
- Approximate/geocoded project pins without versioned source evidence.
- Customer-validation claims.

## Task and branch operating model

Each task is a separate bounded Codex session and branch from the latest verified `main` or the merged predecessor task:

1. `refactor/operating-picture-state`
2. `feat/operating-picture-shell`
3. `feat/infrastructure-entity-map`
4. `feat/map-docked-intelligence`
5. `fix/operating-picture-hardening`

The primary agent owns architecture and integration. Sub-agents may perform bounded pre-implementation inspection or independent verification when explicitly requested, but they do not implement competing versions of the shell or map controller.

## Known constraints

- Beacon Fen deliberately has no Site, so it must prove the unlocated workflow rather than the mapped-project workflow.
- The current local dataset is Oxford-focused and visually sparse. Synthetic linked fixtures may verify interaction behavior, but they must be labelled and may not be presented as real infrastructure evidence.
- Existing Project Subjects are read-only in the frontend and their Site relationship is fixed at creation. This sprint consumes that contract; it does not add a linking workflow.
- Built-world objects are available only through a prepared immutable Screening Context run and must keep their existing availability/coverage semantics.
- The current frontend test suite contains several source-text regression tests. Task 1 must add behavior tests around the new controller rather than expanding that pattern.
- The existing production build has a large-chunk advisory; Task 5 must report it truthfully unless this bounded refactor removes it.
