#!/usr/bin/env python3
"""AINOS3-37 — build the deployable selective per-mode hybrid classifier.

The deployed v3 head (`xgb_attack_classifier_v3.pkl`) is a single global
HistGradientBoosting model. AINOS3-33 showed full per-mode routing lifts the
signal-rich dynamic modes (INERTIAL +0.058, SUNSAFE +0.061) and the ROBUST tier
(+0.068) but regresses the signal-poor modes (BDOT -0.047, PASSIVE -0.028). The
SELECTIVE hybrid banks the dynamic-mode gains with zero risk to the quiescent
modes: route INERTIAL/SUNSAFE frames to their own per-mode head, keep the global
v3 head for PASSIVE/BDOT (and any unseen mode).

Because the non-routed modes keep the exact global head, they are
BASELINE-IDENTICAL — the hybrid cannot regress them by construction. The
`eval_mode_aware_classifier.py --variants baseline,per_mode,selective_hybrid`
LOIO is the evidence; this script produces the deployable artifact.

Artifact (a superset of the v3 pickle, so an unmodified plugin still loads the
global head and behaves exactly like v3):
    clf         : global head (reused from v3 — trained on the full corpus)
    mode_heads  : {mode: HistGB head} for each routed mode, full-corpus trained
    route_modes : [modes routed to their own head]
    calibration : {mode: {"x": [...], "y": [...]}} isotonic top1-prob -> reliability
                  (np.interp-appliable; no sklearn needed at flight runtime)
    labels, label_to_id, schema, config  : carried from v3 (unchanged)

Per-mode calibration makes the top-1 confidence comparable across heads (the
routed per-mode heads and the global head are otherwise on different probability
scales), so the plugin's single `min_confidence` threshold and the incident
confidence mean the same thing regardless of which head scored the frame. It is
monotonic, so it never changes the argmax (accuracy is unchanged) — it only
recalibrates the reported confidence. Fitted on a held-out instance and reported
as per-mode ECE before/after.

Usage:
    python3 components/onair/training/build_hybrid_classifier.py \\
        --classifier data/onair/models/xgb_attack_classifier_v3.pkl \\
        --csv-dir data/onair/csv_corpus_v3stage \\
        --manifest-dir data/onair/scenarios \\
        --route-modes MODE_INERTIAL,MODE_SUNSAFE \\
        --out data/onair/models/xgb_attack_classifier_v3_hybrid.pkl
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time

import numpy as np

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from eval_classifier_clusters import (  # noqa: E402
    discover_instances, load_instance, make_clf)

MIN_MODE_ROWS = 50  # matches the LOIO guard in fit_predict_selective


def _isotonic_xy(prob, correct):
    """Fit an isotonic (monotone non-decreasing) map top1-prob -> reliability,
    returned as sorted (x, y) arrays for np.interp at runtime. Uses sklearn to
    fit, then samples the step function at the unique inputs."""
    from sklearn.isotonic import IsotonicRegression
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(prob, correct.astype(float))
    xs = np.unique(prob)
    ys = iso.predict(xs)
    return xs.tolist(), ys.tolist()


def _ece(prob, correct, n_bins=10):
    """Expected calibration error: mean |confidence - accuracy| over prob bins."""
    prob = np.asarray(prob, float)
    correct = np.asarray(correct, float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        m = (prob >= lo) & (prob < hi if i < n_bins - 1 else prob <= hi)
        if not m.any():
            continue
        ece += (m.mean()) * abs(prob[m].mean() - correct[m].mean())
    return float(ece)


def _route_head(mode, heads, global_clf, route_modes):
    return heads.get(mode, global_clf) if mode in route_modes else global_clf


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--classifier",
                   default="data/onair/models/xgb_attack_classifier_v3.pkl")
    p.add_argument("--csv-dir", default="data/onair/csv_corpus_v3stage")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--route-modes", default="MODE_INERTIAL,MODE_SUNSAFE")
    p.add_argument("--out",
                   default="data/onair/models/xgb_attack_classifier_v3_hybrid.pkl")
    args = p.parse_args()

    t0 = time.time()
    route_modes = [m.strip() for m in args.route_modes.split(",") if m.strip()]

    with open(args.classifier, "rb") as f:
        v3 = pickle.load(f)
    schema = v3["schema"]
    labels = list(v3["labels"])
    hp = dict(v3["clf"].get_params())
    allowed = set(labels)
    n_feat = len(schema.get("feature_names", []))
    global_clf = v3["clf"]           # already trained on the full corpus
    print(f"v3: {len(labels)} labels, {n_feat} features, "
          f"global head max_iter={hp.get('max_iter')}; routing {route_modes}")

    instances = discover_instances(args.manifest_dir)
    if len(instances) < 2:
        sys.exit("need >= 2 instances (one is held out for calibration)")
    data = []
    for i, manifests in enumerate(instances):
        X, y, meta = load_instance(args.csv_dir, manifests, schema, allowed)
        assert X.shape[1] == n_feat, f"feature mismatch {X.shape[1]} != {n_feat}"
        data.append((X, y, meta["adcs_mode"]))
        print(f"  instance {i}: X={X.shape} modes={sorted(set(meta['adcs_mode']))}")

    Xall = np.vstack([d[0] for d in data])
    yall = np.concatenate([d[1] for d in data])
    mall = np.concatenate([d[2] for d in data])

    # ── Deploy per-mode heads: full-corpus, one per routed mode ──────────
    mode_heads = {}
    for m in route_modes:
        sel = mall == m
        if sel.sum() < MIN_MODE_ROWS or len(np.unique(yall[sel])) < 2:
            print(f"  [skip] {m}: too thin ({int(sel.sum())} rows) — will fall "
                  f"back to the global head at runtime")
            continue
        h = make_clf(hp)
        h.fit(Xall[sel], yall[sel])
        mode_heads[m] = h
        print(f"  fit per-mode head {m}: {int(sel.sum())} rows, "
              f"{len(np.unique(yall[sel]))} classes")

    # ── Per-mode calibration on a held-out instance (honest reliability) ──
    # Hold out instance 0; fit calibration heads on the rest with the SAME
    # routing, predict the held-out instance, and fit an isotonic map per mode.
    Xtr = np.vstack([data[j][0] for j in range(1, len(data))])
    ytr = np.concatenate([data[j][1] for j in range(1, len(data))])
    mtr = np.concatenate([data[j][2] for j in range(1, len(data))])
    Xte, yte, mte = data[0]
    cal_global = make_clf(hp); cal_global.fit(Xtr, ytr)
    cal_heads = {}
    for m in route_modes:
        sel = mtr == m
        if sel.sum() < MIN_MODE_ROWS or len(np.unique(ytr[sel])) < 2:
            continue
        h = make_clf(hp); h.fit(Xtr[sel], ytr[sel])
        cal_heads[m] = h

    calibration, ece_report = {}, {}
    for m in sorted(set(mte.tolist())):
        sel = mte == m
        if sel.sum() < MIN_MODE_ROWS:
            continue
        clf = _route_head(m, cal_heads, cal_global, route_modes)
        probs = clf.predict_proba(Xte[sel])
        top1 = probs.max(axis=1)
        pred = clf.classes_[probs.argmax(axis=1)]
        correct = (pred == yte[sel])
        if len(np.unique(top1)) < 2 or correct.mean() in (0.0, 1.0):
            continue  # nothing to calibrate
        # Deploy map: isotonic on the FULL held-out (most data → best map).
        xs, ys = _isotonic_xy(top1, correct)
        calibration[m] = {"x": xs, "y": ys}
        # HONEST validation ECE: fit the isotonic on one interleaved half and
        # measure ECE on the OTHER half — fitting and scoring on the same rows
        # would report a trivially-perfect in-sample 0.0 (isotonic overfits its
        # own fit set). Interleave (::2 / 1::2) so both halves span the ordered
        # scenario stream evenly.
        fit_p, fit_c = top1[::2], correct[::2]
        ev_p, ev_c = top1[1::2], correct[1::2]
        ece_raw = ece_cal = None
        if len(np.unique(fit_p)) >= 2 and len(ev_p) >= 50:
            xv, yv = _isotonic_xy(fit_p, fit_c)
            ece_raw = round(_ece(ev_p, ev_c), 4)
            ece_cal = round(_ece(np.interp(ev_p, xv, yv), ev_c), 4)
        ece_report[m] = {
            "n": int(sel.sum()), "n_eval": int(len(ev_p)),
            "ece_raw": ece_raw, "ece_cal": ece_cal,
            "routed": m in cal_heads,
        }

    print("\nper-mode calibration — held-out ECE (fit/eval split, honest):")
    for m, r in sorted(ece_report.items()):
        head = "per-mode head" if r["routed"] else "global head"
        if r["ece_raw"] is None:
            print(f"  {m:15} n={r['n']:6}  (too thin to validate)  ({head})")
        else:
            print(f"  {m:15} n={r['n']:6} ECE {r['ece_raw']:.4f} -> {r['ece_cal']:.4f}"
                  f"  ({head})")

    # ── Assemble + write the deployable artifact ─────────────────────────
    art = {
        "clf": global_clf,
        "labels": labels,
        "label_to_id": v3.get("label_to_id"),
        "schema": schema,
        "mode_heads": mode_heads,
        "route_modes": [m for m in route_modes if m in mode_heads],
        "calibration": calibration,
        "config": {
            **(v3.get("config") or {}),
            "version": "xgb_v3_hybrid",
            "base_model": os.path.basename(args.classifier),
            "route_modes": [m for m in route_modes if m in mode_heads],
            "calibration_ece": ece_report,
        },
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wb") as f:
        pickle.dump(art, f)
    print(f"\nwrote {args.out}")
    print(f"  global head + {len(mode_heads)} per-mode heads "
          f"({', '.join(mode_heads) or 'none'}); "
          f"{len(calibration)} calibrated modes")
    print(f"total: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
