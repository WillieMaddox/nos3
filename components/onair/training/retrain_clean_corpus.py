#!/usr/bin/env python3
"""AINOS3-101 — retrain the attack classifier on the clean corpus and re-derive
the confidence tiers, with the mode-scope control that makes the comparison honest.

WHY THIS EXISTS (and why it is not `eval_classifier_clusters.py`)
-----------------------------------------------------------------
`eval_classifier_clusters.py` discovers its LOIO instances by a *time-gap
heuristic* over three hardcoded 2026-05 session dates (`V3_DATES`). That was the
only instance identity the v3 corpus ever had. The `AINOS3-100` rebuild records
`(technique, mode, instance)` explicitly per run in `corpus_manifest.json`, so
fold membership is now *declared*, not inferred — and the heuristic cannot
express the new corpus at all (5 instances, two modes, one collection window).

This script therefore keeps every *rule* from the v3 evaluation (the 894-recipe
hyper-parameters, the `tau` cluster rule, the label-set restriction, the
`min`-over-folds tier bar) and replaces only the part that has to change: where
folds come from. Its `loio_predictions.npz` is byte-compatible with
`derive_classifier_tiers.py` and `recluster_from_cache.py`.

THE THREE CONFOUNDS (`AC3`)
---------------------------
A cleaner corpus that is also a *narrower* evaluation would make `ROBUST` look
reachable for the wrong reason. Three things differ between the v3 tier table and
a naive new-corpus run, and each is separately controllable here:

  1. data cleanliness  — v3stage (83 % of attack frames blind-windowed) vs rebuild
  2. mode scope        — v3stage spans 4 ADCS modes; the rebuild is SUNSAFE-deep
  3. fold count        — 3 instances vs 5 (`min` over 5 folds is a STRICTER bar)

`--source v3stage --mode-filter MODE_SUNSAFE --instances 1,2,3` holds (2) and (3)
fixed and moves only (1). `--source rebuild --instances 1,2,3` holds (1) and (2)
and moves only (3). Run all three and the deltas are attributable.

Usage:
    # headline — clean corpus, SUNSAFE, all 5 folds
    python3 components/onair/training/retrain_clean_corpus.py \\
        --source rebuild --mode SUNSAFE --instances 1,2,3,4,5 \\
        --out-dir data/onair/models/rebuild29/sunsafe_5fold

    # like-for-like control — same mode scope, same fold count, old data
    python3 components/onair/training/retrain_clean_corpus.py \\
        --source v3stage --mode-filter MODE_SUNSAFE \\
        --out-dir data/onair/models/rebuild29/control_v3stage_sunsafe
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time
from collections import defaultdict

import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(THIS_DIR)))

from features import V5_DELTA_ONLY_COLUMNS, build_features   # noqa: E402
from label_set import load_label_set, trained_classes    # noqa: E402
from loader import load_with_labels                      # noqa: E402
from eval_classifier_clusters import (                   # noqa: E402
    DOMAIN_IDENTICAL_PAIRS, derive_clusters, discover_instances,
    frame_labels, make_clf, map_to_cluster, per_class_f1,
)

SKIP_WARMUP_ROWS = 30       # inherited verbatim from the v3 evaluation
META_KEYS = ("file_id", "row_idx", "adcs_mode", "in_corruption", "attack_id")


# ───────────────────────── instance discovery ──────────────────────────

def rebuild_instances(corpus_dir: str, mode: str, instances: list[int]):
    """Fold membership straight off the AINOS3-100 corpus manifest.

    Returns [(name, csv_dir, [manifest_path, ...]), ...] in fold order. The
    per-instance symlink views are materialised on demand so `load_with_labels`
    reads only that fold's CSVs instead of the 2 600-file shared csv dir.
    """
    man = json.load(open(os.path.join(corpus_dir, "corpus_manifest.json")))
    by_inst = defaultdict(list)
    for r in man["runs"]:
        if r["mode"] == mode:
            by_inst[r["instance"]].append(r)

    views = os.path.join(corpus_dir, "views")
    out = []
    for inst in instances:
        runs = by_inst.get(inst)
        if not runs:
            raise SystemExit(f"no {mode} runs at instance {inst}")
        d = os.path.join(views, f"{mode}_i{inst}")
        os.makedirs(d, exist_ok=True)
        mans = []
        for r in runs:
            src = os.path.join(ROOT, "data/onair/csv", r["csv"])
            dst = os.path.join(d, r["csv"])
            if not os.path.islink(dst):
                os.symlink(src, dst)
            mans.append(os.path.join(ROOT, "data/onair/scenarios", r["manifest"]))
        out.append((f"{mode}_i{inst}", d, sorted(mans)))
    return out


def prebuilt_views(views_dir: str, mode: str, instances: list[int]):
    """Folds from an already-materialised views directory.

    Used for the blended corpus: `views_blended/<MODE>_i<N>` symlinks into
    `csv_blended/` instead of `csv/`, so the same LOIO runs against
    de-interleaved telemetry with nothing else changed.
    """
    out = []
    for inst in instances:
        name = f"{mode}_i{inst}"
        d = os.path.join(views_dir, name)
        mf = os.path.join(views_dir, f"{name}.manifests.json")
        if not os.path.isdir(d) or not os.path.exists(mf):
            raise SystemExit(f"no prebuilt view for {name} under {views_dir}")
        out.append((name, d, json.load(open(mf))))
    return out


def v3stage_instances(csv_dir: str, manifest_dir: str):
    """The v3 corpus's three instances, via the original time-gap heuristic."""
    insts = discover_instances(manifest_dir)
    if len(insts) < 2:
        raise SystemExit("need >= 2 instances for LOIO")
    return [(f"v3stage_i{i+1}", csv_dir, m) for i, m in enumerate(insts)]


