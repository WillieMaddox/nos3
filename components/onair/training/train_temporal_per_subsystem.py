#!/usr/bin/env python3
"""Phase 4 v2 — train 12 per-subsystem TCNs in sequence.

Loads the corpus + builds features ONCE, then loops over 12 subsystem
groups, slicing the feature matrix per group and training one TCN per
group. Saves all 12 to a single dict pickle for downstream eval.

Subsystem groups (894 features partitioned exactly):
  ADCS       306 — ADCS_HK + ADCS_GNC + ADCS_DI + ADCS_DO
  CFE_EVS    164 — CFE_EVS + CFE_EVS_HK
  EPS         72
  SC          70
  CFE_ES      68
  CFE_SB      46 — CFE_SB + CFE_SB_SUBS + SBN
  SCH         43
  ACTUATORS   38 — RW + THRUSTER
  CFE_TBL     30
  RADIO       22 — RADIO_HK + RADIO_DEV
  NOVATEL     22 — NOVATEL_HK + NOVATEL
  CFE_TIME    13

Architecture tiers:
  Large (≥150): hidden=128, n_blocks=4
  Medium (60-149): hidden=64, n_blocks=3
  Small (20-59): hidden=32, n_blocks=3
  Tiny (<20): hidden=16, n_blocks=2

Estimated CPU training: ~2 hr sequential for all 12. Output pickle is
~5-10 MB.

Usage:
    python3 components/onair/training/train_temporal_per_subsystem.py \\
        --csv-dir /tmp/xgb_train_corpus_v3/csv \\
        --manifest-dir /tmp/xgb_train_corpus_v3/scenarios \\
        --out data/onair/models/tcn_per_subsystem_v1.pkl \\
        --epochs 20 --batch-size 256
"""
from __future__ import annotations

import argparse
import os
import pickle
import re
import sys
import time

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
except ImportError:
    print("ERROR: PyTorch not installed.")
    sys.exit(1)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
from loader import load_with_labels
from features import build_features
from train_temporal import TCNBlock, _build_valid_target_indices

SEQ_LEN = 60


# ─── Subsystem group definitions ─────────────────────────────────────
# Each group lists the feature-prefix patterns it contains. The first
# token of feature_names (or after the `d_` delta prefix) must match
# one of the listed prefixes. Order matters only for display; matching
# is exhaustive across all prefixes.
SUBSYSTEM_GROUPS = {
    "ADCS":      ["ADCS_HK", "ADCS_GNC", "ADCS_DI", "ADCS_DO"],
    "CFE_EVS":   ["CFE_EVS", "CFE_EVS_HK"],
    "EPS":       ["EPS"],
    "SC":        ["SC"],
    "CFE_ES":    ["CFE_ES"],
    "CFE_SB":    ["CFE_SB", "CFE_SB_SUBS", "SBN"],
    "SCH":       ["SCH"],
    "ACTUATORS": ["RW", "THRUSTER"],
    "CFE_TBL":   ["CFE_TBL"],
    "RADIO":     ["RADIO_HK", "RADIO_DEV"],
    "NOVATEL":   ["NOVATEL_HK", "NOVATEL"],
    "CFE_TIME":  ["CFE_TIME"],
}


def _feature_prefix(name: str) -> str:
    """Strip optional 'd_' delta marker and return the first prefix token."""
    base = name[2:] if name.startswith("d_") else name
    return re.split(r"[.\[]", base, 1)[0]


def _build_group_indices(feature_names: list[str]) -> dict[str, list[int]]:
    """Map each subsystem group → list of indices into the 894-feature vector.

    Each feature belongs to exactly one group (partition). Raises if any
    feature can't be assigned or if a feature would match multiple groups.
    """
    # Build prefix → group map. NOTE: must be unambiguous — no overlapping prefixes
    # except parent/child (e.g. "CFE_EVS" + "CFE_EVS_HK"). For those we want the
    # MORE SPECIFIC prefix to win, so we sort prefixes by length descending.
    prefix_to_group: dict[str, str] = {}
    for group, prefixes in SUBSYSTEM_GROUPS.items():
        for p in prefixes:
            assert p not in prefix_to_group, f"prefix {p!r} declared in multiple groups"
            prefix_to_group[p] = group

    sorted_prefixes = sorted(prefix_to_group.keys(), key=len, reverse=True)

    groups: dict[str, list[int]] = {g: [] for g in SUBSYSTEM_GROUPS}
    unassigned: list[str] = []
    for i, fn in enumerate(feature_names):
        base = fn[2:] if fn.startswith("d_") else fn
        matched = None
        for p in sorted_prefixes:
            if base == p or base.startswith(p + ".") or base.startswith(p + "["):
                matched = prefix_to_group[p]
                break
        if matched is None:
            unassigned.append(fn)
        else:
            groups[matched].append(i)
    if unassigned:
        raise ValueError(f"could not assign these features: {unassigned[:10]} "
                         f"({len(unassigned)} total)")
    total = sum(len(v) for v in groups.values())
    assert total == len(feature_names), \
        f"partition mismatch: {total} vs {len(feature_names)}"
    return groups


