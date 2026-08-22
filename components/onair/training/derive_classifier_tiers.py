#!/usr/bin/env python3
"""Derive the classifier confidence tiers from LOIO folds — the artifact that
replaces the hand-maintained tier constants in app/gen_nos3_coverage.py.

WHY THIS EXISTS
---------------
`V5_DETECTOR_COVERAGE.md` §4 published four tiers and stated one rule:
"ROBUST ... F1 >= 0.85 on every split". A 2026-08-20 audit found that **none of
the four techniques listed as ROBUST met that rule** — DE-0003.01 averaged 0.03
F1 while being published as "trust the label" — and that the rules for the other
three tiers were never written down anywhere. The tier column was a set of
hardcoded strings whose derivation no one could reproduce.

This script makes the tier column derived, reproducible, and self-documenting:
the rule lives here, the inputs are a LOIO prediction cache, and the output
records both so any published tier can be traced back.

THE RULE
--------
Two things decide how much an operator should trust a label: how HIGH the F1 is,
and how CONSISTENT it is across runs the model never saw. The published tier
prose already implies both, so the rule uses `min` and `max` across folds rather
than the mean — a mean hides the "works on run A, fails on run B" case that the
HIGH-VARIANCE tier exists to name.

    ROBUST      min F1 >= 0.85          "trust the label" — reliable on EVERY run
    STABLE-MID  min F1 >= 0.50          "good as a top-3 suggestion" — usable on
                                        every run, not authoritative
    HIGH-VAR    max F1 >= 0.25          "a hint, not a verdict" — works on some
                                        runs and not others
    DEAD        max F1 <  0.25          "cannot be labeled as-is" — no run
                                        produces a usable label

Checked in that order; first match wins. The 0.85 bar is inherited unchanged from
the published doc — deliberately NOT relaxed to make the tier non-empty, because
moving a threshold to fit the result is how the original claim became unsupported.

SCORED AT THE LEVEL WE ACTUALLY REPORT
--------------------------------------
Telemetry-indistinguishable techniques are reported as a CLUSTER, not a
sub-technique (§B.1), so they are tiered on their cluster's F1. Scoring
EX-0012.04 at its technique F1 (0.01) would publish a tier for a label the system
never claims to emit; its cluster scores 0.45. Single-member clusters are
unaffected — cluster F1 == technique F1 by construction.

Usage:
    python3 derive_classifier_tiers.py \\
        --cache data/onair/models/cluster_rescore/loio_predictions_oof_v3hybrid_full.npz \\
        --taxonomy data/onair/models/cluster_rescore/cluster_taxonomy.json \\
        --out data/onair/models/classifier_tiers.json
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from sklearn.metrics import f1_score

# (tier, predicate on the per-fold F1 list) — checked in order, first match wins.
TIER_RULE = [
    ("ROBUST",     lambda f: min(f) >= 0.85),
    ("STABLE-MID", lambda f: min(f) >= 0.50),
    ("HIGH-VAR",   lambda f: max(f) >= 0.25),
    ("DEAD",       lambda f: True),
]
RULE_TEXT = {
    "ROBUST": "min F1 >= 0.85 across all LOIO folds — trust the label",
    "STABLE-MID": "min F1 >= 0.50 — usable on every run, good as a top-3 suggestion",
    "HIGH-VAR": "max F1 >= 0.25 but min < 0.50 — correct on some runs, not others",
    "DEAD": "max F1 < 0.25 — no fold produces a usable label",
}


def tier_of(folds: list[float]) -> str:
    for name, pred in TIER_RULE:
        if pred(folds):
            return name
    return "DEAD"


def per_fold_f1(y_true, y_pred, fold_of_row, cls) -> list[float]:
    return [float(f1_score(y_true[fold_of_row == h] == cls,
                           y_pred[fold_of_row == h] == cls, zero_division=0))
            for h in sorted(set(fold_of_row.tolist()))]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", required=True,
                   help="LOIO npz with y_true/y_pred/fold_of_row (export_hybrid_oof.py "
                        "for the deployed hybrid; eval_classifier_clusters.py for a "
                        "global-only model)")
    p.add_argument("--taxonomy", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--label", default=None,
                   help="model label recorded in meta (default: from the cache's "
                        "provenance_classifier field)")
    args = p.parse_args()

    z = np.load(args.cache, allow_pickle=True)
    for k in ("y_true", "y_pred", "fold_of_row"):
        if k not in z.files:
            raise SystemExit(
                f"{args.cache} lacks '{k}'. A predictions-only cache cannot be "
                f"tiered — re-export with export_hybrid_oof.py, which persists "
                f"ground truth and fold assignment alongside the predictions.")
    y_true, y_pred, fold = z["y_true"], z["y_pred"], z["fold_of_row"]

    tax = json.load(open(args.taxonomy))
    clusters = tax["clusters"]
    cluster_of = {m: rep for rep, members in clusters.items() for m in members}
    yt_c = np.array([cluster_of.get(v, v) for v in y_true])
    yp_c = np.array([cluster_of.get(v, v) for v in y_pred])

    n_folds = len(set(fold.tolist()))
    cluster_cache: dict[str, list[float]] = {}
    out = {}
    for cls in sorted(set(y_true.tolist())):
        rep = cluster_of.get(cls, cls)
        members = clusters.get(rep, [rep])
        tech_f1 = per_fold_f1(y_true, y_pred, fold, cls)
        if rep not in cluster_cache:
            cluster_cache[rep] = per_fold_f1(yt_c, yp_c, fold, rep)
        clu_f1 = cluster_cache[rep]
        scored = clu_f1 if len(members) > 1 else tech_f1
        out[cls] = {
            "tier": tier_of(scored),
            "cluster": rep,
            "cluster_is_multi": len(members) > 1,
            "scored_on": "cluster" if len(members) > 1 else "technique",
            "f1_folds_technique": [round(v, 4) for v in tech_f1],
            "f1_folds_cluster": [round(v, 4) for v in clu_f1],
            "f1_min": round(min(scored), 4),
            "f1_mean": round(float(np.mean(scored)), 4),
            "f1_max": round(max(scored), 4),
        }

    counts: dict[str, int] = {}
    for v in out.values():
        counts[v["tier"]] = counts.get(v["tier"], 0) + 1

    doc = {
        "meta": {
            "model": (args.label
                      or (str(z["provenance_model"]) if "provenance_model" in z.files
                          else None)
                      or "UNRECORDED — cache carries no model provenance"),
            "cache": os.path.basename(args.cache),
            "taxonomy": os.path.basename(args.taxonomy),
            "n_folds": n_folds,
            "evaluation": "leave-one-instance-out (LOIO); every fold's predictions "
                          "come from a model that never saw that spacecraft run",
            "provenance": "OOF",
            "rule": RULE_TEXT,
            "rule_order": [t for t, _ in TIER_RULE],
            "scored_at": "cluster F1 for telemetry-indistinguishable multi-member "
                         "clusters (that is the label the system emits), technique "
                         "F1 otherwise",
            "note": "The ROBUST bar of 0.85 is inherited verbatim from the "
                    "V5_DETECTOR_COVERAGE.md §4 text. It is deliberately not "
                    "relaxed to populate the tier.",
        },
        "tier_counts": counts,
        "classes": out,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"tier counts: {counts}\n")
    w = max(len(c) for c in out)
    print(f"{'class':<{w}}  {'tier':<11}{'on':<10}{'min':>6}{'mean':>7}{'max':>6}")
    print("-" * (w + 42))
    order = {t: i for i, (t, _) in enumerate(TIER_RULE)}
    for cls, v in sorted(out.items(), key=lambda kv: (order[kv[1]["tier"]], -kv[1]["f1_min"])):
        print(f"{cls:<{w}}  {v['tier']:<11}{v['scored_on']:<10}"
              f"{v['f1_min']:>6.2f}{v['f1_mean']:>7.2f}{v['f1_max']:>6.2f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
