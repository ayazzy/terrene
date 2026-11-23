# Screening Context v1

Implemented 10 September 2026 from main `6dfeee6d31e71ecba79421b2e33255efc334ba1c`.

## Outcome

A reviewer can intentionally prepare a saved assessment's non-scoring context, inspect the persisted facts, gaps and provenance in Overview, select historical assessments, and preview/download a traceable self-contained HTML artifact. This improves Terrene's ability to reason about represented reality and tests a prospective screening workflow.

## Architecture and identifiers

- Module ID: `site_screening_context`.
- Module version: `site_screening_context_v1`.
- Binding/rules version: `screening_context_binding_v1`.
- Input: a validated, committed `land_evidence_v1` snapshot.
- Configuration: `include_cross_source_context`, default `true`; configurable through the Python execution API. The product action uses the default.

`screening_context.py` defines the typed result and pure offline rule execution. `screening_context_store.py` resolves assessment ownership and snapshot origin, executes the module, and uses the existing ModuleRun identity, content-hash and immutable persistence primitives. A narrow validation dispatch in `module_runs.py` leaves wetland verification unchanged. There are no new tables, dependencies or acquisition paths.

The specification signature includes configuration, declared rules and the typed result-contract hash. Snapshot, module, binding or configuration changes produce distinct run identities. Source timestamps come from evidence; runtime created/completed timestamps remain outside the semantic result. Scoped reads verify persisted integrity and recompute against committed evidence. Contradictions fail rather than overwrite history.

## Evidence semantics

The result groups physical/hydrological, ecology/habitat/designation, and built-world/transport observations and explicit gaps. Measurements, support, availability, source definitions, PHI habitat classifications, object/relationship identities and source/raw references retain their snapshot meanings. Unconnected capabilities are listed separately from observation groups.

Mapped-zero qualifications distinguish source-supported zero from real-world absence; zero mapped distance means contact/intersection. Partial rail-search coverage remains a gap, without a minimum-distance fact. Fixed semantic contexts present WorldCover versus OpenMap Local buildings, WorldCover wetland versus PHI, and distinct Ancient Woodland inventory editions when those observations coexist. There are no numerical conflict thresholds, scores, rankings, overall confidence, recommendations or progression decisions. Questions ask humans whether a gap/support limitation is material to their review.

Every fact and generated review item resolves to evidence or a declared capability. Gap records retain their original state, reason code, reason and references. The catalogue preserves public provenance identities and checksums while omitting raw storage/asset locations. Source URLs omit credentials, query parameters and fragments.

## API and UI behavior

| Endpoint | Behavior |
| --- | --- |
| `POST /api/assessments/{id}/screening-context` | Explicitly create/reuse snapshot and run for an owned, completed or terminal partial assessment with usable saved evidence. |
| `GET /api/assessments/{id}/screening-context` | Read stored default-version context or `null`; creates no records. |
| `GET /api/screening-context-runs/{id}` | Tenant-scoped, integrity-checked stored-run read. |
| `GET /api/assessments/{id}/screening-context/report` | Export existing context; 409 until prepared. |

Missing/wrong-organization records return 404, unusable or unsupported evidence returns 409, and contradictory persisted content returns an explicit 500 integrity failure without internal locations. Existing authentication applies to all four routes.

The compact Overview panel is keyed to the selected assessment and distinguishes absent, preparing, available and failed states. Collapsible groups expose exact support/provenance and an evidence-reference inspector, with a link to the existing Evidence tab. It does not write team status. Export uses the existing report dialog pattern, a sandboxed preview and explicit Download HTML link. The escaped artifact contains snapshot/run/content/boundary identities, evidence references, limitations and separately labelled **current team review status at export**, not historical decision state.

## Immutability and compatibility

Existing snapshot origins are reused, including historical registry versions. Older registries receive an explicit built-world limitation; missing objects are not relabelled as mapped zero. Assessments predating supported saved land evidence and multiple historical snapshot origins are preserved and reported as unsupported. V1 does not offer multi-origin selection.

