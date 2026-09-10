# Codex workflow

Use this lifecycle for each bounded repository task:

1. Read root `AGENTS.md`.
2. Read `docs/CURRENT-STATE.md` as the default orientation document.
3. Confirm that the task has one primary technical outcome. Split independently implementable or testable outcomes into sequential iterations unless they must be atomic.
4. Inspect only the code, tests and documentation materially relevant to the objective; code is authoritative when docs drift. Load broader durable documents, historical reports or repository areas only when genuinely required, and do not begin with a broad repository audit.
5. Inspect Git status, branch, history and remotes. Preserve unrelated user changes.
6. Update from current known-good `main` when safe and appropriate. Do not rewrite history or force-push over unrelated work.
7. Create one dedicated branch using the repository naming conventions.
8. Reproduce the current behavior or problem where relevant.
9. Implement only the bounded scope; do not start a second feature or opportunistic refactor.
10. Add or update focused tests.
11. Run verification proportionate to the risk and affected surface, escalating from focused checks only as warranted. Do not run expensive unrelated suites automatically, and record exactly what ran.
12. Inspect the entire diff for scope, safety, compatibility and accidental generated/private content; run `git diff --check`.
13. Update durable documentation only when the change meets its maintenance threshold.
14. Commit coherent changes, normally in roughly 1–3 atomic commits.
15. Push the dedicated branch when authentication and the intended remote are verified.
16. Report completion using the structure below, recommend at most one next task, and stop.

When substantial frontend work depends on a new backend or data contract, normally establish and verify the contract in one iteration and consume it in a later UI iteration. Keep genuinely tiny changes atomic when splitting would add ceremony without reducing risk.

## Repository sync protocol

When a ChatGPT Terrene strategy, product or engineering conversation creates a durable change to the North Star, architecture, current implementation understanding, commercial hypothesis/evidence or a major technical/product decision, create a bounded docs-only sync task for the corresponding repository document.

Important strategic knowledge must not remain only in chat history. Apply the maintenance rules in `AGENTS.md`; avoid documentation churn and do not rewrite historical implementation reports.

## Default completion report

```markdown
## Outcome

## Implementation / architecture

## Files changed

## Verification

## Historical / compatibility impact

## Known limitations

## Git

Branch:
Commits:

## Recommended next task
```

Add the following task-specific sections when applicable:

- Data/evidence work: `## Source`, `## Evidence semantics`, `## Real-data verification`.
- Bug fixes: `## Root cause`.
- UI: `## Browser QA`.

Never claim verification that did not run, and never begin the recommended next task automatically.
