#!/usr/bin/env python3
"""AINOS3-101 `AC1` — measure *footprint reproducibility* directly, so the answer
to "why is ROBUST out of reach" is evidence rather than inference.

THE CLAIM UNDER TEST
--------------------
`AINOS3-99` concluded that the per-instance F1 spread is a **generalisation
limit** — a class's telemetry footprint varies from run to run — and not a
sample-size or blind-window artifact. The tier rule takes the `min` across LOIO
folds, so a class whose footprint is not reproducible is structurally barred from
`ROBUST` no matter how much data is collected.

That is a claim about the *data*, and it can be measured without any model.

WHAT THIS MEASURES
------------------
For each class `c` and each instance `i`, take the class's frames and that
instance's own nominal frames, and ask which features the attack actually moved:

    disp[c,i]  = median(X_c,i) - median(X_nom,i)
    scale[i]   = 1.4826 * MAD(X_nom,i)          # that run's own noise band
    moved[c,i] = { (feature, sign(disp)) : |disp| > MOVE_SIGMA * scale }

`moved[c,i]` is the class's **footprint as that run expressed it** — a signed set
of features, scale-free by construction. Reproducibility is then how much two
runs agree on it:

    R[c] = mean_{i<j} Jaccard(moved[c,i], moved[c,j])

R = 1 means every run moved the same features in the same direction, and a model
that learns that on four runs will find it on the fifth. R near 0 means the runs
disagree about what the attack looks like — and the fold that disagrees most sets
the `min`, and therefore the tier.

⚠ **Everything here is median/MAD, not mean/std, and that is not fastidiousness.**
`ADCS_GNC.DT` reads 1.5e284 in 6 frames of 413,472 (one instance-4 run; normal
value 0.1). Six frames in 10⁻⁵ of the corpus are enough to make a nominal
variance infinite, which silently zeroes every z-score in that fold and would have
reported the affected class as irreproducible. A rank statistic does not notice.

A secondary cosine on clipped robust z-scores is reported alongside; it weights
by how far each feature moved rather than only whether it moved. Both are on the
same medians. Where they disagree, the Jaccard is the one tied to the tier claim.

Usage:
    python3 components/onair/training/footprint_reproducibility.py \\
        --cache-dir data/onair/models/rebuild29/sunsafe_5fold/cache \\
        --tiers data/onair/models/rebuild29/sunsafe_5fold/classifier_tiers.json \\
        --out data/onair/models/rebuild29/sunsafe_5fold/footprint_reproducibility.json
"""
from __future__ import annotations

import argparse
import glob
import itertools
import json
import os

import numpy as np

EPS = 1e-12
MAD_TO_SIGMA = 1.4826    # MAD -> gaussian-equivalent sigma
MOVE_SIGMA = 3.0         # a feature "moved" at 3 robust sigma from nominal
Z_CLIP = 50.0            # cap the secondary cosine's z so one axis cannot own it
MIN_FRAMES = 20          # a centroid over fewer frames is noise, not a footprint


