# Codex working agreement

This is a durable operating agreement for completing Terrene work within the
included Codex allowance. It does not alter evidence, authorization, scientific
or verification requirements. Account limits, model access and reset times are
account-specific; inspect the Codex usage dashboard before planning a work block.

## One task card

Start each implementation task with this compact card. Keep the task open until
the stated deliverable is complete; do not make a new task for every small edit.

```text
Outcome: [one externally observable result]
Why now: [accepted sprint priority]
Relevant context: [up to 3–8 files/URLs and exact IDs if needed]
In scope: [one bounded change]
Out of scope: [nearby work that must not be started]
Acceptance: [focused tests/checks and any required browser or real-data QA]
Stop point: [for example: "commit the verified change and stop"]
Selected model: [Luna / Terra / Sol / Spark when available, with a one-line reason]
```

If the outcome does not improve Terrene's ability to represent reality, reason
about reality, test a change to reality, or operationalize intelligence for a
validated workflow, decide whether it should exist before spending an engineering
task on it.

## Model and speed policy

Choose for confidence and failure cost, not nominal task size or speed.
Availability and allowances can change, so this is a task-routing policy rather
than a guarantee. Do not downgrade a task merely to conserve allowance: rework,
missed evidence semantics and incorrect architecture cost more than a capable
first pass.

Select the model in Codex **before** creating the task. A prompt can document
the intended choice, but it does not change the model of an active task. Finish
the bounded deliverable and create a fresh task at its handoff when a different
model is warranted.

| Work | Default choice | Escalate only when |
| --- | --- | --- |
| File discovery, extraction, classification, concise documentation, mechanical test execution | Luna | Any ambiguity, design decision or interpretation is required |
| Tiny mechanical UI/code/test edit with an explicit contract | Spark, if separately available; otherwise Terra | The result is not immediately verified or the change has broader state/data impact |
| Ordinary production feature, code review, debugging with a known bounded surface | Terra | The result would establish scientific meaning, durable architecture or a safety-critical rule |
| Evidence semantics, environmental/scientific interpretation, architecture, hard debugging, final high-risk review | Sol | Do not escalate further by default |

Use standard speed. Do not use paid credits unless explicitly asked.
Avoid image generation, broad web research, optional plugins and parallel agents
for a routine coding task. They may be useful for a named objective, but they are
not free acceleration.

When uncertain, start implementation on Terra. A Luna or Spark result may support
Terra work, but should not become the sole basis for an evidence-sensitive or
ambiguous product decision. The requested acceptance checks—not the model tier—
remain the quality gate.

## Efficient execution sequence

1. Read `AGENTS.md`, `docs/CURRENT-STATE.md`, and only the linked task files.
2. Inspect the smallest relevant implementation and tests before proposing a
   change. State the intended contract and stop point.
3. Implement the single deliverable. Keep terminal output narrow and avoid broad
   searches or repeated status checks.
4. Run focused checks first. Add type checking, build, browser QA, PostgreSQL or
   real-data verification only when the affected surface warrants it.
5. Inspect the final diff, run `git diff --check`, commit the coherent change and
   stop. Do not start the suggested next task automatically.

## Handoffs and research

At a pause, record only: current branch/commit, completed deliverable, exact next
decision, relevant files and IDs, verification already passed, blockers and safe
restart command. Never paste long historical summaries into a new task when a
file link is enough.

## Copyable restart request

```text
Read AGENTS.md, docs/CURRENT-STATE.md and [specific handoff].
Outcome: [one bounded result].
Relevant context: [files and IDs].
Acceptance: [checks].
Stop point: commit and stop.
Selected model: [model] because [reason]. Use standard speed and do not spend credits.
```
