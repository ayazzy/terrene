# Project Intelligence v1

## Outcome

Sprint 002 establishes one complete inspectable loop:

```text
explicit project source assertions
  → project_evidence_binding_v1
  → deterministic project_intelligence_v1
  → immutable project_intelligence_runs
  → read-only investigation UI
```

This is a reusable architecture demonstration, not evidence that project intelligence is a validated customer workflow.

## Domain boundary

- A **Project Subject** is a monitored real-world project. It owns Project Evidence and may have no known Site.
- A **Design Study** is the existing `infrastructure_projects` compatibility contract behind `/api/projects`. It must pin one Site and committed Evidence Snapshot before it can own Alternatives and Design Revisions.
- Sprint 002 does not link the two domains or rename historical Design Study persistence.

Migration v6 remains Design Proposals, v7 reconciles Project Evidence ownership under `project_subjects`, and v8 adds dedicated Project Intelligence runs.

## Evidence binding

The caller supplies an explicit non-empty set of bundle IDs. Binding order is canonical and never means “latest”. Every bundle must resolve under the same tenant and Project Subject. The binding pins bundle content/manifest identities, exact source versions, exact claims, retained passages, active/superseded membership and evidence as-of time.

Corrections require complete ancestry, preserve predicate, and must be acyclic. Superseded claims remain inspectable. Multiple incompatible active claims remain present. Changed bundle membership or content changes the binding identity.

## Reasoning semantics

The pure module reports:

- lifecycle stage: `pre_planning`, `planning`, `consented`, `construction`, `construction_complete` or `unclear`;
- separate planning and construction status findings;
- reported grid-connection targets and `future_target` / `elapsed_unverified` timing;
- all incompatible active claim groups;
- unresolved questions grounded in missing, unknown, conflicting or elapsed-target evidence;
- exact claim, source-version, source-content and passage references plus model/binding identity and limitations.

Publication recency never wins a conflict. `paused` remains compatible with construction stage. Refused/withdrawn planning and cancelled construction do not invent lifecycle stages. A past target never establishes completion, delay or failure. The contract contains no confidence/risk score, opportunity, recommendation or customer decision.

## Persistence and API

`project_intelligence_runs` is separate from Site-bound `module_runs`. A run stores its complete binding, signed specification, exact result and content hash. Read-time verification dispatches through the implementation identified by the stored module/binding version tuple, recalculates all identities, reruns that pure module and reconstructs the binding from committed bundles. Retaining the v1 implementation in this registry keeps v1 history readable when a later version becomes current. Identical and concurrent executions reuse one run; changed bindings or module versions produce a new run.

Public endpoints:

- `POST /api/project-subjects/{subject_id}/intelligence-runs`
- `GET /api/project-subjects/{subject_id}/intelligence-runs`
- `GET /api/project-intelligence-runs/{run_id}`

POST intentionally creates/reuses. Both GET paths are side-effect free and tenant scoped.

## Synthetic demonstration

`scripts/seed_project_intelligence_demo.py` creates an isolated synthetic Project Subject and four historical runs: supported construction; conflicting grid targets; an explicit correction producing a new supported binding; and insufficient stage evidence with an elapsed target. Re-running the script reuses exact bundles and runs.

The UI is read-only and isolated from Site map state. It exposes Overview, Evidence, Conflicts & unknowns, and History. Historical selection replaces the whole evidence/conclusion context, keeping source assertions visually distinct from Terrene conclusions.

## Verification model

The Project Evidence and Design Study focused suites now use a small tracked synthetic assessment rather than ignored retained assets. Default `pytest` skips the explicitly identified retained-data suites with a clear reason. `pytest --retained-data` checks both local retained directories first and fails immediately with an actionable prerequisite when absent.

The combined Project Evidence, Design Study and Project Intelligence suite passes 43 tests on SQLite and 43 tests on disposable PostgreSQL/PostGIS. In a temporary repository copy with every ignored retained-data root absent, the default suite passes 163 tests with 63 retained-data checks explicitly skipped, while `--retained-data` exits immediately and names all three missing prerequisites. With those roots present, the opt-in passes 226 tests. After reconciling the Terrene site-brief and portfolio interface, all 46 frontend Node tests, TypeScript, focused lint on the new/refined modules and the production build pass; the changed page retains its known 19 lint diagnostics. Browser QA covers all four synthetic histories, exact evidence and correction inspection, explicit historical selection, desktop and narrow layouts, the restored Terrene portfolio map, no horizontal overflow, and no browser errors. The production build retains its existing large-chunk advisory.

## Exclusions

No project editing, automated research, map redesign, Design Study linking, Scenario calculation, confidence bar, alert, recommendation or pursue/monitor/dismiss action is implemented. No actual infrastructure-project claim or customer validation is implied.
