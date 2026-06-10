#!/usr/bin/env python3
"""Sweep the cluster threshold (tau) over cached LOIO predictions — no retrain.

eval_classifier_clusters.py persists per-fold (y_true, y_pred) to
`loio_predictions.npz`. Re-deriving clusters + re-scoring at cluster
granularity is pure relabeling, so this runs in milliseconds and lets us pick
a defensible tau without paying the ~80-min LOIO retrain each time.

Usage:
    python3 components/onair/training/recluster_from_cache.py \\
        --cache data/onair/models/cluster_rescore/loio_predictions.npz \\
        --taus 0.15,0.20,0.25,0.30 \\
        [--write-taxonomy 0.20]   # re-emit cluster_taxonomy.json at this tau
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from eval_classifier_clusters import (  # noqa: E402
    derive_clusters, map_to_cluster, DOMAIN_IDENTICAL_PAIRS)


def score(y_true, y_pred, fold_of_row, labels, tau):
    from sklearn.metrics import accuracy_score, f1_score
    conf_counts: dict = defaultdict(int)
    for t, p in zip(y_true, y_pred):
        conf_counts[(t, p)] += 1
    clusters, edges = derive_clusters(conf_counts, list(labels), tau)
    multi = {r: m for r, m in clusters.items() if len(m) > 1}

    folds = sorted(set(fold_of_row.tolist()))
    tech_acc, clu_acc = [], []
    for f in folds:
        m = fold_of_row == f
        tech_acc.append(accuracy_score(y_true[m], y_pred[m]))
        ct = map_to_cluster(y_true[m], clusters)
        cp = map_to_cluster(y_pred[m], clusters)
        clu_acc.append(accuracy_score(ct, cp))
    clu_labels = sorted(set(map_to_cluster(y_true, clusters).tolist()))
    tech_f1 = f1_score(y_true, y_pred, labels=list(labels), average="macro",
                       zero_division=0)
    ct_all = map_to_cluster(y_true, clusters)
    cp_all = map_to_cluster(y_pred, clusters)
    clu_f1 = f1_score(ct_all, cp_all, labels=clu_labels, average="macro",
                      zero_division=0)
    return {
        "tau": tau,
        "n_clusters": len(clusters),
        "n_multi": len(multi),
        "multi": {r: m for r, m in sorted(multi.items())},
        "tech_acc": float(np.mean(tech_acc)),
        "clu_acc": float(np.mean(clu_acc)),
        "acc_lift": float(np.mean(clu_acc) - np.mean(tech_acc)),
        "tech_macro_f1": float(tech_f1),
        "clu_macro_f1": float(clu_f1),
        "clusters": {r: m for r, m in sorted(clusters.items())},
        "edges": edges,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache",
                   default="data/onair/models/cluster_rescore/loio_predictions.npz")
    p.add_argument("--taus", default="0.15,0.20,0.25,0.30")
    p.add_argument("--write-taxonomy", type=float, default=None,
                   help="re-emit cluster_taxonomy.json at this tau")
    p.add_argument("--out-dir", default="data/onair/models/cluster_rescore")
    args = p.parse_args()

    z = np.load(args.cache, allow_pickle=True)
    y_true, y_pred = z["y_true"], z["y_pred"]
    fold_of_row, labels = z["fold_of_row"], z["labels"]
    print(f"cache: {len(y_true)} predictions, {len(set(labels))} labels, "
          f"{len(set(fold_of_row.tolist()))} folds\n")

    taus = [float(s) for s in args.taus.split(",")]
    print(f"{'tau':>5} {'clusters':>8} {'multi':>5} {'tech_acc':>9} "
          f"{'clu_acc':>8} {'lift':>7} {'tech_F1':>8} {'clu_F1':>7}")
    print("-" * 64)
    results = []
    for tau in taus:
        r = score(y_true, y_pred, fold_of_row, labels, tau)
        results.append(r)
        print(f"{tau:>5.2f} {r['n_clusters']:>8} {r['n_multi']:>5} "
              f"{r['tech_acc']:>9.4f} {r['clu_acc']:>8.4f} "
              f"{r['acc_lift']:>+7.4f} {r['tech_macro_f1']:>8.4f} "
              f"{r['clu_macro_f1']:>7.4f}")
    print()
    for r in results:
        if r["multi"]:
            print(f"tau={r['tau']:.2f} multi-member clusters:")
            for rep, mem in r["multi"].items():
                print(f"    {rep}: {mem}")

    if args.write_taxonomy is not None:
        r = score(y_true, y_pred, fold_of_row, labels, args.write_taxonomy)
        out = os.path.join(args.out_dir, "cluster_taxonomy.json")
        existing = {}
        if os.path.exists(out):
            existing = json.load(open(out))
        existing["tau"] = args.write_taxonomy
        existing["clusters"] = r["clusters"]
        existing["multi_member_clusters"] = r["multi"]
        existing["technique_level"] = {
            **existing.get("technique_level", {}),
            "loio_accuracy_mean": round(r["tech_acc"], 4),
            "macro_f1": round(r["tech_macro_f1"], 4),
        }
        existing["cluster_level"] = {
            **existing.get("cluster_level", {}),
            "loio_accuracy_mean": round(r["clu_acc"], 4),
            "macro_f1": round(r["clu_macro_f1"], 4),
            "n_clusters": r["n_clusters"],
            "accuracy_lift": round(r["acc_lift"], 4),
        }
        with open(out, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"\nrewrote {out} at tau={args.write_taxonomy}")


if __name__ == "__main__":
    main()
