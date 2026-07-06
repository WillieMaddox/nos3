#!/usr/bin/env python3
"""Phase 4 — score the labeled attack corpus through a trained TCN, emit
per-frame MSE prediction-error, and compute per-attack-class AUCPR.

Compares against the v3 XGBoost F1 baseline for the spike-decision report.

Output:
  - `tcn_scores.csv`: one row per scored frame with attack_id, mode,
    corruption_window flag, prediction MSE, IF score.
  - `tcn_aucpr_per_class.json`: per-class AUCPR with the "is this row
    inside the corruption window for class X" binary task.
  - Stdout: comparison table TCN AUCPR vs v3 XGBoost F1 per class.
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

try:
    import torch
    import torch.nn.functional as F
except ImportError:
    print("ERROR: PyTorch not installed.")
    sys.exit(1)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels
from features import build_features

# Reuse the model class from the trainer
sys.path.insert(0, THIS_DIR)
from train_temporal import GlobalTCN, SEQ_LEN


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="Path to trained TCN pickle")
    p.add_argument("--csv-dir", required=True)
    p.add_argument("--manifest-dir", required=True)
    p.add_argument("--out", required=True,
                   help="Output directory for tcn_scores.csv + tcn_aucpr_per_class.json")
    p.add_argument("--batch-size", type=int, default=512)
    p.add_argument("--v3-cal",
                   default="data/onair/models/xgb_attack_classifier_v3.calibration.json",
                   help="v3 calibration JSON for per-class F1 comparison")
    args = p.parse_args()

    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    # ─── Load model ────────────────────────────────────────────────────
    with open(args.model, "rb") as f:
        art = pickle.load(f)
    cfg = art["config"]
    schema = art["schema"]
    mu = art["feature_mu"]
    sd = art["feature_sd"]
    print(f"loaded TCN v{cfg.get('version', '?')} — seq_len={cfg['seq_len']}, "
          f"n_features={cfg['n_features']}, "
          f"best_val_loss={cfg.get('best_val_loss', '?'):.5f}")
    model = GlobalTCN(n_features=cfg["n_features"],
                      hidden=cfg["hidden"], n_blocks=cfg["n_blocks"])
    model.load_state_dict(art["state_dict"])
    model.eval()

    # ─── Load corpus + features ────────────────────────────────────────
    print("loading corpus ...")
    df, _ = load_with_labels(csv_dir=args.csv_dir, manifest=args.manifest_dir,
                             drop_unlabeled=False, skip_warmup_rows=30)
    print(f"  {len(df)} rows")
    X, _ = build_features(
        df.drop(columns=[c for c in df.columns if c.startswith("__")]),
        include_deltas=True, schema=schema)
    Xn = ((X - mu) / sd).astype(np.float32)

    # ─── Score every frame for which a full SEQ_LEN lookback exists ────
    seq_len = cfg["seq_len"]
    file_ids = df["__file_id"].to_numpy()
    valid = np.zeros(len(df), dtype=bool)
    for t in range(seq_len, len(df)):
        if file_ids[t] == file_ids[t - seq_len]:
            valid[t] = True
    valid_t = np.where(valid)[0]
    print(f"scoring {len(valid_t)} frames (have full lookback) ...")

    mse = np.full(len(df), np.nan, dtype=np.float64)
    t1 = time.time()
    with torch.no_grad():
        for batch_start in range(0, len(valid_t), args.batch_size):
            ts = valid_t[batch_start:batch_start + args.batch_size]
            x_batch = np.stack([Xn[t - seq_len:t] for t in ts]).astype(np.float32)
            y_batch = Xn[ts].astype(np.float32)
            xb = torch.from_numpy(x_batch)
            yb = torch.from_numpy(y_batch)
            yhat = model(xb).numpy()
            mse[ts] = ((yhat - y_batch) ** 2).mean(axis=1)
            if batch_start % (args.batch_size * 50) == 0:
                pct = (batch_start + len(ts)) / len(valid_t) * 100
                print(f"  {batch_start + len(ts):>6}/{len(valid_t)} ({pct:.1f}%)")
    print(f"  scored in {time.time()-t1:.1f}s")

    # ─── Build output frame ─────────────────────────────────────────────
    out = pd.DataFrame({
        "file_id": file_ids,
        "row_idx": df["__row_idx"].to_numpy(),
        "attack_id": df["__attack_id"].fillna("").astype(str).to_numpy(),
        "corruption_window": df["__corruption_window"].astype(int).to_numpy(),
        "scenario": df["__scenario"].astype(str).to_numpy(),
        "mode": df["__adcs_mode"].astype(str).to_numpy(),
        "tcn_mse": mse,
    })
    out_csv = os.path.join(args.out, "tcn_scores.csv")
    out.to_csv(out_csv, index=False)
    print(f"saved -> {out_csv}")

    # ─── Per-class AUCPR ─────────────────────────────────────────────────
    from sklearn.metrics import average_precision_score
    scored = out.dropna(subset=["tcn_mse"]).copy()
    in_scenario = scored["scenario"] != "unlabeled"
    aucpr = {}
    for cls in sorted(set(scored["attack_id"]) - {""}):
        # Binary task: is this row in cls's corruption window?
        y_true = ((scored["attack_id"] == cls) & (scored["corruption_window"] == 1)).astype(int)
        # Use rows in any scenario or attack window as the eval set; exclude unlabeled
        mask = in_scenario.to_numpy()
        if y_true[mask].sum() < 10:
            aucpr[cls] = {"aucpr": None, "n_positive": int(y_true[mask].sum()),
                          "n_total": int(mask.sum()), "note": "<10 positives, skipped"}
            continue
        ap = average_precision_score(y_true[mask], scored["tcn_mse"][mask])
        aucpr[cls] = {"aucpr": float(ap), "n_positive": int(y_true[mask].sum()),
                      "n_total": int(mask.sum())}
    out_json = os.path.join(args.out, "tcn_aucpr_per_class.json")
    with open(out_json, "w") as f:
        json.dump(aucpr, f, indent=2)
    print(f"saved -> {out_json}")

    # ─── Comparison vs v3 XGBoost F1 ─────────────────────────────────────
    v3_cal = None
    if os.path.exists(args.v3_cal):
        v3_cal = json.load(open(args.v3_cal))

    print()
    print(f"{'class':<22} {'TCN AUCPR':>10} {'v3 F1 (LOIO mean)':>20} {'Δ':>6}")
    print("-" * 65)
    if v3_cal:
        per_class = {r["class"]: r for r in v3_cal["per_class_variance"]}
    else:
        per_class = {}
    for cls in sorted(aucpr.keys()):
        a = aucpr[cls]
        if a["aucpr"] is None:
            print(f"{cls:<22} {'(skip)':>10} {a.get('note', ''):>20}")
            continue
        ap = a["aucpr"]
        v3_f1 = per_class.get(cls, {}).get("mean_f1", None)
        delta_str = f"{ap - v3_f1:+.3f}" if v3_f1 is not None else "?"
        v3_str = f"{v3_f1:.3f}" if v3_f1 is not None else "?"
        print(f"{cls:<22} {ap:>10.3f} {v3_str:>20} {delta_str:>6}")

    print(f"\ntotal: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
