#!/usr/bin/env python3
"""AINOS3-37 — export out-of-fold (OOF) predictions for the selective per-mode
hybrid, in the same npz format `eval_incident_rescore.py --oof-predictions`
consumes (file_id, row_idx, y_pred, confidence).

This is the HONEST label source for the coverage overlay: each frame is labelled
by a model that never saw its instance (leave-one-instance-out), mirroring the
deployed hybrid's routing — INERTIAL/SUNSAFE frames go to their per-mode head,
every other mode keeps the global head, labelled by that head's own `classes_`.
(In-sample would let the per-mode heads memorise their own mode → a fake lift.)

Confidence is the raw max-probability of the scoring head (uncalibrated); it only
affects an incident's reported confidence, not the label or recall the overlay's
`label_ok`/`incident_label_accuracy` are built from.

Usage:
    python3 components/onair/training/export_hybrid_oof.py \\
        --classifier data/onair/models/xgb_attack_classifier_v3.pkl \\
        --route-modes MODE_INERTIAL,MODE_SUNSAFE \\
        --out data/onair/models/cluster_rescore/loio_predictions_oof_v3hybrid.npz
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time

import numpy as np

try:
    from label_set import training_excludes as _ls_excludes
except Exception:  # label_set.json absent -> backward-compatible no-op
    _ls_excludes = lambda: []

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from eval_classifier_clusters import (  # noqa: E402
    discover_instances, load_instance, make_clf)

MIN_MODE_ROWS = 50


def fit_predict_selective_conf(Xtr, ytr, mtr, Xte, mte, hp, routed):
    """Selective routing → (labels, confidences) for the test fold. Non-routed
    modes use the global head; routed modes with enough data use their own."""
    heads = {}
    for m in routed:
        sel = mtr == m
        if sel.sum() < MIN_MODE_ROWS or len(np.unique(ytr[sel])) < 2:
            continue
        h = make_clf(hp); h.fit(Xtr[sel], ytr[sel]); heads[m] = h
    global_clf = make_clf(hp); global_clf.fit(Xtr, ytr)
    yp = np.empty(len(Xte), dtype=object)
    conf = np.zeros(len(Xte))
    for m in np.unique(mte):
        sel = mte == m
        clf = heads.get(m, global_clf)
        probs = clf.predict_proba(Xte[sel])
        am = probs.argmax(axis=1)
        yp[sel] = clf.classes_[am]
        conf[sel] = probs[np.arange(len(am)), am]
    return yp, conf


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--classifier",
                   default="data/onair/models/xgb_attack_classifier_v3.pkl")
    p.add_argument("--csv-dir", default="data/onair/csv_corpus_v3stage")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--route-modes", default="MODE_INERTIAL,MODE_SUNSAFE")
    p.add_argument("--out",
                   default="data/onair/models/cluster_rescore/loio_predictions_oof_v3hybrid.npz")
    args = p.parse_args()

    t0 = time.time()
    routed = [m.strip() for m in args.route_modes.split(",") if m.strip()]
    with open(args.classifier, "rb") as f:
        v3 = pickle.load(f)
    schema, hp = v3["schema"], dict(v3["clf"].get_params())
    allowed = set(v3["labels"]) - set(_ls_excludes())  # AINOS3-122 AC7: frozen label set
    n_feat = len(schema.get("feature_names", []))
    print(f"routing {routed} to per-mode heads; global head elsewhere; "
          f"max_iter={hp.get('max_iter')}")

    instances = discover_instances(args.manifest_dir)
    if len(instances) < 2:
        sys.exit("need >= 2 instances for LOIO")
    data = []
    for i, manifests in enumerate(instances):
        X, y, meta = load_instance(args.csv_dir, manifests, schema, allowed)
        assert X.shape[1] == n_feat, f"feature mismatch {X.shape[1]} != {n_feat}"
        data.append((X, y, meta["adcs_mode"],
                     meta["file_id"].astype(str), meta["row_idx"].astype(np.int64)))
        print(f"  instance {i}: X={X.shape}")

    fid_all, ridx_all, pred_all, conf_all = [], [], [], []
    # y_true / fold_of_row / labels are persisted alongside the predictions so
    # this cache can drive recluster_from_cache.py and per-class F1 directly.
    # Without them the file records what the hybrid predicted but not what was
    # true, which makes it unusable for re-deriving the cluster taxonomy or the
    # classifier tiers — both of which are hybrid-dependent.
    true_all, fold_all, mode_all = [], [], []
    for held in range(len(data)):
        Xtr = np.vstack([data[j][0] for j in range(len(data)) if j != held])
        ytr = np.concatenate([data[j][1] for j in range(len(data)) if j != held])
        mtr = np.concatenate([data[j][2] for j in range(len(data)) if j != held])
        Xte, yte, mte, fte, rte = data[held]
        t1 = time.time()
        yp, conf = fit_predict_selective_conf(Xtr, ytr, mtr, Xte, mte, hp, routed)
        fid_all.append(fte); ridx_all.append(rte)
        pred_all.append(yp.astype(str)); conf_all.append(conf)
        true_all.append(np.asarray(yte).astype(str))
        fold_all.append(np.full(len(yp), held, dtype=np.int64))
        mode_all.append(np.asarray(mte).astype(str))
        print(f"  fold {held}: {len(yp)} OOF preds ({time.time()-t1:.0f}s)")

    labels = sorted(set(np.concatenate(true_all).tolist()))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    np.savez_compressed(
        args.out,
        file_id=np.concatenate(fid_all),
        row_idx=np.concatenate(ridx_all),
        y_pred=np.concatenate(pred_all),
        confidence=np.concatenate(conf_all),
        y_true=np.concatenate(true_all),
        fold_of_row=np.concatenate(fold_all),
        adcs_mode=np.concatenate(mode_all),
        fold_held=np.arange(len(data), dtype=np.int64),
        labels=np.array(labels, dtype=str),
        # `--classifier` supplies only the RECIPE (schema + hyper-parameters);
        # the heads are refit per fold and routing is applied here. Recording
        # just the pickle name would read as "these are v3-global predictions",
        # which is exactly wrong — so state the model explicitly.
        provenance_model=np.array(
            f"selective per-mode hybrid (routed: {','.join(routed) or 'none'}) "
            f"— recipe from {os.path.basename(args.classifier)}"),
        provenance_recipe_pickle=np.array(os.path.basename(args.classifier)),
        provenance_route_modes=np.array(",".join(routed)),
        provenance_csv_dir=np.array(args.csv_dir))
    n = sum(len(a) for a in pred_all)
    print(f"\nwrote {args.out}  ({n} OOF predictions)")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
