# Terrene repository instructions

These instructions apply to the entire repository.

## Authority and orientation

- Inspect the implementation before assuming documentation is current. Code is authoritative when implementation and documentation disagree.
- Read `docs/CURRENT-STATE.md` for orientation, then inspect the relevant code, tests and implementation reports. `CURRENT-STATE.md` is navigation, not a substitute for repository inspection.
- Durable documentation hierarchy: `TERRENE-NORTH-STAR.md` for strategy; `ARCHITECTURE.md` for durable architecture; `DECISIONS.md` for append-only decisions; `CUSTOMER-DISCOVERY.md` for hypotheses and evidence; `CURRENT-STATE.md` for implemented state. Historical reports remain valid records of their implementation versions.

## Task discipline

- One Codex session executes one coherent, bounded objective. Stop after reporting completion; never begin the recommended next task automatically.
- Do not perform opportunistic refactors, unrelated lint/test fixes or a second feature. Question scope expansion before implementing it.
- Before substantial implementation, ask whether the work materially improves Terrene's ability to (A) represent reality, (B) reason about reality, (C) test changes to reality or (D) operationalize intelligence for a validated workflow. If none applies, question why it should exist.
- Avoid new dependencies unless materially justified.

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

- Run verification proportionate to the change: focused tests → relevant regression suite → type checking/compilation → lint on changed or relevant code → production build → browser QA for UI changes → real-data verification for evidence/model changes.
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
