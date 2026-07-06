#!/usr/bin/env python3
"""Phase 4 v2 — score every row of the corpus through all 12 per-subsystem
TCNs and emit a 12-column MSE matrix joined to file_id + row_idx.

Output:
  - `tcn_per_subsystem_scores.csv` with columns
    [file_id, row_idx, mode, attack_id, corruption_window, scenario,
     ADCS_mse, CFE_EVS_mse, EPS_mse, ..., CFE_TIME_mse]
    where each `*_mse` is the per-subsystem prediction error.

These 12 MSEs become the additional features for v5 XGBoost.

Usage:
    python3 components/onair/training/eval_temporal_per_subsystem.py \\
        --model data/onair/models/tcn_per_subsystem_v1.pkl \\
        --csv-dir /tmp/xgb_train_corpus_v3/csv \\
        --manifest-dir /tmp/xgb_train_corpus_v3/scenarios \\
        --out /tmp/tcn_subsys_eval/
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
except ImportError:
    print("ERROR: PyTorch not installed.")
    sys.exit(1)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels
from features import build_features
from train_temporal_per_subsystem import SubsystemTCN, SEQ_LEN


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True)
    p.add_argument("--csv-dir", required=True)
    p.add_argument("--manifest-dir", required=True)
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--batch-size", type=int, default=512)
    args = p.parse_args()

    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)

    with open(args.model, "rb") as f:
        art = pickle.load(f)
    schema = art["schema"]
    mu = art["feature_mu"]
    sd = art["feature_sd"]
    seq_len = art["seq_len"]
    groups = art["groups"]
    print(f"loaded v{art.get('version', '?')} with {len(groups)} subsystem TCNs")
    for gname, g in groups.items():
        print(f"  {gname:<12} {g['n_features']:>4} features, "
              f"hidden={g['hidden']}, val_loss={g['best_val_loss']:.5f}")

    print("\nloading corpus + building features ...")
    df, _ = load_with_labels(csv_dir=args.csv_dir, manifest=args.manifest_dir,
                             drop_unlabeled=False, skip_warmup_rows=30)
    X, _ = build_features(
        df.drop(columns=[c for c in df.columns if c.startswith("__")]),
        include_deltas=True, schema=schema)
    Xn = np.clip((X.astype(np.float64) - mu) / sd, -50.0, 50.0).astype(np.float32)
    print(f"  Xn={Xn.shape}")

    file_ids = df["__file_id"].to_numpy()
    valid = np.zeros(len(df), dtype=bool)
    for t in range(seq_len, len(df)):
        if file_ids[t] == file_ids[t - seq_len]:
            valid[t] = True
    valid_t = np.where(valid)[0]
    print(f"  {len(valid_t)} rows with full lookback")

    # Reconstruct each per-subsystem TCN, score the corpus.
    mse_per_group: dict[str, np.ndarray] = {}
    for gname, g in groups.items():
        t1 = time.time()
        col_idx = np.array(g["feature_indices"], dtype=np.int64)
        model = SubsystemTCN(g["n_features"], g["hidden"], g["n_blocks"])
        model.load_state_dict(g["state_dict"])
        model.eval()
        Xg = Xn[:, col_idx]  # (n_rows, n_features_group)
        mse = np.full(len(df), np.nan, dtype=np.float64)
        with torch.no_grad():
            for bstart in range(0, len(valid_t), args.batch_size):
                ts = valid_t[bstart:bstart + args.batch_size]
                xb = torch.from_numpy(
                    np.stack([Xg[t - seq_len:t] for t in ts]).astype(np.float32))
                yb = Xg[ts]
                yhat = model(xb).numpy()
                mse[ts] = ((yhat - yb) ** 2).mean(axis=1)
        mse_per_group[gname] = mse
        print(f"  {gname:<12} scored in {time.time()-t1:.1f}s")

    # Build output dataframe
    out = pd.DataFrame({
        "file_id": file_ids,
        "row_idx": df["__row_idx"].to_numpy(),
        "attack_id": df["__attack_id"].fillna("").astype(str).to_numpy(),
        "corruption_window": df["__corruption_window"].astype(int).to_numpy(),
        "scenario": df["__scenario"].astype(str).to_numpy(),
        "mode": df["__adcs_mode"].astype(str).to_numpy(),
    })
    for gname, mse in mse_per_group.items():
        out[f"{gname}_mse"] = mse
    out_csv = os.path.join(args.out, "tcn_per_subsystem_scores.csv")
    out.to_csv(out_csv, index=False)
    print(f"\nsaved -> {out_csv}")

    # Per-subsystem AUCPR for the binary "any attack" task
    from sklearn.metrics import average_precision_score
    in_scn = (out["scenario"] != "unlabeled").to_numpy()
    y_attack = ((out["attack_id"] != "") & (out["corruption_window"] == 1)).to_numpy()
    aucpr = {}
    for gname in groups:
        col = out[f"{gname}_mse"].to_numpy()
        mask = in_scn & ~np.isnan(col)
        if mask.sum() == 0 or y_attack[mask].sum() < 10:
            aucpr[gname] = None
            continue
        ap = average_precision_score(y_attack[mask], col[mask])
        aucpr[gname] = float(ap)

    print(f"\nPer-subsystem binary anomaly AUCPR (any attack vs nominal):")
    for g in sorted(aucpr, key=lambda k: -(aucpr[k] or 0)):
        v = aucpr[g]
        print(f"  {g:<12} {v:.3f}" if v is not None else f"  {g:<12} (skip)")

    with open(os.path.join(args.out, "tcn_aucpr_per_subsystem.json"), "w") as f:
        json.dump(aucpr, f, indent=2)
    print(f"\ntotal: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
