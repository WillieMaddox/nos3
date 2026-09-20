#!/usr/bin/env python3
"""AINOS3-27 — re-score the labeled corpus at INCIDENT granularity.

Frame-level metrics (e.g. "61% of SUNSAFE corruption rows flagged") undersell
the operational picture: an operator cares whether *the attack* raised an
alert, not what fraction of its frames did. This tool runs the deployed v5 IF
gate + the same hysteresis-based `IncidentAggregator` the live plugin uses
(AINOS3-25) over the 3-instance corpus, then scores:

  - **Incident-level detection (recall):** an attack is DETECTED if ≥1 incident
    overlaps its corruption window. Reported overall + per ADCS mode + per
    attack.
  - **False incidents (FP):** incidents that overlap no corruption window
    (i.e. fire during nominal/scenario time), as a count and a per-hour rate.
  - **Incident label accuracy:** of detected attacks, does the incident's
    winning cluster match the true attack's cluster? (in-sample for the label
    only — the deployed v3 was trained on these frames; the DETECTION metric is
    not, since the IF threshold is calibrated on held-out nominal.)

Detection uses the IF gate + hysteresis only, so it is independent of the
classifier's in-sample bias.

Usage:
    python3 components/onair/training/eval_incident_rescore.py \\
        --csv-dir data/onair/csv_corpus_v3stage \\
        --manifest-dir data/onair/scenarios \\
        --if-model data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl \\
        --classifier data/onair/models/xgb_attack_classifier_v3.pkl \\
        --taxonomy data/onair/models/cluster_rescore/cluster_taxonomy.json \\
        --out data/onair/models/cluster_rescore/incident_rescore.json
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

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
sys.path.insert(0, os.path.join(
    os.path.dirname(THIS_DIR), "fsw", "plugins", "xgb_classifier"))
from loader import load_with_labels        # noqa: E402
from features import build_features          # noqa: E402
from incident import IncidentAggregator, cluster_map_from_taxonomy  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", default="data/onair/csv_corpus_v3stage")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--if-model",
                   default="data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl")
    p.add_argument("--classifier",
                   default="data/onair/models/xgb_attack_classifier_v3.pkl")
    p.add_argument("--oof-predictions", default=None,
                   help="loio_predictions.npz from eval_classifier_clusters.py. "
                        "When set, incident labels are driven by the out-of-fold "
                        "predictions (joined on file_id+row_idx) instead of the "
                        "in-sample classifier, giving an honest label accuracy.")
    p.add_argument("--taxonomy",
                   default="data/onair/models/cluster_rescore/cluster_taxonomy.json")
    p.add_argument("--alert-hyst", type=int, default=3)
    p.add_argument("--clear-hyst", type=int, default=5)
    p.add_argument("--hz", type=float, default=4.2, help="for FP-per-hour")
    p.add_argument("--out", default="data/onair/models/cluster_rescore/incident_rescore.json")
    args = p.parse_args()

    t0 = time.time()

    # ─── models ────────────────────────────────────────────────────────
    with open(args.if_model, "rb") as f:
        if_art = pickle.load(f)
    if_models = if_art["models"]
    schema = if_art["schema"]
    if_cal = json.load(open(args.if_model.removesuffix(".pkl") + ".calibration.json"))
    thresholds = {k: float(v) for k, v in if_cal["thresholds"].items()}

    oof_mode = bool(args.oof_predictions)
    clf = labels = None
    oof = {}
    if oof_mode:
        z = np.load(args.oof_predictions, allow_pickle=True)
        if "file_id" not in z.files:
            sys.exit(f"{args.oof_predictions} predates AINOS3-34 (no file_id/row_idx "
                     "columns); re-run eval_classifier_clusters.py to regenerate it.")
        oof_fid = z["file_id"].astype(str)
        oof_ridx = z["row_idx"].astype(np.int64)
        oof_pred = z["y_pred"].astype(str)
        oof_conf = z["confidence"].astype(float) if "confidence" in z.files \
            else np.ones(len(oof_pred))
        oof = {(oof_fid[i], int(oof_ridx[i])): (oof_pred[i], float(oof_conf[i]))
               for i in range(len(oof_pred))}
        oof_files = set(oof_fid.tolist())
        print(f"out-of-fold predictions: {len(oof)} frames over "
              f"{len(oof_files)} files (label source = LOIO out-of-fold)")
    else:
        with open(args.classifier, "rb") as f:
            clf_art = pickle.load(f)
        clf = clf_art["clf"]
        labels = list(clf_art["labels"])

    cluster_map = {}
    if os.path.exists(args.taxonomy):
        cluster_map = cluster_map_from_taxonomy(json.load(open(args.taxonomy)))

    def to_cluster(lbl):
        return cluster_map.get(lbl, lbl)

    # ─── corpus ────────────────────────────────────────────────────────
    print("loading corpus ...")
    df, _ = load_with_labels(csv_dir=args.csv_dir, manifest=args.manifest_dir,
                             drop_unlabeled=True, skip_warmup_rows=30)
    if oof_mode:
        # Restrict to the exact files the out-of-fold cache covers, so the IF
        # gate + aggregation run over the same frames the LOIO predicted. Whole
        # files are dropped, so per-file delta masking stays intact.
        keep = df["__file_id"].astype(str).isin(oof_files).to_numpy()
        dropped_files = sorted(set(df["__file_id"][~keep].astype(str)))
        df = df[keep].reset_index(drop=True)
        print(f"  OOF: kept {len(df)} rows from {df['__file_id'].nunique()} "
              f"cached files (dropped {len(dropped_files)} non-cache files)")
    drop = [c for c in df.columns if c.startswith("__") and c != "__file_id"]
    X, _ = build_features(df.drop(columns=drop), include_deltas=True, schema=schema)
    print(f"  {len(df)} rows, X={X.shape}")

    modes = df["__adcs_mode"].astype(str).to_numpy()
    fids = df["__file_id"].to_numpy()
    ridx = df["__row_idx"].to_numpy()
    in_corr = df["__corruption_window"].astype(bool).to_numpy()
    attack_id = df["__attack_id"].fillna("").astype(str).to_numpy()

    # ─── IF gate per frame (vectorized per mode) ───────────────────────
    print("IF gating ...")
    is_anom = np.zeros(len(df), dtype=bool)
    if_score = np.full(len(df), np.nan)
    for mode in np.unique(modes):
        if mode not in if_models:
            continue
        m = modes == mode
        sc = if_models[mode].decision_function(X[m])
        if_score[m] = sc
        is_anom[m] = sc < thresholds.get(mode, 0.0)
    print(f"  anomalous frames: {int(is_anom.sum())}/{len(df)} "
          f"({is_anom.mean()*100:.1f}%)")

    # ─── classifier on anomalous frames only (IF-gated, like the plugin) ─
    top1 = np.full(len(df), "", dtype=object)
    top1p = np.zeros(len(df))
    idx = np.where(is_anom)[0]
    if oof_mode:
        print("labeling anomalous frames from out-of-fold predictions ...")
        n_hit = 0
        for i in idx:
            pc = oof.get((str(fids[i]), int(ridx[i])))
            if pc is not None:
                top1[i], top1p[i] = pc[0], pc[1]
                n_hit += 1
        print(f"  {n_hit}/{len(idx)} anomalous frames had an out-of-fold label "
              f"({len(idx) - n_hit} unlabeled — out-of-classifier-set classes)")
    elif len(idx):
        print("classifying anomalous frames ...")
        probs = clf.predict_proba(X[idx])
        am = probs.argmax(axis=1)
        for k, i in enumerate(idx):
            top1[i] = labels[am[k]]
            top1p[i] = float(probs[k, am[k]])

    # ─── per-file incident aggregation ─────────────────────────────────
    print("aggregating incidents per file ...")
    incidents = []   # (file_id, Incident, overlapped_attack_ids:set)
    order = np.lexsort((ridx, fids))   # sort by file, then row_idx
    # group contiguous file blocks in sorted order
    sf = fids[order]
    start = 0
    for i in range(1, len(order) + 1):
        if i == len(order) or sf[i] != sf[start]:
            block = order[start:i]
            _aggregate_file(block, ridx, is_anom, modes, top1, top1p,
                            in_corr, attack_id, to_cluster, fids,
                            args.alert_hyst, args.clear_hyst, incidents)
            start = i

    # ─── ground truth: unique (file, attack_id) with corruption frames ─
    gt = defaultdict(lambda: {"mode": "", "detected": False,
                              "true_cluster": "", "pred_cluster": "",
                              "label_correct": False})
    for j in range(len(df)):
        if in_corr[j] and attack_id[j]:
            key = (fids[j], attack_id[j])
            if not gt[key]["mode"]:
                gt[key]["mode"] = modes[j]
                gt[key]["true_cluster"] = to_cluster(attack_id[j])

    fp_incidents = 0
    for fid, inc, overlapped in incidents:
        if not overlapped:
            fp_incidents += 1
            continue
        for aid in overlapped:
            key = (fid, aid)
            if key in gt:
                gt[key]["detected"] = True
                # record the incident's predicted cluster for label accuracy
                if not gt[key]["pred_cluster"]:
                    gt[key]["pred_cluster"] = inc.cluster
                    gt[key]["label_correct"] = (inc.cluster == gt[key]["true_cluster"])

    # ─── aggregate metrics ─────────────────────────────────────────────
    per_attack = defaultdict(lambda: {"n": 0, "detected": 0, "label_ok": 0})
    per_mode = defaultdict(lambda: {"n": 0, "detected": 0, "label_ok": 0})
    per_cluster = defaultdict(lambda: {"n": 0, "detected": 0, "label_ok": 0})
    for (fid, aid), v in gt.items():
        a = aid
        per_attack[a]["n"] += 1
        per_mode[v["mode"]]["n"] += 1
        per_cluster[v["true_cluster"]]["n"] += 1
        if v["detected"]:
            per_attack[a]["detected"] += 1
            per_mode[v["mode"]]["detected"] += 1
            per_cluster[v["true_cluster"]]["detected"] += 1
            if v["label_correct"]:
                per_attack[a]["label_ok"] += 1
                per_mode[v["mode"]]["label_ok"] += 1
                per_cluster[v["true_cluster"]]["label_ok"] += 1

    n_attacks = len(gt)
    n_detected = sum(1 for v in gt.values() if v["detected"])
    n_label_ok = sum(1 for v in gt.values() if v["detected"] and v["label_correct"])
    total_min = len(df) / args.hz / 60.0

    def _lblacc(v):
        return round(v["label_ok"] / v["detected"], 4) if v.get("detected") else None

    summary = {
        "prediction_source": "out_of_fold" if oof_mode else "in_sample",
        "oof_predictions": args.oof_predictions if oof_mode else None,
        "n_ground_truth_attacks": n_attacks,
        "incident_detection_recall": round(n_detected / n_attacks, 4) if n_attacks else None,
        "n_detected": n_detected,
        "n_false_incidents": fp_incidents,
        "false_incidents_per_hour": round(fp_incidents / (total_min / 60.0), 3) if total_min else None,
        "incident_label_accuracy_of_detected": round(n_label_ok / n_detected, 4) if n_detected else None,
        "total_incidents": len(incidents),
        "corpus_minutes_approx": round(total_min, 1),
        "alert_hyst": args.alert_hyst, "clear_hyst": args.clear_hyst,
        "per_mode": {m: {**v, "recall": round(v["detected"]/v["n"], 4) if v["n"] else None,
                         "label_accuracy_of_detected": _lblacc(v)}
                     for m, v in sorted(per_mode.items())},
        "per_cluster": {c: {**v, "recall": round(v["detected"]/v["n"], 4) if v["n"] else None,
                            "label_accuracy_of_detected": _lblacc(v)}
                        for c, v in sorted(per_cluster.items())},
        "per_attack": {a: {**v, "recall": round(v["detected"]/v["n"], 4) if v["n"] else None}
                       for a, v in sorted(per_attack.items())},
    }

    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)

    # ─── print ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"INCIDENT-LEVEL RE-SCORE  (alert/clear hyst {args.alert_hyst}/{args.clear_hyst})")
    print(f"{'='*60}")
    print(f"ground-truth attacks (file×id) : {n_attacks}")
    print(f"incident detection recall      : {summary['incident_detection_recall']:.1%} "
          f"({n_detected}/{n_attacks})")
    print(f"false incidents                : {fp_incidents} "
          f"({summary['false_incidents_per_hour']:.2f}/h over ~{total_min/60:.1f}h)")
    caveat = ("out-of-fold — honest" if oof_mode
              else "in-sample label caveat")
    print(f"incident label accuracy        : {summary['incident_label_accuracy_of_detected']:.1%} "
          f"of detected ({caveat})")
    print(f"\nper mode (recall · label-acc of detected):")
    for m, v in summary["per_mode"].items():
        if v["n"]:
            la = v["label_accuracy_of_detected"]
            print(f"  {m:16} {v['detected']:>3}/{v['n']:<3} = {v['recall']:.0%} "
                  f"· label {f'{la:.0%}' if la is not None else '—'}")
    print(f"\nper cluster (recall · label-acc of detected):")
    for c, v in summary["per_cluster"].items():
        if v["n"]:
            la = v["label_accuracy_of_detected"]
            print(f"  {c:24} {v['detected']:>3}/{v['n']:<3} = {v['recall']:.0%} "
                  f"· label {f'{la:.0%}' if la is not None else '—'}")
    print(f"\nper attack (recall across instances):")
    for a, v in summary["per_attack"].items():
        print(f"  {a:22} {v['detected']}/{v['n']} det, "
              f"{v['label_ok']}/{v['detected'] or 1} labeled-correct")
    print(f"\nwrote {args.out}")
    print(f"total: {time.time()-t0:.0f}s")


def _aggregate_file(block, ridx, is_anom, modes, top1, top1p, in_corr,
                    attack_id, to_cluster, fids, alert_hyst, clear_hyst,
                    out_incidents):
    """Run the IncidentAggregator over one file's frames (already globally
    sorted, block holds this file's row indices in row order)."""
    fid = fids[block[0]]
    agg = IncidentAggregator(alert_hysteresis=alert_hyst, clear_hysteresis=clear_hyst)
    # map row_idx -> (in_corr, attack_id) for overlap resolution
    block_ridx = ridx[block]
    block_corr = in_corr[block]
    block_aid = attack_id[block]

    def resolve(inc):
        m = (block_ridx >= inc.frame_start) & (block_ridx <= inc.frame_end)
        ats = set(a for a, c in zip(block_aid[m], block_corr[m]) if c and a)
        return ats

    for pos in block:
        inc = agg.update(
            int(ridx[pos]), bool(is_anom[pos]), mode=str(modes[pos]),
            cluster=to_cluster(top1[pos]) if top1[pos] else "",
            sub_technique=str(top1[pos]), confidence=float(top1p[pos]))
        if inc is not None:
            out_incidents.append((fid, inc, resolve(inc)))
    inc = agg.flush()
    if inc is not None:
        out_incidents.append((fid, inc, resolve(inc)))


if __name__ == "__main__":
    main()
