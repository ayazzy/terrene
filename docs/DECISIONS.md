# Terrene decision log

This is a lightweight append-only log of durable product and architecture decisions. Add new records; do not rewrite old records to fit later preferences. Dates are included only when the repository establishes them confidently.

## 2026-09-08 — Land evidence exists independently of reasoning

**Decision:** Create a reusable Land Evidence projection whose facts, gaps, source references and lineage are independently identifiable from the wetland module.

**Rationale:** Evidence about land should be reusable across models and applications. A module's desired features or scores must not determine what is admitted as fact.

**References:** [Land Intelligence Foundation](LAND-INTELLIGENCE-FOUNDATION.md), [Evidence Snapshot persistence](LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md).

## 2026-09-08 — Evidence Snapshots and ModuleRuns are immutable and versioned

**Decision:** Persist evidence under semantic/byte identities, use explicit versioned module bindings, and record deterministic immutable ModuleRuns rather than recalculating or overwriting historical results.

**Rationale:** Boundaries, source releases, processing methods, evidence selections and models change. Reproducibility requires each change to create a new traceable identity while older evidence and results remain inspectable.

**References:** [Evidence Snapshot persistence](LAND-EVIDENCE-SNAPSHOT-PERSISTENCE.md), [wetland binding and ModuleRuns](WETLAND-SNAPSHOT-MODULE-RUN.md).

## 2026-09-08 — Facts, interpretations and decisions remain separate

**Decision:** Treat evidence-backed observations as reusable facts, model outputs as interpretations, and team choices as decisions. Do not use one category as a substitute for another.

**Rationale:** Combining these layers hides provenance, makes model changes look like changes to reality and can let human status overwrite computed evidence.

**References:** [Land Intelligence Foundation](LAND-INTELLIGENCE-FOUNDATION.md), [Stage 2 site analysis](UI-STAGE-2.md), [Architecture](ARCHITECTURE.md).

## 2026-09-09 — Mapped zero has source-bounded meaning

**Decision:** Represent a known mapped zero only after complete declared source support was successfully examined. Keep it distinct from partial coverage, outside coverage, acquisition/processing failure and ecological absence.

**Rationale:** An inventory or generalized map can establish that it maps no qualifying feature within its scope; it cannot establish that the real-world phenomenon is absent.

**References:** [Priority Habitats evidence](PRIORITY-HABITATS-EVIDENCE.md).

## 2026-09-10 — Terrene Earth represents objects and relationships

**Decision:** Permit Earth to retain typed real-world objects and explicit spatial relationships, not only scalar parcel observations, while avoiding a premature universal ontology.

**Rationale:** Buildings, functional sites, railway lines and stations have identities and topology that a single overlap score would erase. Reusable scalar observations can be derived without discarding object lineage.

**References:** [OpenMap Local built world](OPENMAP-LOCAL-BUILT-WORLD.md).

## 2026-09-10 — CRC transitions to Terrene without rewriting history

**Decision:** Use Terrene as the company, product and project name for new durable documentation. Retain `CRC`/`crc` identifiers where they encode model identity, persistence, environment/configuration contracts, hashes, signatures, database names, source provenance or historical reports.

**Rationale:** A global rename would create migration and reproducibility risk without improving the represented evidence or models. Historical reports should continue to describe the versions that existed when they were written.

**References:** [North Star](TERRENE-NORTH-STAR.md), [Architecture](ARCHITECTURE.md), repository history.

## 2026-09-10 — Wetland/restoration is a module, not company identity

**Decision:** Treat wetland restoration as an early Terrene Reasoning primitive rather than the definition of Terrene.

**Rationale:** The durable asset is a computational model of land and interventions. Multiple reasoning modules and validated applications should share the same evidence-backed Earth foundation.

**References:** [North Star](TERRENE-NORTH-STAR.md), [wetland binding and ModuleRuns](WETLAND-SNAPSHOT-MODULE-RUN.md).

## 2026-09-10 — Public data is an input, not the product

**Decision:** Build value through normalization, representation, reasoning, simulation and operational learning rather than treating access to public datasets or a map viewer as the product.

**Rationale:** Durable commercial value must improve expensive decisions and workflows. Source data remains essential, attributable evidence but is not sufficient differentiation by itself.

**References:** [North Star](TERRENE-NORTH-STAR.md), [Customer Discovery](CUSTOMER-DISCOVERY.md).

## 2026-09-10 — Terrene Applications operationalize land decisions

**Decision:** Terrene Applications should operationalize land decisions rather than merely visualize Terrene Earth.

**Rationale:** Terrene's evidence and reasoning become commercially more useful when they participate in a workflow around durable land opportunities: triage, unresolved evidence, collaboration, decisions, next actions and progression. Competitive analysis of LandTech supports the existence of this workflow pattern, but customer discovery must determine Terrene's exact implementation.

