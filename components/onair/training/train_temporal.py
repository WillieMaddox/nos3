#!/usr/bin/env python3
"""Phase 4 — train a global TCN to predict next-frame telemetry from a
60-frame lookback. Anomaly score at inference is the per-frame prediction
MSE. Hundman 2018 style.

Training data: nominal-only frames from the 3-instance corpus
(2026-05-16, 2026-05-29 batch-1, 2026-05-29 batch-2). 75 CSVs.

Sequence semantics:
  - Input: x_t-59 ... x_t (60 frames)
  - Target: x_t+1 (next frame)
  - Sequences span ONE file_id only (no boundary crossing).
  - Sequences must be FULLY NOMINAL: 61-frame window with no
    corruption_window overlap, all frames in a scenario block.

Architecture: dilated causal Conv1d TCN.
  - 4 blocks, dilations [1, 2, 4, 8], kernel_size=3, hidden=128 channels.
  - Receptive field = 1 + 2 * (1+2+4+8) * (3-1)/2 ≈ 60.
  - Output: predicted x_t+1 (894-dim).

Usage:
    python3 components/onair/training/train_temporal.py \\
        --csv-dir /tmp/xgb_train_corpus_v3/csv \\
        --manifest-dir /tmp/xgb_train_corpus_v3/scenarios \\
        --out data/onair/models/tcn_global_v1.pkl \\
        --epochs 20 --batch-size 256

CPU training is feasible (~10-30 min per epoch on a global 894→894 model);
defer GPU until per-subsystem TCN architecture (v2).
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from pathlib import Path

import numpy as np

# Defer torch import until we know it's installed; clean error message otherwise.
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
except ImportError:
    print("ERROR: PyTorch not installed. Run:")
    print("  pip install --index-url https://download.pytorch.org/whl/cpu torch")
    sys.exit(1)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels
from features import build_features


SEQ_LEN = 60  # 60-frame lookback (~12s at 5 Hz)
HIDDEN = 128  # TCN channel count
N_BLOCKS = 4  # dilation = 2**i for i in 0..N_BLOCKS-1


class TCNBlock(nn.Module):
    """Causal dilated Conv1d block with residual.

    Input/output shape: (B, C, T). Uses left-padding for causality."""
    def __init__(self, channels: int, dilation: int, kernel_size: int = 3,
                 dropout: float = 0.1):
        super().__init__()
        pad = (kernel_size - 1) * dilation
        self.pad = pad
        self.conv1 = nn.Conv1d(channels, channels, kernel_size,
                               padding=0, dilation=dilation)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size,
                               padding=0, dilation=dilation)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        # Left-pad for causality, then conv
        x_pad = F.pad(x, (self.pad, 0))
        h = F.relu(self.conv1(x_pad))
        h = self.dropout(h)
        h_pad = F.pad(h, (self.pad, 0))
        h = F.relu(self.conv2(h_pad))
        h = self.dropout(h)
        return x + h  # residual


class GlobalTCN(nn.Module):
    """Predict x_{t+1} ∈ R^{n_features} from (x_{t-T+1}, …, x_t).

    Architecture: input projection → N dilated TCN blocks → output projection.
    Output is taken from the last time-step only."""
    def __init__(self, n_features: int = 894, hidden: int = HIDDEN,
                 n_blocks: int = N_BLOCKS):
        super().__init__()
        self.input_proj = nn.Conv1d(n_features, hidden, kernel_size=1)
        self.blocks = nn.ModuleList([
            TCNBlock(hidden, dilation=2**i) for i in range(n_blocks)
        ])
        self.output_proj = nn.Conv1d(hidden, n_features, kernel_size=1)

    def forward(self, x):  # x: (B, T, F)
        x = x.transpose(1, 2)  # (B, F, T) for Conv1d
        x = self.input_proj(x)
        for block in self.blocks:
            x = block(x)
        x = self.output_proj(x)  # (B, F, T)
        return x[:, :, -1]  # (B, F) — last-time prediction


class SequenceDataset(Dataset):
    """Wraps a (n_frames, n_features) array + a per-row "valid as target"
    mask. A target row t is valid if rows [t-SEQ_LEN .. t] all live in the
    same file_id AND in a nominal scenario row (no corruption overlap)."""
    def __init__(self, X: np.ndarray, valid_target_idx: np.ndarray,
                 seq_len: int = SEQ_LEN):
        self.X = torch.from_numpy(X).float()
        self.targets = valid_target_idx  # int array of valid t values
        self.seq_len = seq_len

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, i):
        t = int(self.targets[i])
        x = self.X[t - self.seq_len:t]   # (seq_len, F)
        y = self.X[t]                    # (F,)
        return x, y


def _build_valid_target_indices(df, seq_len: int) -> np.ndarray:
    """Find row indices t such that [t-seq_len .. t] are all in the same
    file_id AND all nominal (not in corruption_window, in scenario)."""
    file_ids = df["__file_id"].to_numpy()
    in_corr = df["__corruption_window"].to_numpy()
    in_scn = (df["__scenario"].astype(str) != "unlabeled").to_numpy()
    nominal = (~in_corr) & in_scn

    valid: list[int] = []
    n = len(df)
    for t in range(seq_len, n):
        if not nominal[t]:
            continue
        # Whole 61-frame window (lookback + target) must be nominal AND same file.
        win_nominal = bool(nominal[t - seq_len:t + 1].all())
        win_same_file = bool((file_ids[t - seq_len:t + 1] == file_ids[t]).all())
        if win_nominal and win_same_file:
            valid.append(t)
    return np.array(valid, dtype=np.int64)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", required=True)
    p.add_argument("--manifest-dir", required=True)
    p.add_argument("--out", required=True, help="Output .pkl path")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--device", default="cpu")
    p.add_argument("--max-sequences", type=int, default=None,
                   help="cap on training sequences (for smoke testing)")
    args = p.parse_args()

    t0 = time.time()
    print(f"loading corpus from {args.csv_dir} ...")
    df, _ = load_with_labels(csv_dir=args.csv_dir, manifest=args.manifest_dir,
                             drop_unlabeled=False, skip_warmup_rows=30)
    print(f"  {len(df)} rows × {len(df.columns)} cols, "
          f"file_ids={df['__file_id'].nunique()}")

    # Use v5 schema (894 features) for parity with v3 XGBoost + the deployed IF.
    v5_path = "data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl"
    with open(v5_path, "rb") as f:
        schema = pickle.load(f)["schema"]
    print(f"building features ...")
    t1 = time.time()
    X, _ = build_features(
        df.drop(columns=[c for c in df.columns if c.startswith("__")]),
        include_deltas=True, schema=schema)
    print(f"  X={X.shape} in {time.time()-t1:.1f}s")

    # Per-feature standardization on the nominal subset (avoids attack-tail leakage).
    # Use float64 for mu/sd to avoid float32 overflow on long-running counters
    # (e.g. CFE_TIME.SecondsSTCF reaches ~1.1B post-SET_TIME). Cast to float32
    # only for the normalized matrix passed to torch.
    in_corr = df["__corruption_window"].to_numpy()
    in_scn = (df["__scenario"].astype(str) != "unlabeled").to_numpy()
    nominal_mask = (~in_corr) & in_scn
    X64 = X.astype(np.float64)
    mu = X64[nominal_mask].mean(axis=0)
    sd = X64[nominal_mask].std(axis=0) + 1e-6
    Xn = np.clip((X64 - mu) / sd, -50.0, 50.0).astype(np.float32)
    print(f"normalized: mu/sd computed on {nominal_mask.sum()} nominal rows; "
          f"clipped to ±50σ")

    print(f"building valid-target-index list (seq_len={SEQ_LEN}) ...")
    t1 = time.time()
    valid_targets = _build_valid_target_indices(df, SEQ_LEN)
    print(f"  {len(valid_targets)} valid training sequences in {time.time()-t1:.1f}s")
    if args.max_sequences and len(valid_targets) > args.max_sequences:
        valid_targets = np.random.RandomState(42).choice(
            valid_targets, args.max_sequences, replace=False)
        print(f"  capped to {len(valid_targets)} sequences")

    # 90/10 train/val split
    rng = np.random.RandomState(42)
    idx = rng.permutation(len(valid_targets))
    val_n = max(256, int(len(valid_targets) * 0.1))
    val_idx = valid_targets[idx[:val_n]]
    train_idx = valid_targets[idx[val_n:]]
    print(f"split: train={len(train_idx)}, val={len(val_idx)}")

    train_ds = SequenceDataset(Xn, train_idx, SEQ_LEN)
    val_ds = SequenceDataset(Xn, val_idx, SEQ_LEN)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=2, pin_memory=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=2, pin_memory=False)

    device = torch.device(args.device)
    model = GlobalTCN(n_features=X.shape[1]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    print(f"\nmodel: {sum(p.numel() for p in model.parameters())} params, "
          f"device={device}")

    best_val = float("inf")
    history = []
    for epoch in range(args.epochs):
        model.train()
        tr_loss = 0.0; n_batches = 0; t_ep = time.time()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            yhat = model(xb)
            loss = F.mse_loss(yhat, yb)
            loss.backward()
            optimizer.step()
            tr_loss += float(loss.item()); n_batches += 1
        tr_loss /= max(1, n_batches)

        model.eval()
        val_loss = 0.0; n_v = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                yhat = model(xb)
                val_loss += float(F.mse_loss(yhat, yb).item()); n_v += 1
        val_loss /= max(1, n_v)
        elapsed = time.time() - t_ep
        history.append({"epoch": epoch, "train_loss": tr_loss,
                        "val_loss": val_loss, "elapsed_s": elapsed})
        print(f"  epoch {epoch+1:>2}/{args.epochs}  "
              f"train_loss={tr_loss:.5f}  val_loss={val_loss:.5f}  "
              f"({elapsed:.0f}s)")
        if val_loss < best_val:
            best_val = val_loss
            # Save best-by-val-loss checkpoint
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "wb") as f:
                pickle.dump({
                    "state_dict": model.state_dict(),
                    "config": {
                        "version": "tcn_v1",
                        "seq_len": SEQ_LEN,
                        "hidden": HIDDEN,
                        "n_blocks": N_BLOCKS,
                        "n_features": X.shape[1],
                        "epochs_trained": epoch + 1,
                        "best_val_loss": float(best_val),
                    },
                    "schema": schema,
                    "feature_mu": mu,  # float64 — counter values exceed float32 range
                    "feature_sd": sd,
                    "history": history,
                }, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f"\ndone. best val_loss={best_val:.5f}; saved → {args.out}")
    print(f"total: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
