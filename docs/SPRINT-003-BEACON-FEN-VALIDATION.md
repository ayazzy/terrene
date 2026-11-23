# Sprint 003 — Beacon Fen real-project evidence test

## Status

Closed early on 13 September 2026 after Tasks 1 and 2 (the technical proof). One bounded official consent assertion is reproducibly committed through the existing immutable Project Evidence and Project Intelligence contracts. The remaining planned tasks were cancelled so the next sprint could address the infrastructure-intelligence interface.

## Closure decision

The technical experiment achieved its bounded proof: Terrene can retain an exact real-project source assertion, bind it immutably and produce a truthful partial intelligence result without inventing construction or grid facts.

The sprint stopped after the technical proof; the planned review and evaluation tasks were not run.

The next priority is [Sprint 004 — Infrastructure Operating Picture](SPRINT-004-INFRASTRUCTURE-OPERATING-PICTURE.md). It will make the spatial operating picture the continuous primary interaction surface while preserving the source, evidence, reasoning and history semantics proved here.

## Sprint goal

Test whether Terrene's inspectable Project Evidence and Project Intelligence loop materially improves one real early-diligence review:

> What is actually established about this project's consent, construction and grid timing, what is only reported by an interested party, and what remains unresolved?


## Selected Project Subject

- **Name:** Beacon Fen Energy Park
- **Planning Inspectorate reference:** EN010151
- **Project type:** `energy_infrastructure`
- **Location:** east of Sleaford, Lincolnshire, connecting toward Bicker Fen substation
- **Promoter:** Beacon Fen Energy Park Limited / Low Carbon
- **Terrene Site relationship at intake:** none; a boundary is not required to investigate the Project Subject
- **Evidence as-of for Task 1:** 13 September 2026

Beacon Fen is a useful validation subject because it is recent, consequential and unusually inspectable. Development consent was granted on 21 August 2026. The public record includes government, Planning Inspectorate, statutory-notice and promoter material, while its milestone language varies between an anticipated 2026 construction start, an expected 2027 construction start, operation in 2029 and grid capability by 2030. Terrene must preserve those distinctions rather than convert them into one invented schedule.

## Task 1 source register

All sources below are public. URLs are references, not proof that Terrene fetched or independently verified their contents. Task 2 must retain bounded excerpts, source versions and hashes explicitly before committing evidence.