# ─────────────────────────── load / featurize ──────────────────────────

def _align_to_schema(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Add any schema column absent from this fold as a zero column.

    A telemetry column can be entirely missing from one instance's CSVs (an app
    that never emitted during that session). Dropping the fold would be worse
    than imputing a constant: build_features would otherwise KeyError and the
    fold count — which sets the tier bar — would silently change.
    """
    want = list(schema.get("scalar_columns", [])) + list(schema.get("list_columns", {}))
    missing = [c for c in want if c not in df.columns]
    if missing:
        print(f"  schema columns absent from this fold, zero-filled: {len(missing)} "
              f"({missing[:4]}{'...' if len(missing) > 4 else ''})")
        for c in missing:
            df[c] = 0.0
    return df


def apply_mode_filter(X, y, meta, mode_filter: str | None):
    """The `AC3` mode-scope restriction, applied to an already-built fold.

    Deliberately NOT part of `load_fold`: the filter drops rows, and dropping
    rows before the delta pass would fabricate discontinuities. It also keeps the
    fold cache mode-agnostic, so the all-modes and SUNSAFE-only control runs
    featurize the corpus once between them.
    """
    if not mode_filter:
        return X, y, meta
    keep = (meta["adcs_mode"] == mode_filter)
    print(f"  mode filter {mode_filter}: kept {int(keep.sum())}/{len(keep)} rows")
    return X[keep], y[keep], {k: v[keep] for k, v in meta.items()}


def load_fold(csv_dir: str, manifests: list[str], schema: dict | None,
              allowed_labels: set[str], delta_only: list[str] | None = None):
    """One fold → (X, y, meta, schema).

    Label filtering happens AFTER build_features so deltas stay intact across the
    contiguous stream — the discipline the v3 evaluation used.

    ⚠ `delta_only` is not optional in spirit. v3's pickled schema carries the 22
    `V5_DELTA_ONLY_COLUMNS` — absolute time references and the deterministic NOS3
    orbit — whose RAW values are suppressed so the model cannot learn the sim's
    hard-coded epoch and TLE as a feature. `eval_classifier_clusters.py` inherited
    them for free by passing v3's schema to `build_features`. This script derives a
    FRESH schema (the corpus is schema-v1, 470 columns, not v3's 360), so the mask
    has to be re-applied explicitly — otherwise the retrain differs from v3 in
    model RECIPE as well as data, and reports a number inflated by 22 columns that
    encode "which run is this".
    """
    df, _ = load_with_labels(csv_dir=csv_dir, manifest=manifests,
                             drop_unlabeled=True, skip_warmup_rows=SKIP_WARMUP_ROWS)
    y = frame_labels(df)
    meta = {
        "file_id": df["__file_id"].astype(str).to_numpy(),
        "row_idx": df["__row_idx"].to_numpy().astype(np.int64),
        "adcs_mode": df["__adcs_mode"].astype(str).to_numpy(),
        "in_corruption": df["__corruption_window"].astype(bool).to_numpy(),
        "attack_id": df["__attack_id"].fillna("").astype(str).to_numpy(),
    }
    drop = [c for c in df.columns if c.startswith("__") and c != "__file_id"]
    feat_df = df.drop(columns=drop)
    if schema is not None:
        feat_df = _align_to_schema(feat_df, schema)
    X, sch = build_features(feat_df, include_deltas=True, schema=schema,
                            delta_only=delta_only)

    keep = np.array([lbl in allowed_labels for lbl in y], dtype=bool)
    dropped = sorted(set(y[~keep]))
    if dropped:
        print(f"  kept {int(keep.sum())}/{len(keep)} rows; dropped out-of-set "
              f"classes: {dropped}")
    X, y = X[keep], y[keep]
    meta = {k: v[keep] for k, v in meta.items()}
    return X, y, meta, sch


def cached_fold(cache_dir: str, name: str, csv_dir: str, mans: list[str],
                schema: dict | None, allowed: set[str],
                delta_only: list[str] | None = None):
    """One fold, checkpointed. Featurization is the expensive step (~3 min/fold)
    and this machine kills long jobs unpredictably (see AINOS3-100).

    Returns (X, y, meta, schema) with X **memory-mapped**, not resident. Holding
    five folds as float64 put this process at ~7 GB and the environment's reaper
    killed it there, twice, with 445 GB free — so the arrays live on disk as
    float32 `.npy` and only the training matrix of the current fold is ever
    materialised. float32 is also what HistGradientBoosting converts to before
    binning into uint8, so nothing is lost by storing it that way.

    The schema is written beside the FIRST fold's cache and read back with it, so
    a resumed run can never build later folds against a schema the cached fold 0
    was not built with.
    """
    os.makedirs(cache_dir, exist_ok=True)
    xp = os.path.join(cache_dir, f"{name}_X.npy")
    mp = os.path.join(cache_dir, f"{name}_meta.npz")
    sp = os.path.join(cache_dir, "schema.json")
    if os.path.exists(xp) and os.path.exists(mp):
        X = np.load(xp, mmap_mode="r")
        z = np.load(mp, allow_pickle=True)
        print(f"  [cache] {name}: X={X.shape} (mmap)")
        if schema is None:
            schema = json.load(open(sp))
        return (X, z["y"].astype(object),
                {k: z[f"meta_{k}"] for k in META_KEYS}, schema)
    X, y, meta, sch = load_fold(csv_dir, mans, schema, allowed, delta_only)
    if schema is None:
        schema = {"scalar_columns": sch.scalar_columns,
                  "list_columns": sch.list_columns,
                  "dropped_text_columns": sch.dropped_text_columns,
                  "delta_only_columns": sch.delta_only_columns,
                  "feature_names": sch.feature_names}
        json.dump(schema, open(sp, "w"))
    np.save(xp, _to_float32(X))
    np.savez(mp, y=np.array(y, dtype=str),
             **{f"meta_{k}": v for k, v in meta.items()})
    del X
    return np.load(xp, mmap_mode="r"), y, meta, schema


def _to_float32(X: np.ndarray) -> np.ndarray:
    """Cast to float32, clamping anything outside its range first.

    `ADCS_GNC.DT` reads 1.5e284 in 6 frames of the corpus (normal value 0.1),
    which overflows float32 to `inf` on a plain `.astype`. Clamping to the float32
    limit is the cast that preserves behaviour: HistGradientBoosting bins by RANK,
    so the clamped value lands in exactly the bin the float64 value occupied,
    whereas NaN would silently reclassify a corrupt reading as a missing one.
    """
    F32MAX = np.finfo(np.float32).max
    out = np.clip(X, -F32MAX, F32MAX).astype(np.float32)
    n_bad = int((~np.isfinite(out)).sum())
    if n_bad:
        raise SystemExit(f"{n_bad} non-finite cells survived the float32 cast")
    return out


def fit_resumable(hp: dict, Xtr, ytr, ckpt: str, step: int = 25):
    """Fit a HistGradientBoosting model, checkpointing every `step` iterations.

    A fold's 300 boosting iterations take ~29 minutes here, and this environment
    reaps the process every few minutes for reasons AINOS3-100 investigated and
    could not explain. Fold-level checkpointing is not enough: if no fold can ever
    finish between two kills, the run never converges no matter how many times it
    is resumed.

    ⚠ `step` must stay BELOW the interval between kills. Observed 2026-09-19: with
    step=25 (~150 s/block) and kills arriving every ~60-90 s, fold 3 resumed at
    iteration 25 three times in a row and never advanced — checkpointing that is
    slower than the kill rate is not resumable, it is a live-lock. Drop `--fit-step`
    until a block fits inside the window.

    Boosting is sequential, so `warm_start=True` with a rising `max_iter` produces
    exactly the tree sequence a single `fit(max_iter=300)` would — the same data in
    the same order with the same seed, just resumable. The partially-trained
    estimator is pickled after each block, and a resumed run picks up at the block
    boundary it reached.
    """
    target = hp.get("max_iter", 300)
    clf, done = None, 0
    if os.path.exists(ckpt):
        with open(ckpt, "rb") as f:
            clf, done = pickle.load(f)
        print(f"    [partial] resuming at iteration {done}/{target}")
    if clf is None:
        clf = make_clf(hp)
        clf.set_params(warm_start=True, max_iter=step)
    while done < target:
        nxt = min(done + step, target)
        clf.set_params(max_iter=nxt)
        t = time.time()
        clf.fit(Xtr, ytr)
        done = nxt
        tmp = ckpt + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump((clf, done), f)
        os.replace(tmp, ckpt)      # atomic: a kill mid-write cannot corrupt it
        print(f"    iter {done}/{target} ({time.time()-t:.0f}s)", flush=True)
    return clf


def stack_folds(data, exclude: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Materialise the training matrix from the memory-mapped folds.

    Two deliberate choices, both about peak RSS — this environment reaps a
    background task somewhere around 6 GB:

    * `np.vstack` over mmaps would build an intermediate list of full arrays.
      Preallocating and copying fold-by-fold costs one training matrix, not two.
    * The destination is **float64**, even though the caches are float32.
      HistGradientBoosting's `X_DTYPE` is float64, so handing it float32 makes it
      allocate its own float64 copy and we pay for both — 1.5 GB + 3.0 GB instead
      of 3.0 GB. Building float64 up front lets `check_array` pass it through.
    """
    idx = [j for j in range(len(data)) if j != exclude]
    rows = sum(data[j][0].shape[0] for j in idx)
    cols = data[idx[0]][0].shape[1]
    Xtr = np.empty((rows, cols), dtype=np.float64)
    at = 0
    for j in idx:
        n = data[j][0].shape[0]
        Xtr[at:at + n] = data[j][0]
        at += n
    ytr = np.concatenate([data[j][1] for j in idx])
    return Xtr, ytr


# ──────────────────────────────── main ─────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["rebuild", "v3stage"], default="rebuild")
    p.add_argument("--corpus", default="data/onair/corpus/rebuild_2026-09-10")
    p.add_argument("--views-dir", default="",
                   help="use prebuilt per-instance view dirs instead of "
                        "materialising them from the corpus manifest — e.g. "
                        "views_blended/, which points at de-interleaved CSVs")
    p.add_argument("--mode", default="SUNSAFE", help="rebuild: which collection mode")
    p.add_argument("--instances", default="", help="rebuild: comma list, e.g. 1,2,3")
    p.add_argument("--csv-dir", default="data/onair/csv_corpus_v3stage")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--mode-filter", default="",
                   help="keep only rows in this __adcs_mode (e.g. MODE_SUNSAFE) — "
                        "the AC3 mode-scope control")
    p.add_argument("--hp-from", default="data/onair/models/xgb_attack_classifier_v3.pkl",
                   help="pickle whose hyper-parameters are reused, so the retrain "
                        "differs from v3 in DATA only, not in model capacity")
    p.add_argument("--cache-dir", default="")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--tau", type=float, default=0.30)
    p.add_argument("--fit-step", type=int, default=25,
                   help="boosting iterations per checkpoint. Must be small "
                        "enough that one block finishes between kills, or the "
                        "run live-locks re-doing the same block forever.")
    p.add_argument("--delta-only-preset", default="v5", choices=["v5", "none"],
                   help="v5 (default) masks the raw values of the 22 absolute-time "
                        "and orbital columns, matching the recipe frozen into v3's "
                        "schema; 'none' would let the model read the sim epoch")
    p.add_argument("--featurize-only", action="store_true",
                   help="build and cache the folds, then stop — used to prepare a "
                        "held-out fold (e.g. INERTIAL) against an existing schema "
                        "without running LOIO on it")
    p.add_argument("--fit-full", action="store_true",
                   help="also fit one model on ALL folds and pickle it — the "
                        "deployable artifact (AC6)")
    return p


