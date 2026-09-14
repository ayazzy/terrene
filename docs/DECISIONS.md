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

## 2026-09-14 — The operating picture uses a configured dark vector style

**Decision:** Prefer `NEXT_PUBLIC_BASEMAP_STYLE_URL` as the primary MapLibre style configuration and retain `NEXT_PUBLIC_BASEMAP_URL` only as a legacy raster fallback. Permit OpenFreeMap Dark as the attributed, no-SLA local-development default; never make the public service an implicit production dependency. If production is unconfigured, load a dark blank base, preserve Terrene-owned semantic layers and disclose the missing configuration. Keep GeoLibre as a cartographic and workbench reference rather than an application runtime.

The spatial UI defaults to top-down 2D. It may offer a 55-degree perspective only when valid object-level height evidence exists, and only height-backed buildings may extrude. Layers, legend and roster share one mutually exclusive left-side surface; the entity inspector is docked on desktop and becomes a bottom sheet on narrow screens. Legends and source times are generated from the selected scene rather than maintained as decorative static copy.

**Rationale:** A native vector style gives the spatial application a coherent operator-grade hierarchy without corrupting source colours through a canvas filter. Explicit production configuration avoids depending on a public development service with no SLA. Evidence-gated perspective and generated states keep visual richness subordinate to immutable evidence semantics, while the surface hierarchy preserves the map as the primary analytical canvas.

