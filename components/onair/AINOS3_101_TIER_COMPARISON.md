# AINOS3-101 — tier comparison across the three confounds

Derived by `compare_tier_runs.py`. The `ROBUST` bar is 0.85 on the **minimum** F1 across LOIO folds, inherited verbatim and not moved (`AC4`).

## Cells

| Cell | Source | Mode scope | Folds | Classes | LOIO acc (tech) | LOIO acc (cluster) | ROBUST | STABLE-MID | HIGH-VAR | DEAD |
|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `rebuild_5fold` | rebuild | SUNSAFE (collected) | 5 | 17 | 0.613 | 0.700 | 3 | 1 | 11 | 2 |
| `rebuild_3fold` | rebuild | SUNSAFE (collected) | 3 | 17 | 0.573 | 0.687 | 1 | 5 | 6 | 5 |
| `v3stage_sunsafe_3fold` | v3stage | MODE_SUNSAFE | 3 | 13 | 0.757 | 0.777 | 2 | 1 | 9 | 1 |
| `v3stage_allmodes_3fold` | v3stage | all modes | 3 | 17 | 0.682 | 0.691 | 0 | 2 | 9 | 6 |

## `rebuild_5fold` — per-class tiers

`min` is what sets the tier. `scored on` is *cluster* where the class is telemetry-indistinguishable from a sibling, because the cluster is the label the system actually emits.

| Class | Tier | Scored on | min F1 | mean F1 | max F1 | Fold F1s |
|---|---|---|--:|--:|--:|---|
| `EX-0014.03` | ROBUST | technique | 0.925 | 0.944 | 0.965 | 0.95, 0.97, 0.93, 0.94, 0.93 |
| `EX-0008.01` | ROBUST | cluster | 0.887 | 0.950 | 0.974 | 0.89, 0.97, 0.95, 0.97, 0.96 |
| `EX-0008.02` | ROBUST | cluster | 0.887 | 0.950 | 0.974 | 0.89, 0.97, 0.95, 0.97, 0.96 |
| `nominal` | STABLE-MID | technique | 0.777 | 0.813 | 0.850 | 0.79, 0.78, 0.81, 0.85, 0.84 |
| `EX-0012.12` | HIGH-VAR | cluster | 0.364 | 0.509 | 0.622 | 0.52, 0.52, 0.62, 0.51, 0.36 |
| `EX-0014.01` | HIGH-VAR | cluster | 0.364 | 0.509 | 0.622 | 0.52, 0.52, 0.62, 0.51, 0.36 |
| `EX-0012.03` | HIGH-VAR | cluster | 0.144 | 0.324 | 0.481 | 0.48, 0.14, 0.33, 0.34, 0.32 |
| `EX-0012.04` | HIGH-VAR | cluster | 0.144 | 0.324 | 0.481 | 0.48, 0.14, 0.33, 0.34, 0.32 |
| `EX-0014.04` | HIGH-VAR | technique | 0.009 | 0.766 | 0.960 | 0.01, 0.96, 0.94, 0.96, 0.96 |
| `DE-0003.01` | HIGH-VAR | technique | 0.000 | 0.375 | 0.614 | 0.61, 0.27, 0.43, 0.56, 0.00 |
| `DE-0003.02` | HIGH-VAR | technique | 0.000 | 0.237 | 0.746 | 0.75, 0.06, 0.27, 0.00, 0.11 |
| `DE-0003.06` | HIGH-VAR | technique | 0.000 | 0.557 | 0.796 | 0.59, 0.00, 0.65, 0.80, 0.75 |
| `EX-0012.05` | HIGH-VAR | technique | 0.000 | 0.083 | 0.366 | 0.01, 0.03, 0.00, 0.01, 0.37 |
| `EX-0012.07` | HIGH-VAR | technique | 0.000 | 0.413 | 0.883 | 0.00, 0.00, 0.84, 0.88, 0.34 |
| `EX-0012.09` | HIGH-VAR | technique | 0.000 | 0.758 | 0.971 | 0.94, 0.00, 0.97, 0.96, 0.93 |
| `DE-0003.08` | DEAD | technique | 0.000 | 0.021 | 0.088 | 0.09, 0.00, 0.00, 0.00, 0.02 |
| `EX-0012.08` | DEAD | technique | 0.000 | 0.009 | 0.046 | 0.00, 0.00, 0.05, 0.00, 0.00 |

## `AC2` — the near-bar class

**`EX-0012.12`** — min F1 **0.3639** against the 0.85 bar (short by 0.4861), tier `HIGH-VAR`, scored on cluster. Fold minima: 0.523, 0.520, 0.622, 0.514, 0.364.

## Per-class `min` F1 across cells

A class that rises between two cells rose because of the one thing that differs between them.

| Class | `rebuild_5fold` | `rebuild_3fold` | `v3stage_sunsafe_3fold` | `v3stage_allmodes_3fold` |
|---|--:|--:|--:|--:|
| `DE-0003.01` | 0.000 | 0.032 | — | 0.000 |
| `DE-0003.02` | 0.000 | 0.000 | — | 0.000 |
| `DE-0003.06` | 0.000 | 0.000 | — | 0.000 |
| `DE-0003.08` | 0.000 | 0.000 | — | 0.000 |
| `EX-0008.01` | 0.887 | 0.758 | 0.651 | 0.000 |
| `EX-0008.02` | 0.887 | 0.758 | 1.000 | 0.806 |
| `EX-0012.03` | 0.144 | 0.340 | 0.000 | 0.078 |
| `EX-0012.04` | 0.144 | 0.340 | 0.000 | 0.078 |
| `EX-0012.05` | 0.000 | 0.340 | 0.338 | 0.312 |
| `EX-0012.07` | 0.000 | 0.000 | 0.302 | 0.047 |
| `EX-0012.08` | 0.000 | 0.000 | 0.000 | 0.000 |
| `EX-0012.09` | 0.000 | 0.493 | 0.000 | 0.000 |
| `EX-0012.12` | 0.364 | 0.521 | 0.079 | 0.000 |
| `EX-0014.01` | 0.364 | 0.521 | 0.079 | 0.000 |
| `EX-0014.03` | 0.925 | 0.884 | 0.000 | 0.000 |
| `EX-0014.04` | 0.009 | 0.009 | 0.000 | 0.000 |
| `nominal` | 0.777 | 0.763 | 0.874 | 0.801 |

