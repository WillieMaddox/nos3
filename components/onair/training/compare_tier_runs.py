#!/usr/bin/env python3
"""AINOS3-101 — assemble the tier tables from several LOIO runs into the one
comparison that answers "is ROBUST reachable, and if not, why".

Each *cell* is one `retrain_clean_corpus.py` output directory. A cell differs
from its neighbours in exactly one of the three confounds (data cleanliness,
mode scope, fold count), so a tier that moves between two cells is attributable
to the thing that changed between them — which is the whole point of `AC3`.

It derives the tiers for any cell that lacks them (same rule, same 0.85 bar, via
`derive_classifier_tiers.py`), then reports:

  * per-cell tier counts and LOIO accuracy
  * the per-class tier table for the headline cell, with the fold minima that set it
  * the NEAR-BAR class (`AC2`) — the surviving class closest to 0.85 from below
  * per-class `min`-F1 deltas across cells

Usage:
    python3 components/onair/training/compare_tier_runs.py \\
        --cell headline=data/onair/models/rebuild29/sunsafe_5fold \\
        --cell ctrl_v3_sunsafe=data/onair/models/rebuild29/control_v3stage_sunsafe \\
        --cell ctrl_v3_allmodes=data/onair/models/rebuild29/control_v3stage_allmodes \\
        --headline headline --out components/onair/AINOS3_101_TIER_COMPARISON.md
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
ROBUST_BAR = 0.85          # inherited verbatim; AC4 forbids moving it


def ensure_tiers(cell_dir: str, label: str) -> dict:
    """Derive the tiers for a cell if absent, then load them."""
    out = os.path.join(cell_dir, "classifier_tiers.json")
    if not os.path.exists(out):
        cmd = [sys.executable, os.path.join(THIS_DIR, "derive_classifier_tiers.py"),
               "--cache", os.path.join(cell_dir, "loio_predictions.npz"),
               "--taxonomy", os.path.join(cell_dir, "cluster_taxonomy.json"),
               "--out", out, "--label", label]
        print(f"[{label}] deriving tiers…")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    return json.load(open(out))


def near_bar(tiers: dict) -> tuple[str, float] | None:
    """The `AC2` designee: the class whose fold-min F1 is nearest 0.85 from
    below. `nominal` is excluded — it is not an attack label and its F1 is set
    by the detection problem, not the classification one."""
    cands = [(c, v["f1_min"]) for c, v in tiers["classes"].items()
             if c != "nominal" and v["f1_min"] < ROBUST_BAR]
    return max(cands, key=lambda kv: kv[1]) if cands else None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cell", action="append", required=True, metavar="LABEL=DIR")
    p.add_argument("--headline", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    cells: dict[str, str] = {}
    for spec in args.cell:
        label, _, d = spec.partition("=")
        if not d:
            raise SystemExit(f"--cell needs LABEL=DIR, got {spec!r}")
        cells[label] = d
    if args.headline not in cells:
        raise SystemExit(f"--headline {args.headline!r} is not one of {list(cells)}")

    tiers = {lab: ensure_tiers(d, lab) for lab, d in cells.items()}
    taxa = {lab: json.load(open(os.path.join(d, "cluster_taxonomy.json")))
            for lab, d in cells.items()}

    L: list[str] = []
    L.append("# AINOS3-101 — tier comparison across the three confounds\n")
    L.append("Derived by `compare_tier_runs.py`. The `ROBUST` bar is 0.85 on the "
             "**minimum** F1 across LOIO folds, inherited verbatim and not moved "
             "(`AC4`).\n")

    # ─── per-cell summary ───────────────────────────────────────────────
    L.append("## Cells\n")
    L.append("| Cell | Source | Mode scope | Folds | Classes | LOIO acc (tech) "
             "| LOIO acc (cluster) | ROBUST | STABLE-MID | HIGH-VAR | DEAD |")
    L.append("|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for lab in cells:
        t, x = tiers[lab], taxa[lab]
        c = t["tier_counts"]
        scope = x.get("mode_filter") or (
            f"{x.get('mode')} (collected)" if x.get("mode") else "all modes")
        L.append(
            f"| `{lab}` | {x.get('source', '?')} | {scope} | {t['meta']['n_folds']} "
            f"| {x['technique_level']['n_classes']} "
            f"| {x['technique_level']['loio_accuracy_mean']:.3f} "
            f"| {x['cluster_level']['loio_accuracy_mean']:.3f} "
            f"| {c.get('ROBUST', 0)} | {c.get('STABLE-MID', 0)} "
            f"| {c.get('HIGH-VAR', 0)} | {c.get('DEAD', 0)} |")
    L.append("")

    # ─── headline per-class table ───────────────────────────────────────
    hl = tiers[args.headline]
    L.append(f"## `{args.headline}` — per-class tiers\n")
    L.append("`min` is what sets the tier. `scored on` is *cluster* where the "
             "class is telemetry-indistinguishable from a sibling, because the "
             "cluster is the label the system actually emits.\n")
    L.append("| Class | Tier | Scored on | min F1 | mean F1 | max F1 | Fold F1s |")
    L.append("|---|---|---|--:|--:|--:|---|")
    order = {"ROBUST": 0, "STABLE-MID": 1, "HIGH-VAR": 2, "DEAD": 3}
    rows = sorted(hl["classes"].items(),
                  key=lambda kv: (order[kv[1]["tier"]], -kv[1]["f1_min"]))
    for cls, v in rows:
        folds = v["f1_folds_cluster"] if v["scored_on"] == "cluster" else v["f1_folds_technique"]
        L.append(f"| `{cls}` | {v['tier']} | {v['scored_on']} | {v['f1_min']:.3f} "
                 f"| {v['f1_mean']:.3f} | {v['f1_max']:.3f} | "
                 f"{', '.join(f'{f:.2f}' for f in folds)} |")
    L.append("")

    # ─── AC2 near-bar designee ──────────────────────────────────────────
    L.append("## `AC2` — the near-bar class\n")
    nb = near_bar(hl)
    if nb is None:
        L.append("Every surviving class already clears the bar — no near-bar "
                 "designee exists to name.\n")
    else:
        cls, f1 = nb
        v = hl["classes"][cls]
        L.append(f"**`{cls}`** — min F1 **{f1:.4f}** against the 0.85 bar "
                 f"(short by {ROBUST_BAR - f1:.4f}), tier `{v['tier']}`, scored on "
                 f"{v['scored_on']}. Fold minima: "
                 f"{', '.join(f'{x:.3f}' for x in (v['f1_folds_cluster'] if v['scored_on'] == 'cluster' else v['f1_folds_technique']))}.\n")

    # ─── cross-cell min-F1 deltas ───────────────────────────────────────
    L.append("## Per-class `min` F1 across cells\n")
    L.append("A class that rises between two cells rose because of the one thing "
             "that differs between them.\n")
    all_cls = sorted({c for t in tiers.values() for c in t["classes"]})
    L.append("| Class | " + " | ".join(f"`{lab}`" for lab in cells) + " |")
    L.append("|---|" + "--:|" * len(cells))
    for cls in all_cls:
        cvals = []
        for lab in cells:
            v = tiers[lab]["classes"].get(cls)
            cvals.append(f"{v['f1_min']:.3f}" if v else "—")
        L.append(f"| `{cls}` | " + " | ".join(cvals) + " |")
    L.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
