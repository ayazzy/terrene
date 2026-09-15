# Sprint close — independent evidence and terrain display

Closed 15 September 2026. Engineering pauses until the founder returns, expected
20 September, while market research informs the next priority. This is a completed
engineering checkpoint, not a claim of product-market fit or production launch.
No automatic restart, scheduled work or new implementation is authorized by this record.

## Outcome

Terrene can acquire and retain independent geographic evidence, browse exact
captures and display verified terrain in its operating map. The original Oxford
analysis remains accessible. The founder will use the pause to investigate which
customer decision and intelligence service should receive priority.

## Implementation / architecture

- Independent source adapters cover England/Scotland SSSI, EA terrain and surface
  elevation, dated Sentinel-2 imagery and historical NASA POWER/MERRA-2 weather,
  subject to each source's geographic, temporal and size limits.
- Organization-scoped catalogue and detail reads expose retained evidence with
  provenance and explicit availability. Data sources provides the capture browser.
- Four fresh captures populate the active Oxford workspace: DTM, DSM, one
  19 June 2025 satellite observation and six daily weather variables for 2025.
- The terrain preview contract verifies retained bytes and produces a bounded
  display derivative. Layers supports selection, hide/show/remove, extent fitting,
  elevation legend and source disclosure. Responsive acceptance is complete.

See [Current State](CURRENT-STATE.md), [Oxford captures](OXFORD-CAPTURE-LIBRARY.md),
[preview contract](TERRAIN-PREVIEW-CONTRACT.md) and [terrain UI](TERRAIN-MAP-LAYER.md).

## Files changed

This closeout adds this handoff, marks the pause in Current State and records the
founder's research plan in Customer Discovery. Application code is unchanged.
A local ignored backup preserves the active Oxford runtime data.

## Verification

Existing acceptance results, not rerun for this documentation-only closeout:

- 149 frontend tests; TypeScript; focused lint; production build.
- Terrain backend: 285 affected tests on each of SQLite and PostgreSQL/PostGIS;
  235 independent inverse-coordinate pixel checks in the prior contract report.
- Real Oxford desktop and 390 px / 320 px browser acceptance; no console warnings
  or errors in the final responsive pass. Existing build advisories remain.

Closeout checks: SQLite backup integrity is `ok`; all 82 non-database files were
hash-verified against the active data directory, including 78 stored object files.
Only the three intended Markdown files are committed. No raw evidence, databases,
credentials or generated outputs enter Git.

## Historical / compatibility impact

No assessments, snapshots, ModuleRuns, source versions, identities or model
interpretations were changed by closeout. The backup uses SQLite's backup API and
copies retained files; it does not relocate or reconfigure the running application.

## Local restart and data preservation

Implementation checkpoint: `8353700` on `feat/terrain-map-layer`.
Closeout branch: `docs/sprint-close-2026-09-15`, directly based on that checkpoint.
Do not assume these changes have been merged to main or deployed.

Active configuration in the ignored local `.env`:

- `CRC_ENV=development`
- `CRC_DATA_DIR=/private/tmp/terrene-oxford-ui.VVWWW7`
- `DATABASE_URL=sqlite:////private/tmp/terrene-oxford-ui.VVWWW7/oxford-qa.db`

Verified local backup relative to the repository:
`data/local-backups/sprint-close-2026-09-15/`.
It contains `oxford-qa.db`, `objects/`, remaining retained source files and
`backup-verification.json`. This is a local, Git-ignored backup, not an off-device
backup. It preserves the complete directory's non-database file bytes.

On return, inspect existing local processes before starting duplicate servers.
Use `scripts/dev.sh` with the intended local `.env`. If the temporary data directory
has disappeared, restore from the backup before starting the app. Prefer restoring
the original directory layout so historical absolute file references remain valid;
do not silently start against the unrelated default `data/crc.db`.

Oxford Site: `0277a958-022d-54f9-adb1-31364b548f08`.
Saved assessment: `c10d373d-444d-5d04-9f3b-25c36a8f0d45`.
Local URL: `http://localhost:3000/?mode=site&entity=site&id=0277a958-022d-54f9-adb1-31364b548f08`.
Terrain: Layers → Search this view → EA terrain `11051877`.
Independent captures: Data sources. The five saved map-scene sources and the
independent capture library are different evidence collections.