| ID | Source and version rule | Publisher / role | Candidate assertion | Admission decision |
|---|---|---|---|---|
| BF-S1 | [Development-consent decision, published 21 August 2026](https://www.gov.uk/government/publications/beacon-fen-energy-park-project-decision-on-application-for-development-consent-under-the-planning-act-2008) | DESNZ; official decision record | Development consent was granted on 21 August 2026. | Admit as `planning_status=approved`, effective 2026-08-21. |
| BF-S2 | [Planning Inspectorate decision announcement, published 21 August 2026](https://www.gov.uk/government/news/beacon-fen-energy-park-development-consent-decision-announced) | Planning Inspectorate; official process record | The application was submitted on 8 April 2025, accepted on 1 May 2025 and later granted consent; the described project includes 400 MW solar and up to 600 MVA storage. | Use as corroborating source context. Admit a second approved-status claim only if the interview dossier benefits from demonstrating multiple compatible sources. Capacity is outside the v1 claim vocabulary. |
| BF-S3 | [Beacon Fen project page, captured 13 September 2026](https://www.beaconfenenergypark.co.uk/) | Project promoter; interested-party report | The promoter reports a National Grid connection agreement, expected construction in 2027 and operation in 2029. The same page also retains historical wording about possible construction in 2026. | Retain as source assertions. Do not translate construction or operation targets into a current construction status. Do not treat the page as independent verification. |
| BF-S4 | [London Gazette notice 4889106, published 21 May 2025](https://www.thegazette.co.uk/notice/4889106) | Statutory notice | The accepted application described a project capable of connecting to the national grid by 2030. | Retain, but do not admit to v1: a year-only deadline cannot be truthfully converted to an exact `target_grid_connection_date`. |
| BF-S5 | [Summer 2023 project newsletter](https://www.beaconfenenergypark.co.uk/wp-content/uploads/2023/08/Beacon-Fen-Newsletter.pdf) | Project promoter; historical publication | The published timeline anticipated construction beginning in 2026, subject to consent. | Retain as historical source context. It is not a construction-status observation and is not an explicit correction ancestor. |

## Evidence-admission rules

Task 2 must apply these rules:

1. Official consent establishes `planning_status=approved`; it does not establish that construction started.
2. A planned construction-start year is not `construction_status=preparation`, `not_started` or `under_construction`.
3. An operational target is not silently relabelled as a grid-connection target.
4. “By 2030” retains year precision and is not normalized to 1 January or 31 December 2030.
5. An updated webpage does not explicitly supersede an older claim unless the source states the correction relationship.
6. Promoter assertions remain attributed promoter assertions even when repeated by secondary reporting.
7. Project capacity, boundary, technology and environmental claims remain out of the v1 intelligence bundle unless a later task establishes a typed contract for them.
8. Absence of a public construction-status statement remains insufficient evidence, not `not_started`.

## Current contract-fit finding

The real source record validates one part of `project_evidence_v1`: the official consent decision can be represented exactly and should produce a supported `consented` stage.

It also exposes a deliberate limitation. Public project schedules frequently use year-level precision and distinguish construction start, commercial operation and grid connection. Version 1 represents only exact grid-connection dates and status assertions. Task 2 must therefore produce a truthful partial result—supported consent with insufficient construction/grid evidence—rather than extending the schema during ingestion.

This is a validation finding, not yet sufficient evidence for a version 2 contract.

## Sprint tasks

### Task 1 — Select the project and certify evidence admission

**Allocation:** Day 1

Produce the selected Project Subject, source register, decision hypothesis, admission rules and explicit contract-fit findings.

**Gate:** Every candidate claim is either mapped exactly to the current contract or explicitly excluded with a semantic reason. No date or status is inferred.

### Task 2 — Commit the first real evidence bundle and baseline run

**Allocation:** Days 2–3

Create Beacon Fen as a Project Subject without fabricating a Site. Commit only source passages that fit `project_evidence_v1`, bind the exact bundles and create an immutable Project Intelligence run. Record excluded source assertions alongside the experiment, not inside an incompatible predicate.

**Gate:** The run reports supported consent, preserves exact official source references, shows insufficient construction/grid evidence, is reproducible, and passes integrity/readback checks.

**Completed 13 September 2026:** `docs/sprints/003-beacon-fen-evidence.json` retains the curated source passage, claim locator, capture identity and five deliberately excluded assertions. `scripts/seed_beacon_fen_validation.py` creates or reuses the Site-less Project Subject, publishes the exact bundle, binds it, runs `project_intelligence_v1`, integrity-checks both records on read and refuses any semantic result other than:

- reported stage `consented` / `supported`;
- planning status `approved` / `supported`;
- construction status `insufficient_evidence`;
- grid-connection target `insufficient_evidence`; and
- unresolved questions for construction status and grid target only.

The script performs no source acquisition. The source `content_hash` identifies the exact retained human-submitted excerpt captured at 2026-09-13T22:10:23Z; it is not represented as a hash of the full mutable GOV.UK page.

The official page reports its publication as a calendar date without a clock time. Because `SourceRecord.published_at` requires a timezone-aware datetime, the packet stores that field as null rather than fabricate midnight. The exact 2026-08-21 consent event date remains attached to the planning claim, and the omitted publication precision is recorded in `source_metadata_notes`.

Local replay command:

```bash
CRC_ENV=development .venv/bin/python scripts/seed_beacon_fen_validation.py --org local-development
```

Hosted execution must use the deployment's configured database, authentication and immutable object storage rather than this local development command.

## Sprint acceptance criteria

**Closure result:** the technical criteria below were met by Task 2.

- One real Project Subject and immutable run are inspectable end to end.
- Every admitted conclusion resolves to retained official source evidence.
- Year-only and semantically different milestones are not coerced into exact grid dates.
- Official, promoter and historical assertions remain visibly distinct.
- No confidence score, recommendation, automated research, alerting or Scenario capability is added.

## Known dependencies

- Public pages can change. Task 2 must record capture time, bounded retained excerpts and deterministic hashes.
- The current Project Intelligence UI is read-only; Task 2 may use the existing authenticated API or a bounded local ingestion script, but it must not introduce an evidence editor.

## Task 2 verification record

- Curated packet hash, locator, allowed claim and excluded-assertion semantics are executable tests.
- Identical ingestion reuses one Project Subject, bundle, binding and run.
- Public API readback is tenant scoped and GET requests create no records.
- An isolated command-line replay produced supported consent plus exactly two missing-evidence questions.
- Browser QA in the local workspace verified Overview, the exact source assertion and both unresolved questions.
- The combined Beacon Fen, Project Evidence and Project Intelligence suite passed **32 tests on SQLite** and **32 tests on disposable PostgreSQL/PostGIS**.
- The default fresh-clone-compatible suite passed **166 tests with 63 retained-data tests explicitly skipped**.
