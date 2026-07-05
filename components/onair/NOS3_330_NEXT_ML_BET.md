# NOS3-330 — Next big-ML bet: Phase 5 vs Phase 6 vs consolidate

**Spike verdict (one page).** Date: 2026-07-05.

| Option | Verdict | One-line reason |
|---|---|---|
| **Phase 5** — VAE / DeepSAD (deep semi-supervised detection) | **NO-GO (now)** | Phase 4 already showed deep models plateau on this data; the detection gaps are information-limited, which a bigger model can't fix. |
| **Phase 6** — GNN/GAT (graph root-cause isolation) | **DEFER (conditional)** | Overlaps the just-shipped explanation layer (NOS3-311/312); "very high" complexity; incremental value unproven until coverage is broadened + operators ask for causal chains. |
| **Consolidate** — harden deployed system + add *signal* | **GO** | The binding constraint is observability, not model capacity. The highest-value lever (NOS3-321 extra MIDs) adds information, not architecture. |

## The one argument that decides it: the constraint is *information*, not *model capacity*

Every recent result points the same way — more modeling won't move the gaps, more signal will:

- **NOS3-301:** PASSIVE attack-labeling is an **information limit, not a modeling one** — mode-aware / rebalanced / per-mode heads *all* left it flat. A deeper model (Phase 5) inherits the same limit.
- **Phase 4 (TCN):** a global deep detector reached AUCPR 0.67 (**below** the v5 IF's SUNSAFE recall); the per-subsystem TCN ensemble landed **within v3's noise band** (LOIO 0.654). Deep architectures already plateaued here → closed as diminishing returns.
- **DEAD classes:** the *nominal-ambiguous* ones (`DE-0003.03/.08/.09`, `EX-0014.03`) are unlabelable because their discriminating MIDs were **pruned** — a signal problem, fixed by NOS3-321, not by a new model.
- **NOS3-306:** the classifier may be leaning on generic activity counters — a signal-quality question, not a capacity one.

A VAE or a GNN is a bigger hammer. The problem isn't hammer size; it's that some nails aren't in the board (unobserved signal).

## Per-option detail

**Phase 5 — VAE / DeepSAD.** *Data sufficiency:* marginal — the ~3-instance corpus was already thin for the TCN; deep semi-supervised models are data-hungry and per-class labels are sparse. *Expected lift over v5+v3:* low, on Phase-4 precedent (reconstruction-based deep detection didn't beat the per-mode IF). *Operational value:* latent "mode discovery" is neat but the four ADCS modes are already known/routed. **The one hedge:** DeepSAD (semi-supervised, *uses* the attack labels the IF ignores) is the only variant with a plausible edge — revisit **only after NOS3-321 broadens the signal**, which also enlarges its training basis.

**Phase 6 — GNN/GAT root-cause.** *Capability:* trace an anomaly backward through a subsystem dependency graph → causal chain. *Overlap:* NOS3-311/312 already ship per-incident SHAP top-fields ("why"); graph root-cause is a more sophisticated version of the same operator need. *Complexity:* "very high" (per the plan's own table); needs a curated dependency graph + enough multi-subsystem anomaly examples to learn edges (sparse). *Verdict:* real long-term value, but **premature** — defer until (a) coverage is broadened (321) and (b) NOS3-322 stakeholder feedback shows operators need causal chains beyond the current explanations.

**Consolidate.** The deployed stack (v5 per-mode IF + v3 classifier + incident aggregation + explanations) is defensible, drift-free (5-day soak), and now explainable. Its dominant gaps are signal-limited. The ungated, high-value work is already scoped: **NOS3-321** (extra MIDs — the actual PASSIVE/DEAD-class fix), **NOS3-305** (selective hybrid, +6 pts), **NOS3-306** (audit, cheap precursor).

## Recommended path

1. **Consolidate + add signal.** Make NOS3-321 the next headliner; it's the lever the evidence keeps pointing at. Pair with 306 → 305.
2. **Re-evaluate Phase 5 (DeepSAD only) *after* 321** — with more MIDs and a larger corpus the data-sufficiency picture changes; that's the trigger to reopen this.
3. **Hold Phase 6** until coverage is broad and stakeholders (322) explicitly want causal-chain root-cause beyond the shipped top-fields explanations.

**Net:** no new big-ML phase now. Invest in observability (signal), not architecture.