Terrene Earth continues to represent reality and evidence; Terrene Reasoning interprets it; Terrene Scenario tests interventions; and Terrene Applications operationalize useful workflows. Workflow state must not turn Terrene Earth into a CRM or become mixed with core environmental facts.

**References:** [Customer Discovery](CUSTOMER-DISCOVERY.md), [North Star](TERRENE-NORTH-STAR.md).

## 2026-09-10 — Screening context publication requires an intentional action

**Decision:** Create or reuse assessment Evidence Snapshots and screening ModuleRuns through an explicit prepare action. Ordinary discovery, stored-run reads and export reads do not publish immutable records. Preserve an existing assessment origin rather than silently projecting it under a newer registry.

**Rationale:** Opening a site or historical assessment must not create new scientific history. Reviewers need a reproducible context for the selected saved evidence, while unsupported or ambiguous historical origins require an explicit limitation.

**References:** [Screening Context v1](SCREENING-CONTEXT-V1.md), [Architecture](ARCHITECTURE.md).

## 2026-09-13 — Project source assertions are Earth evidence, not Terrene findings

**Decision:** Store attributed infrastructure-project source assertions as immutable `project_evidence_v1` evidence in Terrene Earth. Terrene-derived findings such as stage, progress, delay, risk, confidence, commercial opportunity or recommendation belong in a separately versioned Terrene Reasoning module and must not be editable fields on the evidence record.

**Rationale:** A citation establishes who asserted something, not that the assertion is true. Source claims can conflict, target dates can pass without becoming completed events, and corrections must preserve what was originally recorded. Keeping those assertions separate from derived findings makes future reasoning inspectable and reproducible.

Infrastructure project intelligence remains an application hypothesis. Implementing its reusable evidence input does not constitute customer validation or a decision that this is Terrene's chosen market.

**References:** [Project Evidence v1](PROJECT-EVIDENCE-V1.md), [Architecture](ARCHITECTURE.md), [Customer Discovery](CUSTOMER-DISCOVERY.md), [North Star](TERRENE-NORTH-STAR.md).

## 2026-09-13 — Proposed designs are versioned state, not Earth evidence

**Decision:** Represent proposed infrastructure through an organisation-scoped
Project, named Alternative and immutable Revision hierarchy. Pin each Project
and every Revision to one explicit committed Evidence Snapshot and historical
Site boundary. Use explicit parent-head matching for stale-write protection and
scoped idempotency keys for retry safety.

**Rationale:** A proposal describes a possible change to reality, not an observed
fact or model result. Immutable proposal lineage and a fixed evidence baseline
are prerequisites for later reproducible Scenario calculations; selecting the
latest evidence or overwriting an alternative would make historical comparisons
unreliable.

**References:** [Architecture](ARCHITECTURE.md), [Sprint 001](sprints/001-design-proposals.md).

## 2026-09-13 — Project Subjects and Design Studies are separate contracts

**Decision:** Use `project_subjects` and `/api/project-subjects` for monitored real-world projects that own Project Evidence. Preserve `infrastructure_projects` and `/api/projects` as the compatibility contract for Site- and Evidence-Snapshot-pinned Design Studies containing Alternatives and Revisions.

**Rationale:** A real-world project may be investigated before Terrene knows its Site. A Design Study is a proposed-state container whose meaning depends on one exact parcel baseline. Combining them would either fabricate spatial identity for source intelligence or weaken Design Revision reproducibility.

**References:** [Project Intelligence v1](PROJECT-INTELLIGENCE-V1.md), [Architecture](ARCHITECTURE.md).

## 2026-09-13 — Project reasoning binds explicit evidence and preserves conflict

**Decision:** `project_intelligence_v1` consumes only `project_evidence_binding_v1`, created from explicit bundle IDs. It keeps active conflicts visible, applies only explicit corrections, evaluates targets against the binding evidence-as-of time, and persists complete results in dedicated immutable Project Intelligence runs.

**Rationale:** “Latest” selection and publication recency would make results non-reproducible and could turn an attributed assertion into an unsupported conclusion. Dedicated runs support non-spatial Project Subjects without weakening the Site-bound ModuleRun contract.

**References:** [Project Intelligence v1](PROJECT-INTELLIGENCE-V1.md), [Architecture](ARCHITECTURE.md).

## 2026-09-14 — Operating-picture navigation has one URL-addressable state contract

**Decision:** Represent the active Terrene investigation through one typed
navigation contract containing operating mode, an exact Site or Project Subject
selection, a compatible historical assessment or intelligence run, dossier
section/visibility and meaningful layer visibility. Use browser history as the
restorable presentation-state boundary; keep camera position session-local.

Validate identifiers syntactically and then against authorized API results.
Invalid, unavailable or mutually inconsistent selection/artifact combinations
fail closed and may not expose data retained from a prior entity. Navigation
reads and history transitions must not create or rewrite domain records.