def _arch_tier(n: int) -> tuple[int, int]:
    """Return (hidden_channels, n_blocks) for a group of n features."""
    if n >= 150: return 128, 4
    if n >= 60: return 64, 3
    if n >= 20: return 32, 3
    return 16, 2


class SubsystemTCN(nn.Module):
    """One TCN for a single subsystem. Input: (B, T, F_sub). Output: (B, F_sub).

    Architecture matches GlobalTCN except hidden/n_blocks scale to the
    group's feature count."""
    def __init__(self, n_features: int, hidden: int, n_blocks: int):
        super().__init__()
        self.input_proj = nn.Conv1d(n_features, hidden, kernel_size=1)
        self.blocks = nn.ModuleList([
            TCNBlock(hidden, dilation=2**i) for i in range(n_blocks)
        ])
        self.output_proj = nn.Conv1d(hidden, n_features, kernel_size=1)

    def forward(self, x):  # x: (B, T, F)
        x = x.transpose(1, 2)
        x = self.input_proj(x)
        for block in self.blocks:
            x = block(x)
        x = self.output_proj(x)
        return x[:, :, -1]


class GroupSequenceDataset(Dataset):
    """Wraps the FULL Xn array + valid_target_idx + a feature-column subset.
    Yields (seq, target) where both are restricted to the subset columns."""
    def __init__(self, Xn: np.ndarray, valid_targets: np.ndarray,
                 col_idx: np.ndarray, seq_len: int = SEQ_LEN):
        self.X = torch.from_numpy(Xn[:, col_idx]).float()
        self.targets = valid_targets
        self.seq_len = seq_len

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, i):
        t = int(self.targets[i])
        x = self.X[t - self.seq_len:t]
        y = self.X[t]
        return x, y


