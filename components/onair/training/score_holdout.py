#!/usr/bin/env python3
"""AINOS3-101 — score a trained classifier against a fold it never saw.

The LOIO run answers "does this generalise to another *run*". This answers the
different and harder question: "does it generalise to another *flight mode*".
The rebuild corpus is SUNSAFE-deep (5 instances) and INERTIAL-shallow (1), so
INERTIAL cannot be a LOIO fold — but it is a clean held-out test set for a model
trained only on SUNSAFE, and that number belongs in the tier discussion because
it bounds what the tiers mean off the mode they were measured on.

Usage:
    python3 components/onair/training/score_holdout.py \\
        --model data/onair/models/rebuild29/sunsafe_5fold/classifier.pkl \\
        --fold data/onair/models/rebuild29/sunsafe_5fold/cache/INERTIAL_i1.npz \\
        --out data/onair/models/rebuild29/sunsafe_5fold/holdout_inertial.json
"""
from __future__ import annotations

import argparse
import json
import os
import pickle

import numpy as np
from sklearn.metrics import accuracy_score, f1_score


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True)
    p.add_argument("--fold", required=True)
    p.add_argument("--taxonomy", default="",
                   help="cluster_taxonomy.json — also score at cluster granularity, "
                        "the level the system actually reports")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    with open(args.model, "rb") as f:
        m = pickle.load(f)
    clf, schema = m["clf"], m["schema"]

    # A fold is `<name>_X.npy` (memory-mapped) plus `<name>_meta.npz` beside it.
    X = np.load(args.fold, mmap_mode="r")
    y = np.load(args.fold[:-6] + "_meta.npz", allow_pickle=True)["y"].astype(str)
    if X.shape[1] != len(schema["feature_names"]):
        raise SystemExit(f"feature mismatch: fold {X.shape[1]} vs model "
                         f"{len(schema['feature_names'])} — the fold cache must be "
                         f"built against the model's schema")

    # predict in blocks: the held-out fold is ~80k x 1768 and materialising it as
    # float64 in one go is exactly the allocation this environment reaps.
    ypred = np.concatenate([
        clf.predict(np.asarray(X[i:i + 20000], dtype=np.float64))
        for i in range(0, X.shape[0], 20000)])
    labels = sorted(set(y.tolist()) | set(map(str, clf.classes_)))
    per = dict(zip(labels, f1_score(y, ypred, labels=labels, average=None,
                                    zero_division=0)))
    doc = {
        "source_ticket": "AINOS3-101",
        "model": os.path.basename(args.model),
        "fold": os.path.basename(args.fold),
        "n_frames": int(len(y)),
        "accuracy": round(float(accuracy_score(y, ypred)), 4),
        "macro_f1": round(float(f1_score(y, ypred, labels=labels, average="macro",
                                         zero_division=0)), 4),
        "support": {c: int((y == c).sum()) for c in labels},
        "f1": {c: round(float(v), 4) for c, v in per.items()},
    }

    if args.taxonomy:
        clusters = json.load(open(args.taxonomy))["clusters"]
        rep = {mem: r for r, members in clusters.items() for mem in members}
        yt = np.array([rep.get(v, v) for v in y])
        yp = np.array([rep.get(v, v) for v in ypred])
        cl = sorted(set(yt.tolist()) | set(yp.tolist()))
        doc["cluster_accuracy"] = round(float(accuracy_score(yt, yp)), 4)
        doc["cluster_macro_f1"] = round(float(f1_score(yt, yp, labels=cl,
                                                       average="macro",
                                                       zero_division=0)), 4)
        doc["cluster_f1"] = {c: round(float(v), 4) for c, v in zip(
            cl, f1_score(yt, yp, labels=cl, average=None, zero_division=0))}

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(doc, open(args.out, "w"), indent=2)

    print(f"{doc['fold']} vs {doc['model']}: {doc['n_frames']} frames  "
          f"acc={doc['accuracy']:.4f}  macro-F1={doc['macro_f1']:.4f}")
    if args.taxonomy:
        print(f"  cluster-level: acc={doc['cluster_accuracy']:.4f}  "
              f"macro-F1={doc['cluster_macro_f1']:.4f}")
    w = max(len(c) for c in doc["f1"])
    print(f"\n{'class':<{w}}  {'support':>8}{'F1':>8}")
    for c, v in sorted(doc["f1"].items(), key=lambda kv: -kv[1]):
        print(f"{c:<{w}}  {doc['support'][c]:>8}{v:>8.3f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