def _robust_center_scale(A: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    med = np.median(A, axis=0)
    mad = np.median(np.abs(A - med), axis=0)
    return med, MAD_TO_SIGMA * mad


def fold_signatures(path: str, min_frames: int, mode_filter: str | None = None):
    """→ ({class: (moved_set, clipped_z)}, n_frames per class).

    `path` is a fold's `<name>_X.npy`; its labels and metadata live alongside in
    `<name>_meta.npz`. X is memory-mapped — the medians below are the only thing
    needed from it, and this environment reaps processes that grow large.
    """
    X = np.load(path, mmap_mode="r")
    z = np.load(path[:-6] + "_meta.npz", allow_pickle=True)
    y = z["y"].astype(str)
    if mode_filter:
        keep = (z["meta_adcs_mode"].astype(str) == mode_filter)
        X, y = X[keep], y[keep]
    nom = (y == "nominal")
    if nom.sum() < min_frames:
        raise SystemExit(f"{path}: only {nom.sum()} nominal frames")
    med_n, scale_n = _robust_center_scale(X[nom])
    # A feature that never moves in nominal has scale 0: any displacement at all
    # is then outside its noise band, which is the correct reading — those are
    # exactly the static-in-nominal counters the rule gate keys on.
    thresh = MOVE_SIGMA * scale_n
    sigs, counts = {}, {}
    for cls in sorted(set(y.tolist())):
        if cls == "nominal":
            continue
        m = (y == cls)
        if m.sum() < min_frames:
            continue
        disp = np.median(X[m], axis=0) - med_n
        moved = np.abs(disp) > np.maximum(thresh, EPS)
        idx = np.flatnonzero(moved)
        sigs[cls] = (
            frozenset(zip(idx.tolist(), np.sign(disp[idx]).astype(int).tolist())),
            np.clip(disp / (scale_n + EPS), -Z_CLIP, Z_CLIP),
        )
        counts[cls] = int(m.sum())
    return sigs, counts


def jaccard(a: frozenset, b: frozenset) -> float:
    u = len(a | b)
    return len(a & b) / u if u else 1.0


def cos(a, b) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > EPS and nb > EPS else 0.0


def spearman(a: list[float], b: list[float]) -> float:
    """Rank correlation without pulling in scipy (average ranks for ties)."""
    def ranks(v):
        order = np.argsort(np.asarray(v, dtype=float))
        r = np.empty(len(v), dtype=float)
        r[order] = np.arange(len(v), dtype=float)
        # average ties
        arr = np.asarray(v, dtype=float)
        for val in np.unique(arr):
            m = arr == val
            if m.sum() > 1:
                r[m] = r[m].mean()
        return r
    ra, rb = ranks(a), ranks(b)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    d = np.linalg.norm(ra) * np.linalg.norm(rb)
    return float(ra @ rb / d) if d > EPS else 0.0


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache-dir", required=True)
    p.add_argument("--tiers", default="", help="classifier_tiers.json to correlate against")
    p.add_argument("--min-frames", type=int, default=MIN_FRAMES)
    p.add_argument("--mode-filter", default="",
                   help="restrict to one __adcs_mode, to match a mode-scoped cell")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    paths = sorted(glob.glob(os.path.join(args.cache_dir, "*_X.npy")))
    if len(paths) < 2:
        raise SystemExit(f"need >= 2 fold caches in {args.cache_dir}")
    print(f"{len(paths)} instances: {[os.path.basename(p) for p in paths]}")

    per_fold, per_counts = [], []
    for path in paths:
        s, c = fold_signatures(path, args.min_frames, args.mode_filter or None)
        per_fold.append(s)
        per_counts.append(c)
        print(f"  {os.path.basename(path)}: {len(s)} classes with "
              f">= {args.min_frames} frames")

    classes = sorted(set().union(*[set(s) for s in per_fold]))
    tiers = json.load(open(args.tiers))["classes"] if args.tiers else {}

    rows = []
    for cls in classes:
        present = [i for i, s in enumerate(per_fold) if cls in s]
        if len(present) < 2:
            continue
        pairs = list(itertools.combinations(present, 2))
        jac = [jaccard(per_fold[i][cls][0], per_fold[j][cls][0]) for i, j in pairs]
        csim = [cos(per_fold[i][cls][1], per_fold[j][cls][1]) for i, j in pairs]
        t = tiers.get(cls, {})
        rows.append({
            "class": cls,
            "instances": len(present),
            "frames_per_instance": [per_counts[i].get(cls, 0) for i in present],
            "features_moved_per_instance": [len(per_fold[i][cls][0]) for i in present],
            "reproducibility_mean": round(float(np.mean(jac)), 4),
            "reproducibility_min": round(float(np.min(jac)), 4),
            "reproducibility_max": round(float(np.max(jac)), 4),
            "cosine_mean": round(float(np.mean(csim)), 4),
            "f1_min": t.get("f1_min"),
            "f1_mean": t.get("f1_mean"),
            "tier": t.get("tier"),
        })

    scored = [r for r in rows if r["f1_min"] is not None]
    rho = (spearman([r["reproducibility_mean"] for r in scored],
                    [r["f1_min"] for r in scored]) if len(scored) >= 3 else None)
    rho_cos = (spearman([r["cosine_mean"] for r in scored],
                        [r["f1_min"] for r in scored]) if len(scored) >= 3 else None)

    doc = {
        "source_ticket": "AINOS3-101",
        "measure": "mean pairwise Jaccard overlap of the per-instance SIGNED set of "
                   "features displaced > 3 robust sigma from that instance's own "
                   "nominal median; secondary = cosine of clipped robust z-scores",
        "robust_statistics": "median / 1.4826*MAD — a single 1.5e284 glitch frame in "
                             "ADCS_GNC.DT makes mean/std unusable on this corpus",
        "move_sigma": MOVE_SIGMA,
        "z_clip": Z_CLIP,
        "cache_dir": args.cache_dir,
        "mode_filter": args.mode_filter or None,
        "n_instances": len(paths),
        "min_frames": args.min_frames,
        "spearman_reproducibility_vs_f1_min": (round(rho, 4) if rho is not None else None),
        "spearman_cosine_vs_f1_min": (round(rho_cos, 4) if rho_cos is not None else None),
        "classes": sorted(rows, key=lambda r: -r["reproducibility_mean"]),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(doc, open(args.out, "w"), indent=2)

    w = max(len(r["class"]) for r in rows)
    print(f"\n{'class':<{w}}  {'R jac':>7}{'R min':>7}{'cos':>7}{'moved':>8}{'F1 min':>8}  tier")
    print("-" * (w + 46))
    for r in doc["classes"]:
        f1 = f"{r['f1_min']:.3f}" if r["f1_min"] is not None else "  —  "
        mv = int(np.median(r["features_moved_per_instance"]))
        print(f"{r['class']:<{w}}  {r['reproducibility_mean']:>7.3f}"
              f"{r['reproducibility_min']:>7.3f}{r['cosine_mean']:>7.3f}{mv:>8}"
              f"{f1:>8}  {r['tier'] or ''}")
    if rho is not None:
        print(f"\nSpearman(jaccard, min F1)  = {rho:+.3f} over {len(scored)} classes")
        print(f"Spearman(cosine,  min F1)  = {rho_cos:+.3f}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
