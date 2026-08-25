---
key: AINOS3-101
slug: retrain-clean-corpus
type: Story
epic: AINOS3-98 (corpus-integrity)
status: Backlog
priority: Medium
opened: 2026-08-23
sprints: [28]
---

# AINOS3-101 — Retrain + re-derive tiers on the clean corpus — is `ROBUST` reachable?

**Summary:** 

## Description



## Acceptance criteria

The single living list. Nothing here is superseded or extended by a sprint plan.

- [ ] `AC1` Retrain and re-derive tiers on the clean corpus; report whether `ROBUST` is reachable.
- [ ] `AC2` Designated test case `IMP-0005` (min F1 0.8481 against a 0.85 bar) reported explicitly.
- [ ] `AC3` ⚠ The like-for-like control is produced — tiers re-derived on `csv_corpus_v3stage` restricted to the same mode scope — or the comparison confounds cleaner data with narrower scope.
- [ ] `AC4` ⚠ The 0.85 bar is **not** moved; more instances make `ROBUST` harder (min over more folds).
- [ ] `AC5` Deployment, if any, follows the `AINOS3-37` discipline: one-line ini change, one-line rollback, live-verified, build tree synced. **Not deploying is a valid outcome.**

## Log

Dated, append-only. Starts at the first real event — creation is implied by `opened:`. Results live here, not in a sprint plan.