**References:** [Architecture](ARCHITECTURE.md), [Sprint 005 Task 3](SPRINT-005-TASK-3-DARK-SPATIAL-OPERATING-PICTURE.md), [OpenFreeMap quick start](https://openfreemap.org/quick_start/), [OpenFreeMap service](https://openfreemap.org/).

## 2026-09-14 — Spatial presentation failures do not change evidence semantics

**Decision:** Treat the basemap, immutable map scene and object-height evidence as separate failure boundaries. If a configured remote basemap fails, retain the authorized Terrene scene on an evidence-only dark background and disclose the cartographic failure. If the selected scene fails validation, is unavailable or is superseded by a newer request, fail closed and never retain objects from the prior selection. Preserve partial, gap and historical unsupported height states explicitly; only valid evidence-backed observations may extrude.

**Rationale:** A third-party cartographic dependency must not hide evidence Terrene can still verify, while a missing or stale evidence response must not be made plausible with current objects, zero values or default heights. Keeping these boundaries visible preserves analyst continuity without weakening historical or scientific integrity.

**References:** [Architecture](ARCHITECTURE.md), [Sprint 005 Task 5 spatial overhaul certification](SPRINT-005-TASK-5-SPATIAL-OVERHAUL-CERTIFICATION.md).

## 2026-09-14 — New Site reasoning binds one explicit Evidence Snapshot

**Decision:** Publish `site_reasoning_input_catalogue_v1` as the read-only
organization-scoped inventory of verified Site snapshots and supported modules.
For each snapshot, publish a complete `site_reasoning_run_request_v1` envelope
containing exact Site, snapshot content, boundary, binding and model identities.
Accept a new reasoning run only when the client returns that envelope unchanged;
then create or reuse the existing immutable ModuleRun. Pin snapshot execution to
no acquisition. Keep the legacy assessment POST and its latest registered
dataset selection unchanged as a compatibility path.

**Rationale:** A map-visible source is not automatically a model input, and an
implicit “latest” lookup cannot support reviewable historical reasoning. An
explicit immutable envelope lets an analyst choose known retained evidence,
detects stale or contradictory client state and makes retries deterministic
without rewriting assessment history or allowing newer registry families to
silently alter `wetland_restoration_v0_1`.

**References:** [Snapshot-bound Site reasoning](SITE-REASONING-INPUT-CONTRACT.md), [Architecture](ARCHITECTURE.md), [wetland binding and ModuleRuns](WETLAND-SNAPSHOT-MODULE-RUN.md).

## 2026-09-14 — Develop reusable intelligence capabilities while the market remains open

**Status:** Founder-approved direction; acquisition implementation is planned.

**Decision:** Develop Terrene toward an extensible intelligence platform around
geography, time, evidence, entities and analytical models. Preserve the existing
Earth/Reasoning/Scenario/Application separation. Support future climate,
infrastructure, monitoring and analyst workflows through shared capabilities;
no initial buyer or vertical is selected by this decision. Earlier renewable
screening hypotheses and technical experiments remain historical records, not
customer validation or binding architectural requirements.

Begin with geographic evidence acquisition independent of assessments, using
explicit source capabilities and one existing source in two bounded areas.
Prove this contract before introducing dated Sentinel-2 imagery and then
historical weather in separate iterations. Keep native evidence with common
discovery/provenance metadata rather than flatten every data family into one
measurement schema. Expand types and workflows only as concrete work needs them.

**Rationale:** Architectural work should reduce the cost of supporting a new
customer geography, source, model or workflow. The Oxford prototype and wetland
module should not dictate the eventual product. Public, commercial and customer
data need compatible discovery and lineage, with truthful differences in access,
coverage, time and resolution. Product references such as Gotham and Stellaria
inform ambition without establishing demand, data access or equivalent capability.

**Compatibility:** Retain historical CRC identities and all existing assessments,
snapshots, runs, imports and map contracts. New regional acquisitions must not
enter the legacy source-only `latest()` selection and replace Oxford inputs.
Future time requests must fail explicitly when the selected source cannot serve
them. Source collection must not silently execute a model or fabricate a Site.

**References:** [Architecture](ARCHITECTURE.md), [first acquisition iteration](GEOGRAPHIC-EVIDENCE-ACQUISITION-PLAN.md), [Customer Discovery](CUSTOMER-DISCOVERY.md).

## 2026-09-14 — UK-wide coverage is a near-term requirement

**Decision:** Following the founder's clarification, prioritize delivery across
England, Scotland, Wales and Northern Ireland, including their islands. The
initial two-area England proof remains bounded, but its shared geometry, identity
and capability contracts must accommodate the whole UK from the outset. Follow
it promptly with four-nation source expansion and application access, ahead of
optional new data-family work. No calendar deadline has been agreed.

**Rationale:** Natural England coverage cannot establish UK coverage. Provider
jurisdictions, source types, temporal support and coordinate systems differ.
Represent these through explicit adapters and coverage metadata rather than
reusing an England bounding box or silently renaming all designations as SSSI.
Maintain a source-family coverage matrix; a missing national source remains a gap.

**Completion meaning:** A UK-capable request schema and four demonstration sites
are insufficient to claim complete UK data. Each delivered evidence family needs
verified publisher coverage, acquisition limits, representative tests in all four
nations and truthful application availability. Broader terrain, imagery, climate
and infrastructure coverage must be tracked separately from the first designation
family. Preserve all existing Oxford evidence and historical processing methods.

**References:** [Architecture](ARCHITECTURE.md), [UK expansion plan](GEOGRAPHIC-EVIDENCE-ACQUISITION-PLAN.md).


## 2026-09-14 — Isolate geographic acquisition history and pin operational coverage

**Status:** Implemented within the approved first acquisition iteration.

**Decision:** Retain geographic requests/attempts in separate organization-scoped
tables and immutable objects. Do not publish them into the legacy latest-by-key
dataset catalogue. Use a bounded synchronous operator service with idempotency,
expiring claims and token-fenced publication; leave HTTP access and scheduling
for later iterations. Preserve original provider candidates separately from
normalized full-feature selections and record publisher/capture-time distinctions.

**Coverage:** Keep general WGS84 area validation independent from source coverage.
The first England SSSI adapter pins an immutable ONS December 2024 full-resolution,
coastline-clipped coverage profile, acquired once from its registered official
endpoint. A profile hash is explicit in the request. Require whole-area support
without clipping or filling exclusions. This is an intentionally conservative
operational footprint, not complete publisher or legal coverage. Live Broads
verification demonstrated tidal-water exclusions; resolve those in a versioned
coverage contract before offering broad national access. Do not generalize an
England profile to Scotland, Wales or Northern Ireland.

**Evidence:** Live Oxford and western Norfolk selections match independent
provider polygon queries. SQLite and PostgreSQL acquisition/legacy checks pass;
retained Oxford results are unchanged. No customer/workflow validation is implied.
See [implementation and verification](GEOGRAPHIC-EVIDENCE-ACQUISITION.md).


## 2026-09-14 — Version England coverage independently of historical captures

**Status:** Implemented as the next bounded coverage correction.

**Decision:** Preserve `sssi_arcgis_v1` and its pinned ONS BFC high-water coverage.
Introduce explicit `sssi_arcgis_v2` / `england_current_vector_v2` with an ONS
December 2024 BFE extent-of-realm profile. Require matching adapter/profile
versions and a new idempotency key for changed requests. Keep CLI defaults at v1
for compatibility. Use the official full-resolution geometry without filling
holes, clipping or buffering, and retain setup provenance and consistency checks.

**Reason:** High-water clipping excluded tidal water inside the first Broads
request. The new footprint supports that exact polygon; two SSSI features match
an independent live provider query. This is an operational coverage correction,
not an expanded claim about complete marine coverage or legal designation extent.
The old rejection and prior successes remain unchanged. Country and jurisdiction
support must stay specific to each publisher; other national adapters remain
separate next iterations.

**References:** [Coverage v2 implementation and verification](GEOGRAPHIC-COVERAGE-V2.md),
[ONS boundary definitions](https://www.ons.gov.uk/methodology/geography/geographicalproducts/digitalboundaries).

## 2026-09-14 — Keep Scottish designation and component identities distinct

**Decision:** Add NatureScot SSSI as a separate registered publisher/adapter with
an explicitly pinned Scottish ONS BFE coverage profile. Preserve native
`OBJECTID` component identities and `PA_CODE` designation identities separately;
multiple components may represent one designation. Retain interest class,
current status and nullable provider update values without turning them into
observations, ecological condition or a publication date. Verify publisher item
identity and terms before and after each capture.

**Coverage:** The Scottish profile requests and checks 10 decimal places in
provider WGS84 coordinates. This bounds output serialization while retaining
vertices; no geometry generalization, buffering, clipping or repair is requested
for coverage. Keep that precision policy in the new profile identity and retain
the exact response hashes. England v1/v2 and their defaults remain unchanged.
Whole-area coverage is operational and does not establish complete marine or
legal designation extent. Wales, Northern Ireland and cross-border composition
remain separate work.

**References:** [NatureScot implementation and verification](NATURESCOT-SSSI-ACQUISITION.md).

## 2026-09-14 — Prioritize LIDAR and data-family breadth before more designation publishers

**Decision:** The founder explicitly deferred Wales and Northern Ireland
designation work and asked to continue acquiring data such as LIDAR. Preserve
the broader UK capability requirement while advancing one data family at a time.
This supersedes the earlier requirement to finish those designation adapters
before starting additional data families; it does not claim their coverage exists.

**First outcome:** Add independent EA 1 m DTM raster acquisition on the existing
geographic request/attempt foundation. Retain original binary source responses
and explicit native-grid availability rather than running an assessment to
obtain terrain data. Keep historical composite dates, acquisition time and unknown
local survey dates separate. Missing cells remain missing, including an entirely
nodata area; a successfully retained response does not imply usable terrain.

**Compatibility:** Binary artifact support is additive. Preserve existing JSON
manifest/object identities, source profiles, legacy terrain/height processing,
snapshots and model inputs. Scotland LIDAR is not established by Scottish SSSI
coverage. Surface models, imagery, weather and application access remain separate
subsequent iterations. No market-validation or purchasing decision is implied.

**Reference:** [Independent LIDAR acquisition](EA-LIDAR-GEOGRAPHIC-ACQUISITION.md).

## 2026-09-15 — Separate surface elevation from terrain and qualify raster pairing

**Decision:** Add EA last-return DSM as an independent registered raster source,
sharing bounded transport/grid checks with DTM while retaining separate source,
coverage and processing identities. Do not label DSM elevation as ground height,
building height or a contemporary observation.

**Pairing:** Require explicit retained DTM and DSM capture IDs, matching area and
coverage-profile identity, correct source roles and compatible verified native
grids/units/datums. Report intersecting valid cells and missing pairs. Do not
infer joint availability from the minimum of marginal coverage fractions, or
infer matching survey dates from matching grids or catalogue composite labels.
Expose pairing as a deterministic read-only compatibility contract with exact
input references; it creates no model result or new persisted evidence record.

**Compatibility:** Existing DTM/vector requests, source descriptors, profile and
artifact hashes, legacy terrain/height methods, assessments, snapshots and model
inputs remain unchanged. A future surface-minus-terrain interpretation requires
its own versioned binding and explicit assumptions. No commercial-workflow
validation or broader UK publisher coverage is implied.

**Reference:** [DSM acquisition and pairing](EA-DSM-GEOGRAPHIC-ACQUISITION.md).