## Known limitations / remaining work

The following are candidates, not an instruction to build every item:

1. Verified exact-capture Sentinel-2 true-colour preview contract, then its map UI.
2. Surface elevation display and historical weather charts as separate iterations.
3. Customer-facing area/source selection, acquisition requests, progress and retries.
4. Explicit new snapshot/model bindings for newly acquired evidence.
5. Broader England/Scotland coverage; Wales and Northern Ireland remain deferred.
6. Indexed geographic discovery, larger-area processing and efficient tiled delivery.
7. Saved investigations, document/survey intake and evidence-linked asset/project identity.
8. Compatible temporal comparisons, monitoring and reviewable alerts.
9. Validated analytical modules; climate assessment additionally needs suitable
   projections, local inputs, explicit scenarios and a validated impact model.
10. Scenario editing and computed consequences for proposed interventions.
11. Hosted end-to-end deployment, tenant acceptance, backup/recovery and operations.
12. A customer-validated deliverable, onboarding, pricing and paid pilot.

Historical weather is not a climate forecast. The wetland model remains unvalidated.
National support is source-specific. The commercial market remains open.

## Resource-efficient working agreement for the next sprint

- Use one fresh task per bounded deliverable, with a short handoff and file links.
  Keep an active task together until its deliverable is complete; do not fragment
  every small edit into a new context.
- Match model strength to the task: try the separately reported Spark allowance
  for focused coding; use Luna for routine tasks and stronger models for difficult
  architecture, scientific semantics, debugging or review. Check current account
  availability on return; no fixed cost or quality guarantee is implied.
- Prefer standard speed when conserving allowance; fast mode consumes more credits.
- Ask for a concrete outcome, relevant files, acceptance checks and a clear stop point.
- Read Current State and relevant implementation, not the full historical archive.
  Keep tool output and completion reports concise; link existing reports instead
  of reproducing them. Avoid unrelated exploration and repeated status requests.
- Run focused verification, then relevant regression/build/browser checks once the
  change is ready. Repeat only after a change, failure or unresolved concern.
- Keep evidence-integrity, authorization and scientific checks even when economizing.
  Fewer checks are not automatically more efficient if they create rework.
- Use manual browser exploration and collect reproducible issues in one short batch.
  Use deterministic local scripts for repeated checks when appropriate.
- Avoid parallel agents and optional integrations for small tasks. Consider disabling
  unused plugins/MCP servers in a focused coding workspace; no settings were changed.
- Track allowance around meaningful work blocks and stop at the agreed deliverable.
  A requested dollar budget is not an enforceable billing cap through this assistant.

These recommendations align with the official usage guidance consulted on
15 September: https://learn.chatgpt.com/docs/pricing . Account limits, model access
and prices can change and should be checked when work resumes.

## Market research during the pause

Compare a few candidate workflows without committing the architecture to one market.
For each, record the buyer, specific decision, trigger/frequency, current process,
cost of delay/error, existing spend, necessary evidence and smallest useful paid
output. Preserve source links and distinguish desk research from practitioner
statements and actual payment commitments. Competitor breadth is not proof of demand.

Bring back a short comparison of climate assessment, infrastructure intelligence
and any stronger candidate uncovered. Record findings in Customer Discovery when
available; no new interviews or validated demand are claimed today.

## Git

Key recent commits: `fad83de` capture browser; `fe8d7c1` Oxford capture population;
`f28453e` terrain preview contract; `f28d20a` terrain map layer;
`8353700` responsive acceptance fixes. Closeout commit subject:
`docs: close evidence and terrain sprint for research pause`.
No merge, push or deployment is part of closeout.

## Recommended next task

Review the founder's market findings first and select one bounded deliverable.
The provisional engineering next step is the Sentinel-2 preview contract; market
evidence may change its priority. Resume only when the founder requests it.

Suggested restart prompt:

> Read AGENTS.md, docs/CURRENT-STATE.md and docs/SPRINT-CLOSE-2026-09-15.md.
> We are resuming from the completed terrain sprint. Here are my market findings:
> [insert findings]. Help choose one bounded next task before implementing it.
> Keep context and reporting concise and match verification to the change.