def train_one_group(group_name: str, col_idx: list[int], Xn: np.ndarray,
                    valid_targets: np.ndarray, val_idx: np.ndarray,
                    train_idx: np.ndarray, args, device) -> dict:
    """Train one subsystem TCN; return the artifact dict for that group."""
    n_features = len(col_idx)
    hidden, n_blocks = _arch_tier(n_features)
    print(f"\n  [{group_name}] {n_features} features → hidden={hidden}, n_blocks={n_blocks}")

    col_arr = np.array(col_idx, dtype=np.int64)
    train_ds = GroupSequenceDataset(Xn, train_idx, col_arr, SEQ_LEN)
    val_ds = GroupSequenceDataset(Xn, val_idx, col_arr, SEQ_LEN)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              num_workers=2, pin_memory=False)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            num_workers=2, pin_memory=False)

    model = SubsystemTCN(n_features, hidden, n_blocks).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  [{group_name}] params={n_params}, train={len(train_ds)}, val={len(val_ds)}")

    best_val = float("inf")
    best_state = None
    history = []
    for ep in range(args.epochs):
        model.train()
        tr_loss = 0.0; nb = 0; t_ep = time.time()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            yhat = model(xb)
            loss = F.mse_loss(yhat, yb)
            loss.backward()
            opt.step()
            tr_loss += float(loss.item()); nb += 1
        tr_loss /= max(1, nb)
        model.eval()
        val_loss = 0.0; nv = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(device), yb.to(device)
                yhat = model(xb)
                val_loss += float(F.mse_loss(yhat, yb).item()); nv += 1
        val_loss /= max(1, nv)
        history.append({"epoch": ep, "train": tr_loss, "val": val_loss,
                        "elapsed_s": time.time() - t_ep})
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    print(f"  [{group_name}] best val_loss={best_val:.5f} after {args.epochs} epochs "
          f"(total {sum(h['elapsed_s'] for h in history):.0f}s)")
    return {
        "state_dict": best_state,
        "feature_indices": col_arr.tolist(),
        "n_features": n_features,
        "hidden": hidden,
        "n_blocks": n_blocks,
        "best_val_loss": float(best_val),
        "history": history,
        "n_params": n_params,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv-dir", required=True)
    p.add_argument("--manifest-dir", required=True)
    p.add_argument("--out", required=True, help="output dict pickle")
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--device", default="cpu")
    p.add_argument("--max-sequences", type=int, default=None)
    p.add_argument("--groups", nargs="+", default=None,
                   help="Restrict to specific groups (default: all 12)")
    args = p.parse_args()

    t0 = time.time()
    print(f"loading corpus from {args.csv_dir} ...")
    df, _ = load_with_labels(csv_dir=args.csv_dir, manifest=args.manifest_dir,
                             drop_unlabeled=False, skip_warmup_rows=30)
    print(f"  {len(df)} rows × {len(df.columns)} cols")

    v5_path = "data/onair/models/iforest_per_mode_v5_invariant_bolstered.pkl"
    with open(v5_path, "rb") as f:
        schema = pickle.load(f)["schema"]
    feature_names = schema["feature_names"]

    print("building feature matrix ...")
    t1 = time.time()
    X, _ = build_features(
        df.drop(columns=[c for c in df.columns if c.startswith("__")]),
        include_deltas=True, schema=schema)
    print(f"  X={X.shape} in {time.time()-t1:.1f}s")

    # Standardize per-feature on nominal mask (same as global TCN).
    in_corr = df["__corruption_window"].to_numpy()
    in_scn = (df["__scenario"].astype(str) != "unlabeled").to_numpy()
    nominal_mask = (~in_corr) & in_scn
    X64 = X.astype(np.float64)
    mu = X64[nominal_mask].mean(axis=0)
    sd = X64[nominal_mask].std(axis=0) + 1e-6
    Xn = np.clip((X64 - mu) / sd, -50.0, 50.0).astype(np.float32)
    print(f"normalized on {nominal_mask.sum()} nominal rows; clipped ±50σ")

    # Build per-group column indices.
    groups = _build_group_indices(feature_names)
    print(f"\nsubsystem groups (feature counts):")
    for g in SUBSYSTEM_GROUPS:
        print(f"  {g:<12} {len(groups[g]):>4}")

    # Sequence indices — shared across all groups (a "valid" sequence is
    # valid for ALL groups since the validity criterion is on rows, not columns).
    print(f"\nbuilding valid-target indices (seq_len={SEQ_LEN}) ...")
    t1 = time.time()
    valid_targets = _build_valid_target_indices(df, SEQ_LEN)
    print(f"  {len(valid_targets)} valid sequences in {time.time()-t1:.1f}s")
    if args.max_sequences and len(valid_targets) > args.max_sequences:
        valid_targets = np.random.RandomState(42).choice(
            valid_targets, args.max_sequences, replace=False)
        print(f"  capped to {len(valid_targets)} sequences")

    rng = np.random.RandomState(42)
    idx = rng.permutation(len(valid_targets))
    val_n = max(256, int(len(valid_targets) * 0.1))
    val_idx = valid_targets[idx[:val_n]]
    train_idx = valid_targets[idx[val_n:]]
    print(f"split: train={len(train_idx)}, val={len(val_idx)}")

    device = torch.device(args.device)
    selected = args.groups if args.groups else list(SUBSYSTEM_GROUPS.keys())
    out_dict: dict = {
        "groups": {},
        "feature_names": feature_names,
        "feature_mu": mu,
        "feature_sd": sd,
        "schema": schema,
        "seq_len": SEQ_LEN,
        "version": "tcn_per_subsystem_v1",
    }

    for gname in selected:
        col_idx = groups[gname]
        if not col_idx:
            print(f"  [{gname}] no features assigned — skipping")
            continue
        artifact = train_one_group(gname, col_idx, Xn, valid_targets,
                                   val_idx, train_idx, args, device)
        out_dict["groups"][gname] = artifact
        # Persist incrementally so a crash partway through doesn't lose work
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "wb") as f:
            pickle.dump(out_dict, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"  [{gname}] saved (incremental).")

    print(f"\ndone. trained {len(out_dict['groups'])} subsystems → {args.out}")
    print(f"total wallclock: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
