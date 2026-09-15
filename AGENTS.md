# Terrene repository instructions

These instructions apply to the entire repository.

## Authority and orientation

- Read this file and `docs/CURRENT-STATE.md` at the start of every task. `CURRENT-STATE.md` is the default orientation document.
- Inspect the implementation before assuming documentation is current. Code is authoritative when implementation and documentation disagree.
- After orientation, inspect only the code, tests and documentation materially relevant to the bounded objective. Do not perform a broad repository audit by default.
- Load other durable documents, historical reports or broad repository areas only when the task genuinely requires them. The durable documentation hierarchy is: `TERRENE-NORTH-STAR.md` for strategy; `ARCHITECTURE.md` for durable architecture; `DECISIONS.md` for append-only decisions; `CUSTOMER-DISCOVERY.md` for hypotheses and evidence; `CURRENT-STATE.md` for implemented state. Historical reports remain valid records of their implementation versions.

## Task discipline

- One Codex session executes one coherent, bounded objective with one primary technical outcome. Stop after reporting completion; never begin the recommended next task automatically.
- If a proposed task contains outcomes that can be implemented or tested independently, split them into sequential iterations unless atomic implementation is technically necessary. A combination such as backend contract + major UI redesign + state refactor + bug fix + responsive redesign is a warning that the task is too large.
- When substantial frontend work needs a new backend or data contract, prefer establishing and verifying the contract first, then consuming it in a later UI task. A genuinely tiny contract-and-UI change need not be split.
- Do not perform opportunistic refactors, unrelated lint/test fixes or a second feature. Question scope expansion before implementing it.
- Before substantial implementation, ask whether the work materially improves Terrene's ability to (A) represent reality, (B) reason about reality, (C) test changes to reality or (D) operationalize intelligence for a validated workflow. If none applies, question why it should exist.
- Avoid new dependencies unless materially justified.
- Task prompts should contain task-specific context and requirements, not repeat standing repository rules already defined here.

## Allowance-aware working protocol

Terrene is developed within a limited Codex allowance. Preserve it by making each
task a small, verifiable deliverable rather than by weakening evidence or safety
checks. Before implementation, the task request must state: the outcome, relevant
files or contract, acceptance checks, model tier when it matters, and an explicit
stop point (normally "commit and stop"). See
[`docs/CODEX-WORKING-AGREEMENT.md`](docs/CODEX-WORKING-AGREEMENT.md) for the
copyable task card and model-selection guide.

- Use the lightest available model that can safely complete the task. Routine
  discovery, narrow edits and focused tests belong on a high-volume/lightweight
  model; reserve stronger reasoning for scientific semantics, architecture,
  non-obvious failures and final review.
- Begin with the linked current-state and task files. Do not perform a broad
  repository audit, reread historical reports, or repeat successful checks unless
  the change, a failure or a new risk requires it.
- Report only outcome, files changed, checks actually run, unresolved limits and
  commit. Link existing reports rather than reproducing their contents.
- Do not spend paid credits, enable fast mode, create parallel agents or add
  integrations merely to accelerate a routine Terrene task unless the founder
  explicitly asks for that trade-off.

## Branches and commits

- Never implement feature, fix, data, refactor or chore work directly on `main`.
- Start from current known-good `main` unless the task explicitly depends on another branch. Use `feat/<short-name>`, `fix/<short-name>`, `data/<source-name>`, `refactor/<short-name>`, `chore/<short-name>` or `docs/<short-name>`.
- Make coherent commits; do not force one commit per task. Roughly 1–3 atomic commits is usually appropriate. Do not mix unrelated changes.
- Prefer clear subjects such as `fix: synchronize sidebar compact state`, `feat: add OpenMap Local acquisition`, `feat: represent built-world parcel relationships` or `test: verify Oxford built-object evidence`.

## Historical, environmental and scientific integrity

- Never silently mutate historical assessments, Evidence Snapshots, ModuleRuns, model versions, evidence provenance or source identities.
- A changed boundary, dataset release, processing method, model, binding or source evidence should create a new version, snapshot or run where appropriate rather than rewrite history.
- Missing data is not zero. Mapped absence is not necessarily real-world absence. Source-specific evidence must not be silently broadened.
- Evidence completeness is not predictive confidence. Models and interpretations remain distinct from reusable Terrene Earth facts. Never fabricate environmental measurements.
- Scientifically changed interpretations require explicit versioning.
- Preserve legacy `CRC`/`crc` technical identifiers when they encode compatibility, persistence, hashes, signatures, database structures, model identity or reproducibility. Use Terrene for new product and project language; do not run a global rename.

## Verification and completion

- Match verification to the risk and affected surface. Start with focused tests, then add relevant regression, type checking/compilation, lint on changed or relevant code, production build, browser QA for UI changes or real-data verification for evidence/model changes as warranted. Do not automatically run expensive unrelated suites when focused and relevant regression verification is sufficient.
- Never claim a check that was not run. State credentials or service blockers explicitly.
- Before completion, inspect the final diff for scope creep, run `git diff --check`, verify intended changes are committed, and confirm no secrets, local databases, raw/private/licensed data or generated junk are staged.
- Update durable documentation only when warranted: Current State for material implementation changes; Architecture for durable architecture changes; Decisions for meaningful product/architecture decisions; Customer Discovery for actual market evidence or major hypothesis changes; North Star only for strategic thesis changes.

Use this default completion structure:

1. `## Outcome`
2. `## Implementation / architecture`
3. `## Files changed`
4. `## Verification`
5. `## Historical / compatibility impact`
6. `## Known limitations`
7. `## Git` with branch and commits
8. `## Recommended next task`

Add `## Source`, `## Evidence semantics` and `## Real-data verification` for data/evidence work; `## Root cause` for fixes; and `## Browser QA` for UI work.