No wetland implementation, binding, thresholds, inputs, legacy identifiers or saved assessments were changed. Existing historical manifests and wetland ModuleRuns remain exact before/after screening execution. Team review status remains mutable operational state, separate from calculated context.

## Verification

- Focused backend: **16 passed**; snapshot/projection/wetland regression: **39 passed**.
- Complete backend: **176 passed on SQLite**, **176 passed on disposable PostgreSQL 17/PostGIS 3.5** (`crc_test`). Existing dependency/reflection warnings remain.
- Frontend semantic suite: **24 passed**; `npx tsc --noEmit`: passed; `npm run build`: passed with existing bundle-size/classification advisories.
- Focused lint: new frontend modules/test passed. `app/page.tsx` retains 20 pre-existing diagnostics: 17 explicit `any`, one effect setState, one GET-body rule and one status-role rule. No unrelated lint changes.
- Backend tests cover tenant isolation/auth, read-only discovery, exact reuse, changed identities, historical origins, corruption/no overwrite, typed reference validation, source semantics, and escaped self-contained export.
- Final scope/staging review and `git diff --check`: passed. No private data, local databases, build output or QA fixtures are committed.

### Retained Oxford real-data verification

All 12 retained OpenMap Local Oxford cases replayed offline through snapshot and screening execution. Exact observations, support, gaps and objects were checked; all **33 referenced local raw objects** were present. No source reacquisition or historical report rewrite occurred.

| Retained case | OpenMap building fraction | WorldCover built-up fraction | PHI union fraction | Track minimum distance |
| --- | ---: | ---: | ---: | --- |
| Westgate | 0.4334733619796526 (13 objects) | 0.9532164383337427 | 0 | 447.4675132529079 m |
| Oxford station | 0.30407492325272334 (5 objects) | 0.9294104498660849 | 0 | 0 m (mapped contact) |
| Port Meadow | 0 | 0.0007011924048548014 | 0.9889667465216154 | 6.8546427777381655 m |
| Redbridge | 0 | 0.28472342797810385 | 0.10041910610549862 | No fact: partial search coverage |

These are retained source-specific fractions, not current surveys or interchangeable measurements. PHI union overlaps do not establish habitat condition or complete wetland extent.

The established `england-real-v1-final` wetland fixtures still pass exact saved-state/output parity. A separate comparison of newer OpenMap retained payloads to the unchanged wetland binding exposes a pre-existing unavailable-flood placeholder/provenance and explicit-gap timestamp difference. This iteration does **not** claim exact saved-payload-versus-binding parity for that newer set. Its tests establish exact wetland ModuleRun equality before/after adding screening context for all 12 newer cases. The binding and projection files remain unchanged.

### Browser QA

Used real persisted local records plus clearly labelled Westgate/Redbridge QA sites copied from retained evidence. Verified prepare/loading/available, stored reread, positive building evidence, distinct WorldCover semantics, object inspection, Redbridge zeros/partial-search gaps, historical Westgate context and registry limitation. Existing synthetic current v2 and historical v1 assessments returned the unsupported-evidence message without rewriting them. All five original sites and eight original assessments retained their full-row fingerprints.

The HTML preview rendered and the explicit download produced a **489,509-byte** Westgate artifact byte-identical to its authenticated report response. Desktop (1280 px) and the existing narrower in-app panel were visually inspected. No horizontal document overflow occurred at 1280 px. A requested 390 px viewport override did not change the hidden in-app tab (it remained 1280 px); phone-width QA is therefore not claimed. The override was reset. Chrome browser automation was unavailable.

## Known limitations

Rules need pilot feedback; human materiality judgments remain unresolved. Evidence is bounded by retained source coverage, dates and definitions. No new datasets, hosted deployment, credentials or production publication were introduced. Large catalogues use collapsible JSON inspection and may be verbose. Legacy multiple-origin selection, unsupported old evidence, phone-width QA and the pre-existing newer-fixture wetland provenance discrepancy remain explicit limitations.