def main():
    args = build_parser().parse_args()

    t0 = time.time()
    os.makedirs(args.out_dir, exist_ok=True)
    cache_dir = args.cache_dir or os.path.join(args.out_dir, "cache")

    # ─── label scope: the frozen set, never inferred from the corpus (AC6) ───
    ls = load_label_set()
    allowed = set(trained_classes())
    print(f"frozen label set {ls['frozen_at']} ({ls['source_ticket']}): "
          f"{len(allowed)} trained classes")

    # ─── hyper-parameters: v3's, so only the DATA differs ───────────────────
    with open(args.hp_from, "rb") as f:
        hp = pickle.load(f)["clf"].get_params()
    print(f"hyper-parameters from {os.path.basename(args.hp_from)}: "
          f"max_iter={hp['max_iter']} max_depth={hp['max_depth']} "
          f"class_weight={hp['class_weight']}")

    delta_only = (list(V5_DELTA_ONLY_COLUMNS)
                  if args.delta_only_preset == "v5" else [])
    print(f"delta-only mask: {len(delta_only)} columns "
          f"(preset {args.delta_only_preset})")

    # ─── folds ──────────────────────────────────────────────────────────────
    if args.source == "rebuild":
        insts = [int(s) for s in (args.instances or "1,2,3,4,5").split(",") if s.strip()]
        folds = (prebuilt_views(args.views_dir, args.mode, insts) if args.views_dir
                 else rebuild_instances(args.corpus, args.mode, insts))
    else:
        folds = v3stage_instances(args.csv_dir, args.manifest_dir)
    print(f"\n{len(folds)} folds: {[n for n, _, _ in folds]}")

    # Fold 0 defines the feature schema; every later fold is built against it so
    # the matrix width — and therefore the model — is identical across folds.
    schema = None
    data = []
    for i, (name, csv_dir, mans) in enumerate(folds):
        print(f"\n=== fold {i}: {name} ({len(mans)} runs) ===")
        X, y, meta, schema = cached_fold(cache_dir, name, csv_dir, mans,
                                         schema, allowed, delta_only)
        X, y, meta = apply_mode_filter(X, y, meta, args.mode_filter or None)
        assert X.shape[1] == len(schema["feature_names"]), \
            f"{name}: {X.shape[1]} features != schema {len(schema['feature_names'])}"
        print(f"  X={X.shape} classes={len(set(y))} "
              f"attack={(y != 'nominal').sum()} nominal={(y == 'nominal').sum()}")
        data.append((X, y, meta))

    labels = sorted(set().union(*[set(y) for _, y, _ in data]))
    print(f"\nlabel space: {len(labels)} classes -> {labels}")

    if args.featurize_only:
        print(f"\n--featurize-only: cached {len(data)} folds to {cache_dir}, stopping")
        return

    # ─── LOIO ───────────────────────────────────────────────────────────────
    from sklearn.metrics import accuracy_score, f1_score
    conf_counts: dict = defaultdict(int)
    fold_acc, per_fold_f1_list = [], []
    all_true, all_pred, all_conf = [], [], []
    all_meta = {k: [] for k in META_KEYS}

    # Each fold's fit is checkpointed. A fold costs 15-40 min and this machine
    # kills long jobs for reasons AINOS3-100 investigated and could not explain;
    # without this, one kill at fold 4 of 5 discards hours of completed folds.
    fit_dir = os.path.join(args.out_dir, "folds")
    os.makedirs(fit_dir, exist_ok=True)

    for held in range(len(data)):
        Xte, yte, mte = data[held]
        ckpt = os.path.join(fit_dir, f"fold_{held}.npz")
        if os.path.exists(ckpt):
            z = np.load(ckpt, allow_pickle=True)
            if len(z["y_pred"]) != len(yte):
                raise SystemExit(
                    f"{ckpt} holds {len(z['y_pred'])} predictions but the fold now "
                    f"has {len(yte)} rows — the cache changed under the checkpoint. "
                    f"Delete {fit_dir} and re-fit.")
            ypred = z["y_pred"].astype(object)
            conf = z["confidence"]
            acc = float(z["accuracy"])
            print(f"  [ckpt] fold {held} ({folds[held][0]}): acc={acc:.4f}")
        else:
            Xtr, ytr = stack_folds(data, exclude=held)
            t1 = time.time()
            clf = fit_resumable(hp, Xtr, ytr,
                                os.path.join(fit_dir, f"fold_{held}.partial.pkl"),
                                step=args.fit_step)
            del Xtr, ytr
            proba = clf.predict_proba(np.asarray(Xte, dtype=np.float64))
            am = proba.argmax(axis=1)
            ypred = clf.classes_[am]
            conf = proba[np.arange(len(am)), am]
            acc = float(accuracy_score(yte, ypred))
            del proba
            np.savez(ckpt, y_pred=np.array(ypred, dtype=str),
                     confidence=conf, accuracy=np.array(acc))
            partial = os.path.join(fit_dir, f"fold_{held}.partial.pkl")
            if os.path.exists(partial):
                os.remove(partial)      # the fold is done; its partial is dead weight
            print(f"  fold {held} ({folds[held][0]}): test={len(yte)} "
                  f"acc={acc:.4f} ({time.time()-t1:.0f}s)")
        fold_acc.append(acc)
        per_fold_f1_list.append(per_class_f1(yte, ypred, labels))
        all_true.append(yte)
        all_pred.append(ypred)
        all_conf.append(conf)
        for k in META_KEYS:
            all_meta[k].append(mte[k])
        for t, pr in zip(yte, ypred):
            conf_counts[(t, pr)] += 1

    np.savez(
        os.path.join(args.out_dir, "loio_predictions.npz"),
        fold_held=np.array(list(range(len(data)))),
        fold_names=np.array([n for n, _, _ in folds], dtype=str),
        y_true=np.concatenate(all_true).astype(str),
        y_pred=np.concatenate(all_pred).astype(str),
        confidence=np.concatenate(all_conf).astype(np.float64),
        fold_of_row=np.concatenate(
            [np.full(len(all_true[h]), h) for h in range(len(data))]),
        file_id=np.concatenate(all_meta["file_id"]).astype(str),
        row_idx=np.concatenate(all_meta["row_idx"]).astype(np.int64),
        adcs_mode=np.concatenate(all_meta["adcs_mode"]).astype(str),
        in_corruption=np.concatenate(all_meta["in_corruption"]).astype(bool),
        attack_id=np.concatenate(all_meta["attack_id"]).astype(str),
        labels=np.array(labels, dtype=str),
        provenance_model=np.array(f"{args.source}:{args.mode}:"
                                  f"{len(folds)}fold:{args.mode_filter or 'allmodes'}"),
        provenance_csv_dir=np.array(args.csv_dir if args.source == "v3stage"
                                    else args.corpus),
        provenance_skip_warmup_rows=np.array(SKIP_WARMUP_ROWS),
    )

    acc_mean, acc_std = float(np.mean(fold_acc)), float(np.std(fold_acc))
    print(f"\nTECHNIQUE-level LOIO: {acc_mean:.4f} ± {acc_std:.4f}  "
          f"folds={[round(a, 4) for a in fold_acc]}")

    # ─── clusters + cluster-level re-score (same rule as v3) ────────────────
    clusters, edges = derive_clusters(conf_counts, labels, args.tau)
    multi = {r: m for r, m in clusters.items() if len(m) > 1}
    print(f"clusters: {len(clusters)} ({len(multi)} multi-member) at tau={args.tau}")
    for rep, members in sorted(multi.items()):
        print(f"  {rep}: {members}")

    clu_acc, clu_true_all, clu_pred_all = [], [], []
    for held in range(len(data)):
        yt = map_to_cluster(all_true[held], clusters)
        yp = map_to_cluster(all_pred[held], clusters)
        clu_acc.append(float(accuracy_score(yt, yp)))
        clu_true_all.append(yt)
        clu_pred_all.append(yp)
    clu_labels = sorted(set().union(*[set(y) for y in clu_true_all]))
    tech_macro = float(f1_score(np.concatenate(all_true), np.concatenate(all_pred),
                                labels=labels, average="macro", zero_division=0))
    clu_macro = float(f1_score(np.concatenate(clu_true_all), np.concatenate(clu_pred_all),
                               labels=clu_labels, average="macro", zero_division=0))
    print(f"CLUSTER-level   LOIO: {np.mean(clu_acc):.4f} ± {np.std(clu_acc):.4f}")
    print(f"macro-F1  technique={tech_macro:.4f}  cluster={clu_macro:.4f}")

    def mean_f1(per_fold, keys):
        return {k: {"mean_f1": round(float(np.mean([pf.get(k, 0.0) for pf in per_fold])), 3),
                    "std_f1": round(float(np.std([pf.get(k, 0.0) for pf in per_fold])), 3)}
                for k in keys}

    clu_per_fold = [per_class_f1(clu_true_all[h], clu_pred_all[h], clu_labels)
                    for h in range(len(data))]

    taxonomy = {
        "generated_utc": None,
        "source_ticket": "AINOS3-101",
        "source": args.source,
        "mode": args.mode if args.source == "rebuild" else None,
        "mode_filter": args.mode_filter or None,
        "n_instances": len(data),
        "fold_names": [n for n, _, _ in folds],
        "tau": args.tau,
        "label_set_frozen_at": ls["frozen_at"],
        "technique_level": {
            "loio_accuracy_mean": round(acc_mean, 4),
            "loio_accuracy_std": round(acc_std, 4),
            "loio_per_fold": [round(a, 4) for a in fold_acc],
            "macro_f1": round(tech_macro, 4),
            "n_classes": len(labels),
        },
        "cluster_level": {
            "loio_accuracy_mean": round(float(np.mean(clu_acc)), 4),
            "loio_accuracy_std": round(float(np.std(clu_acc)), 4),
            "loio_per_fold": [round(a, 4) for a in clu_acc],
            "macro_f1": round(clu_macro, 4),
            "n_classes": len(clu_labels),
        },
        "clusters": {r: m for r, m in sorted(clusters.items())},
        "cluster_edges": edges,
        "domain_identical_pairs": DOMAIN_IDENTICAL_PAIRS,
        "technique_f1": mean_f1(per_fold_f1_list, labels),
        "cluster_f1": mean_f1(clu_per_fold, clu_labels),
    }
    with open(os.path.join(args.out_dir, "cluster_taxonomy.json"), "w") as f:
        json.dump(taxonomy, f, indent=2)

    # ─── the deployable model: one fit over every fold (AC6) ────────────────
    out_pkl = os.path.join(args.out_dir, "classifier.pkl")
    if args.fit_full and os.path.exists(out_pkl):
        print(f"\n[ckpt] full-corpus model already at {out_pkl}")
    elif args.fit_full:
        print("\nfitting the full-corpus model (all folds)…")
        Xall, yall = stack_folds(data)
        t1 = time.time()
        full = fit_resumable(hp, Xall, yall,
                             os.path.join(fit_dir, "full.partial.pkl"),
                             step=args.fit_step)
        with open(out_pkl, "wb") as f:
            pickle.dump({"clf": full, "schema": schema,
                         "labels": sorted(set(yall.tolist())),
                         "provenance": {
                             "ticket": "AINOS3-101",
                             "corpus": args.corpus if args.source == "rebuild" else args.csv_dir,
                             "mode": args.mode, "instances": [n for n, _, _ in folds],
                             "label_set_frozen_at": ls["frozen_at"],
                             "hp_from": os.path.basename(args.hp_from),
                         }}, f)
        print(f"  wrote {out_pkl} ({len(set(yall.tolist()))} classes, "
              f"{time.time()-t1:.0f}s)")

    print(f"\nwrote {args.out_dir}  ({time.time()-t0:.0f}s total)")


if __name__ == "__main__":
    main()
