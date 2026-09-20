#!/usr/bin/env python3
"""Does de-interleaving help the Isolation Forest? A like-for-like A/B.

WHY THE IF AND NOT JUST THE CLASSIFIER
--------------------------------------
The blended classifier run moved macro-F1 +0.034 but left top-1 accuracy flat.
The IF is the more interesting test, for a specific reason: it is the
**delta-driven** detector, and de-interleaving removes 4-6x of noise from
exactly the delta features it scores on. `AINOS3-121` found the deployed IF
misses every single-subsystem spoof because its 1 %-FP threshold sits in the low
tail of a concentrated nominal distribution — if that distribution is wide
*because of the double buffer* rather than because of the spacecraft, blending
should tighten it and buy back sensitivity.

THE COMPARISON
--------------
Train on instances 1-4 NOMINAL frames, hold out instance 5. Identical
hyper-parameters to `train.py` (200 trees, contamination 0.01, seed 42) and the
identical feature recipe, since both variants reuse the fold caches the
classifier runs already built — the ONLY difference is interleaved vs blended.

Two readings, because the first one alone can mislead:

  * **native threshold** — each model's own `score < 0` boundary. Shows what you
    would actually get, but confounds sensitivity with calibration.
  * **matched FP** — threshold set at the 1st percentile of the held-out NOMINAL
    scores, so both models are pinned to the same 1 % false-alarm budget and the
    attack recall is directly comparable. This is the number that answers the
    question.

Usage:
    python3 components/onair/training/compare_if_blended.py \\
        --out data/onair/models/rebuild29/if_blended_ab.json
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
from sklearn.ensemble import IsolationForest

VARIANTS = {
    "interleaved": "data/onair/models/rebuild29/sunsafe_5fold/cache",
    "blended": "data/onair/models/rebuild29/sunsafe_5fold_blended/cache",
}
TRAIN_INSTANCES = (1, 2, 3, 4)
HELDOUT = 5


def fold(cache_dir: str, inst: int):
    X = np.load(os.path.join(cache_dir, f"SUNSAFE_i{inst}_X.npy"), mmap_mode="r")
    y = np.load(os.path.join(cache_dir, f"SUNSAFE_i{inst}_meta.npz"),
                allow_pickle=True)["y"].astype(str)
    return X, y


def run(name: str, cache_dir: str, n_estimators: int, contamination: float):
    # Train on NOMINAL only — the IF learns what normal looks like.
    parts = []
    for i in TRAIN_INSTANCES:
        X, y = fold(cache_dir, i)
        parts.append(np.asarray(X[y == "nominal"], dtype=np.float64))
    Xtr = np.vstack(parts)
    del parts

    clf = IsolationForest(n_estimators=n_estimators, contamination=contamination,
                          random_state=42, n_jobs=-1)
    clf.fit(Xtr)
    del Xtr

    Xte, yte = fold(cache_dir, HELDOUT)
    nom = yte == "nominal"
    s_nom = clf.decision_function(np.asarray(Xte[nom], dtype=np.float64))
    s_atk = clf.decision_function(np.asarray(Xte[~nom], dtype=np.float64))

    # native: the model's own boundary
    fp_native = float((s_nom < 0).mean())
    rec_native = float((s_atk < 0).mean())
    # matched: pin both models to the same 1 % nominal false-alarm budget
    thr = float(np.percentile(s_nom, 1.0))
    rec_matched = float((s_atk < thr).mean())

    atk = yte[~nom]
    per_class = {}
    for c in sorted(set(atk.tolist())):
        m = atk == c
        per_class[c] = round(float((s_atk[m] < thr).mean()), 4)

    return {
        "variant": name,
        "train_nominal_frames": int(sum((fold(cache_dir, i)[1] == "nominal").sum()
                                        for i in TRAIN_INSTANCES)),
        "heldout_nominal": int(nom.sum()),
        "heldout_attack": int((~nom).sum()),
        "fp_native": round(fp_native, 4),
        "recall_native": round(rec_native, 4),
        "threshold_matched_1pct": round(thr, 6),
        "recall_at_1pct_fp": round(rec_matched, 4),
        "nominal_score_p1": round(float(np.percentile(s_nom, 1)), 6),
        "nominal_score_p50": round(float(np.percentile(s_nom, 50)), 6),
        "nominal_score_std": round(float(s_nom.std()), 6),
        "per_class_recall_at_1pct_fp": per_class,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n-estimators", type=int, default=200)
    p.add_argument("--contamination", type=float, default=0.01)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    results = {}
    if os.path.exists(args.out):          # resumable: this box kills long jobs
        results = json.load(open(args.out))
    for name, d in VARIANTS.items():
        if name in results:
            print(f"[cached] {name}")
            continue
        if not os.path.isdir(d):
            print(f"skip {name}: no cache at {d}")
            continue
        print(f"training IF on {name}…", flush=True)
        results[name] = run(name, d, args.n_estimators, args.contamination)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(results, open(args.out, "w"), indent=1)
        print(f"  done: {results[name]['recall_at_1pct_fp']:.4f} recall @1% FP",
              flush=True)

    if len(results) == 2:
        a, b = results["interleaved"], results["blended"]
        print(f"\n{'metric':<34}{'interleaved':>13}{'blended':>11}{'Δ':>9}")
        print("-" * 67)
        for k, lab in [("fp_native", "FP @ native threshold"),
                       ("recall_native", "attack recall @ native"),
                       ("recall_at_1pct_fp", "attack recall @ 1% FP"),
                       ("nominal_score_std", "nominal score std (spread)"),
                       ("nominal_score_p1", "nominal p1"),
                       ("nominal_score_p50", "nominal p50")]:
            print(f"{lab:<34}{a[k]:>13.4f}{b[k]:>11.4f}{b[k]-a[k]:>+9.4f}")
        print(f"\n{'class':<14}{'interleaved':>13}{'blended':>11}{'Δ':>9}")
        print("-" * 47)
        pa, pb = a["per_class_recall_at_1pct_fp"], b["per_class_recall_at_1pct_fp"]
        for c in sorted(set(pa) | set(pb), key=lambda c: -(pb.get(c, 0) - pa.get(c, 0))):
            print(f"{c:<14}{pa.get(c, 0):>13.3f}{pb.get(c, 0):>11.3f}"
                  f"{pb.get(c, 0)-pa.get(c, 0):>+9.3f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