**Rationale:** Independent in-memory map, workspace, entity and history states
can disagree and cannot survive reload or browser Back/Forward. One canonical
contract makes later shell, map and dossier convergence testable while
preserving the distinction between ephemeral interaction state and immutable
Terrene evidence/reasoning history.

**References:** [Sprint 004](SPRINT-004-INFRASTRUCTURE-OPERATING-PICTURE.md), [Sprint 004 Task 1](SPRINT-004-TASK-1-OPERATING-PICTURE-STATE.md).

## 2026-09-14 — Project geography requires an explicit Site relationship

**Decision:** Use one persistent infrastructure-entity map for Site and Project
Subject selection. Render a Project Subject spatially only when its authorized
record has an explicit `site_id` relationship to an authorized Site with saved
geometry. Derive the marker's display anchor from that Site envelope while
retaining the Site boundary as the actual geographic object. Keep every other
Project Subject in an explicitly unlocated roster and leave the camera unchanged
when it is selected.

**Rationale:** Names, promoter text and source references are not defensible
spatial evidence. A shared map improves investigation continuity only if it does
not turn missing geography into an approximate or fabricated location.

**References:** [Sprint 004](SPRINT-004-INFRASTRUCTURE-OPERATING-PICTURE.md), [Sprint 004 Task 3](SPRINT-004-TASK-3-ENTITY-MAP.md), [Architecture](ARCHITECTURE.md).

## 2026-09-14 — Sites and Project Subjects share one dossier shell

**Decision:** Present Site and Project Subject investigation through one docked
entity-dossier shell beside the persistent infrastructure map. The shell owns
entity identity, defensible location state, exact assessment/run envelope,
evidence time, historical state, map-layer access and collapse behavior. Keep
the existing Site and Project evidence/reasoning components inside it rather
than normalizing their distinct domain contracts.

**Rationale:** A common investigation grammar reduces context switching and
keeps the map operational, while shared presentation must not imply that Site
observations and attributed project assertions are the same evidence type.
Collapse is presentation state; historical artifact, section and entity
selection remain canonical and restorable. Source assertions and Terrene
conclusions remain visibly and navigably separate.

**References:** [Sprint 004](SPRINT-004-INFRASTRUCTURE-OPERATING-PICTURE.md), [Sprint 004 Task 4](SPRINT-004-TASK-4-ENTITY-DOSSIERS.md), [Architecture](ARCHITECTURE.md).

## 2026-09-14 — Building height is versioned object evidence, not an object attribute

**Decision:** Add `BuildingHeightObservation` in `land_evidence_registry_v4` and link each observation or explicit gap to one immutable `MappedBuildingObject`. Derive the estimate only from exact co-registered Environment Agency 1 m DSM/DTM responses using the pinned `crc_ea_lidar_building_height_v1` method. Keep the mapped building record unchanged and keep height evidence outside the historical wetland input.

**Rationale:** A building identity comes from the declared OpenMap Local release, while DSM-derived surface height has separate source dates, artifacts, coverage, processing and uncertainty. Placing height directly on the object would conceal that independent lineage and encourage a later source or method to rewrite historical object state. A dedicated observation preserves multiple future measurements without introducing a general graph database or treating a historical composite as a current survey.

**References:** [EA LIDAR building heights](EA-LIDAR-BUILDING-HEIGHTS.md), [OpenMap Local built world](OPENMAP-LOCAL-BUILT-WORLD.md), [Architecture](ARCHITECTURE.md).

## 2026-09-14 — The primary map is a projection of one immutable Evidence Snapshot

**Decision:** Define `infrastructure_map_scene_v1` as an authenticated, organization-scoped, read-only presentation projection of one exact committed Land Evidence Snapshot. Validate the snapshot manifest and identity envelope before returning safe WGS84 features, semantic layer and capability states, source metadata, typed parcel relationships and object-level height evidence. Render that contract through native MapLibre GeoJSON sources, rendered-feature queries and feature state. Preserve `screening_context_map_features_v1` unchanged and keep temporary SVG geometry only in the isolated boundary editor.

**Rationale:** The operating picture needs object-centric interaction without making the map another evidence store or coupling spatial presentation to one reasoning module. A snapshot-native projection keeps selection, historical state and height eligibility tied to immutable evidence, while native MapLibre layers provide reliable layer ordering, hit testing and future perspective rendering. Keeping the historical response avoids silently changing existing Screening Context consumers.

**References:** [Architecture](ARCHITECTURE.md), [Sprint 005 Task 2](SPRINT-005-TASK-2-NATIVE-INFRASTRUCTURE-MAP.md), [EA LIDAR building heights](EA-LIDAR-BUILDING-HEIGHTS.md).
