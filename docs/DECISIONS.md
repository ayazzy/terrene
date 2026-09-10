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
