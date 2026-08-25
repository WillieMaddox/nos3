---
key: —
slug: ground-counter-reconciliation
type: Story
epic: AINOS3-41 (coverage-expansion)
status: Pending Jira key
priority: Low
estimate: E 5 / T 1.5
opened: 2026-08-25
origin: AINOS3-95 (sparta-logging-gap-analysis)
---

# ground-counter-reconciliation — Reconcile ground and spacecraft command counters

**Summary:** EX-0001.01 was ruled out for the wrong reason: the workbook proposes reconciling spacecraft and ground command counters, not separating replayed bytes.

## Description

AINOS3-95 `AC4` found that our published rationale for `EX-0001.01` (replay valid commands)
answers a question SPARTA does not ask. We said replayed commands are byte-identical to
legitimate ones, so no telemetry field separates them — which is true and beside the point.

The workbook (`C&DH` row 13) proposes detecting a **mismatch**: log every command-counter
increment and alert when the ground's count of commands sent diverges from the spacecraft's
count of commands accepted. A replayed command increments the spacecraft counter with no
corresponding ground increment.

We already record every spacecraft-side counter — `CI.usCmdCnt`, `TO.usCmdCnt`, and all five
`CFE_*.CommandCounter`. The missing half is the **ground** count, which lives in COSMOS and has
never been joined to the telemetry stream.

⚠ This is the only item in the AINOS3-95 backlog needing a **new data path between two systems
that do not currently talk**, which is why it is sized at E 5 and sequenced last. It is also
the most architecturally interesting: a ground/spacecraft reconciliation channel would support
more than this one technique.

## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Establish whether COSMOS's command count is retrievable in a form joinable to the telemetry stream, and at what latency.
- [ ] `AC2` Determine the nominal mismatch envelope — commands lost, retried or issued outside COSMOS all create benign divergence, and the rule is unusable if that envelope is wide.
- [ ] `AC3` If viable, a reconciliation check with 0 FP over a nominal soak.
- [ ] `AC4` Validated against a LIVE replayed command.
- [ ] `AC5` `EX-0001.01` verdict updated either way; a documented negative is a valid outcome.

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`.
Results live here, not in a sprint plan.
