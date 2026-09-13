# Project Evidence v1

## Outcome

Project Evidence v1 is an authenticated Terrene Earth input contract for human-submitted, source-backed assertions about infrastructure projects. It introduces only a stable organization-owned Project identity and immutable evidence bundle publication. A Project may optionally link to an existing Site; it is not a parcel and requires no fabricated boundary.

The API exposes:

- `POST /api/projects`
- `GET /api/projects/{project_id}`
- `POST /api/projects/{project_id}/evidence-bundles`
- `GET /api/projects/{project_id}/evidence-bundles`
- `GET /api/projects/{project_id}/evidence-bundles/{bundle_id}`

There is no Project update/delete API, project-management workflow, source URL fetch, crawler, OCR/LLM ingestion or reasoning action.

## Source

Every v1 source is explicitly `human_submitted_structured`. A source record retains:

- stable `id` plus `source_version`;
- publisher, title and URL/reference;
- optional `published_at` and separate required `recorded_at`;
- retained text excerpt;
- a lowercase SHA-256 `content_hash` supplied for the exact source version; and
- the entry method.

The source hash is retained attribution/content identity supplied with the record. Terrene validates its shape and immutability but does not fetch the reference or independently prove the external material merely by storing it. The canonical bundle hash also covers the retained excerpt and every source field.

A logical source ID may appear in a later bundle with a new source version. Reusing the same `(Project, source ID, source version)` with different content is rejected.

## Evidence semantics

The only predicates in v1 are:

- `planning_status`: `unknown`, `not_submitted`, `submitted`, `under_review`, `approved`, `refused`, `withdrawn`;
- `construction_status`: `unknown`, `not_started`, `preparation`, `under_construction`, `paused`, `completed`, `cancelled`; and
- `target_grid_connection_date`: a discriminated `known` date or an `unknown` value with a reason.

Status `unknown` values require an explicit reason. Each claim references its Project and exactly one source record in the same bundle. Its locator contains zero-based, end-exclusive character offsets and the exact passage; the submitted passage must equal that slice of the retained excerpt.

`time.kind` is one of `reported_occurrence`, `future_target` or `unknown`. Occurrences and targets require an effective/event date; unknown time prohibits one. A known grid-connection target must use `future_target`, and its event date must equal its value. No current-clock rule changes that meaning: a target whose date has passed remains a source's target assertion.

`supersedes_claim_id` is an explicit correction relationship to a claim with the same predicate in the same bundle or an earlier bundle for the same organization and Project. The original claim remains committed and readable. Broken, self-referential, cyclic, cross-predicate, cross-Project and cross-tenant relationships are rejected.

Two claims with the same predicate may disagree. Bundles contain no selected value, verified flag, score or inferred conclusion. A source citation establishes attribution, not truth.

## Exact committed contract

The next Terrene Reasoning binding should consume the committed `ProjectEvidenceBundle` below together with its bundle `id` and `content_hash`, never a mutable Project view or an implicit latest bundle.

```text
ProjectEvidenceBundle {
  schema_version: "project_evidence_v1"
  project: {
    id: string
    org: string
    name: string
    project_type:
      "energy_infrastructure" | "transport_infrastructure" |
      "water_infrastructure" | "digital_infrastructure" |
      "social_infrastructure" | "other_infrastructure"
    site_id: string | null
    content_hash: sha256
  }
  land_evidence_snapshot: null | {
    snapshot_id: string
    site_id: string
    boundary_version: integer >= 1
    content_hash: sha256
  }
  sources: SourceRecord[1..100]
  claims: ProjectClaim[1..500]
}

SourceRecord {
  id: string
  source_version: string
  publisher: string
  title: string
  reference: string
  published_at: timezone-aware datetime | null
  recorded_at: timezone-aware datetime
  retained_excerpt: string
  content_hash: lowercase sha256
  entry_method: "human_submitted_structured"
}

ProjectClaim = PlanningStatusClaim |
               ConstructionStatusClaim |
               TargetGridConnectionDateClaim

Claim common fields {
  id: string
  project_id: string
  phase: null | "concept" | "planning" | "pre_construction" |
                "construction" | "commissioning" | "operational" |
                "decommissioning"
  source_record_id: string
  locator: { start: integer, end: integer, exact_passage: string }
  time: {
    kind: "reported_occurrence" | "future_target" | "unknown"
    effective_or_event_date: date | null
  }
  supersedes_claim_id: string | null
}
```

The executable Pydantic contract, including the three discriminated claim variants and all cross-field validation, is in `backend/project_evidence.py`. The isolated synthetic request fixture is `tests/fixtures/project_evidence_v1/synthetic_packet.json`.

## Persistence and identity

Project metadata is immutable in v1 and protected by a content hash. Bundle sources and claims are sorted by stable ID before canonical serialization. The bundle content hash covers the Project snapshot, optional exact land snapshot link, all source versions/excerpts and all claims/locators/time/correction links. The deterministic bundle identity additionally includes organization and Project ID.

The canonical manifest is written through immutable compare-and-set object storage, read back and byte-verified, then one database transaction commits the bundle row, exact membership catalogue and stable source-version/claim identity catalogues. A uniqueness race reloads and fully verifies the winner. Identical retries therefore return the same first committed identity and timestamp. Changed evidence produces a different bundle, while the earlier manifest remains unchanged.

Read paths organization- and Project-scope every lookup, load the stored manifest, verify its byte hash, revalidate the typed graph, recompute deterministic identity and compare all relational catalogues. Reads contain no persistence action.

## Real-data verification

The example Project packet and all project/source claims are explicitly synthetic and isolated under tests. No invented infrastructure facts are seeded into the portfolio. Optional land-link verification uses one already-retained land Evidence Snapshot fixture only to prove exact snapshot/Site/content-hash binding; it does not turn that land evidence into a project claim.

No live URL, external service, hosted R2 bucket or production customer data is used by Project Evidence v1 verification.

## Boundary with Terrene Reasoning

Project Evidence v1 does not calculate project stage, progress, delay/risk, confidence, commercial opportunity, recommendation or pursue/monitor/dismiss decisions. Existing Site team-review status is neither copied into the bundle nor interpreted as Project stage.

Sprint 002 resolved the next binding boundary with `project_evidence_binding_v1`: a run consumes an explicit non-empty set of bundle IDs, canonicalizes their order, pins their complete content/source/claim membership, requires complete acyclic correction ancestry and leaves contradictory active claims visible. It never selects a newest bundle or lets publication recency win. See [Project Intelligence v1](PROJECT-INTELLIGENCE-V1.md).

Infrastructure project intelligence remains a customer hypothesis, not a validated market decision.
