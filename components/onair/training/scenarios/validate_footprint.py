#!/usr/bin/env python3
"""Offline attack-footprint validator (Track 2 helper).

Given a manifest path + the .md-declared footprint columns for one attack,
loads the single OnAIR CSV that pairs to the manifest (matched by start
timestamp) and dumps pre / attack-window / corruption-window / post slices
for each declared column. Used to apply the evaluation-provenance rule to
the 17 new IMP + DE-0003 catalog entries without firing up the FSW.

Usage:
    python validate_footprint.py \\
        --manifest data/onair/scenarios/manifest_2026-05-16T04-33-54Z.json \\
        --attack-id IMP-0001 \\
        --columns CFE_EVS_HK.CommandCounter CFE_ES.CommandCounter

The verdict at the bottom is a rough heuristic — eyeball the slice table
before trusting it.

Standalone implementation (no loader.load_with_labels). Reads just the one
CSV that pairs to the manifest by timestamp. Designed to be fast on the
full corpus (1 attack ≈ 1 s).
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "..", ".."))
DEFAULT_CSV_DIR = os.path.join(REPO_ROOT, "data", "onair", "csv")

# OnAIR's nominal frame rate; matches the loader.fallback_rate_hz default.
NOMINAL_SAMPLE_HZ = 5.0


def _parse_csv_ts(name: str) -> dt.datetime:
    """Decode a CSV filename timestamp like 2026-05-16T05-31-18-885586."""
    m = re.match(r"^csv_out_(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})"
                 r"(?:-(\d{1,6}))?_pid\d+\.csv$", os.path.basename(name))
    if not m:
        raise ValueError(f"unparseable CSV name: {name}")
    date, hr, mi, se, us = m.groups()
    us_str = (us or "0").ljust(6, "0")[:6]
    return dt.datetime.fromisoformat(
        f"{date}T{hr}:{mi}:{se}.{us_str}+00:00")


def _find_paired_csv(manifest_path: str, csv_dir: str,
                     pair_tolerance_s: float = 5.0) -> str:
    """Pick the CSV whose start time is closest to the manifest session_id.

    The CSV-start filename timestamp is typically a few hundred ms AFTER
    the manifest session_id (manifest sid captures run_attack.py start;
    OnAIR's CSV file is created moments later when the FSW pipeline
    finishes warm-up). A strict `<=` comparison would mismatch in that
    sub-second window. We pick the closest candidate within
    `pair_tolerance_s` of the manifest sid; if no candidate is within the
    tolerance we fall back to the latest one strictly before it.
    """
    with open(manifest_path) as f:
        d = json.load(f)
    sid = d["session_id"]  # 2026-05-16T05-31-19Z
    m = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})Z$", sid)
    if not m:
        raise SystemExit(f"unparseable session_id in {manifest_path}: {sid!r}")
    date, hr, mi, se = m.groups()
    sid_dt = dt.datetime.fromisoformat(f"{date}T{hr}:{mi}:{se}+00:00")
    candidates = sorted(glob.glob(os.path.join(csv_dir, "csv_out_*.csv")),
                        key=_parse_csv_ts)
    # Closest within tolerance (either side):
    in_window = [(abs((_parse_csv_ts(c) - sid_dt).total_seconds()), c)
                 for c in candidates
                 if abs((_parse_csv_ts(c) - sid_dt).total_seconds()) <= pair_tolerance_s]
    if in_window:
        in_window.sort()
        return in_window[0][1]
    # Fallback: latest CSV strictly before sid.
    matched = None
    for c in candidates:
        if _parse_csv_ts(c) <= sid_dt:
            matched = c
        else:
            break
    if matched is None:
        raise SystemExit(f"no CSV in {csv_dir} within {pair_tolerance_s}s of {sid}")
    return matched


def _infer_sample_rate(csv_path: str, manifest_path: str) -> float:
    """Infer the OnAIR effective frame rate from CSV row count + manifest extent.

    With run_attack_batch's stack_restart-per-attack flow, each CSV maps to
    a single attack session. The CSV ends shortly after the post-scenario
    completes, so `n_rows / (post_end - csv_start)` is a reasonable rate
    estimate. The 5 Hz nominal value from the soak code is wrong by 1.5-2x
    on these CSVs because the longer corruption-dwell extends the idle tail.
    """
    df_n = sum(1 for _ in open(csv_path)) - 1  # rows minus header
    csv_start = _parse_csv_ts(csv_path)
    with open(manifest_path) as f:
        d = json.load(f)
    scns = d.get("scenarios", [])
    if not scns:
        return NOMINAL_SAMPLE_HZ
    post_end_str = scns[-1].get("end_utc")
    if not post_end_str:
        return NOMINAL_SAMPLE_HZ
    post_end = dt.datetime.fromisoformat(post_end_str).replace(tzinfo=dt.timezone.utc)
    # Add the corruption-window tail (CSV usually continues writing through it).
    a = d.get("attacks", [])
    if a:
        ce = a[-1].get("corruption_end_utc")
        if ce:
            ce_dt = dt.datetime.fromisoformat(ce).replace(tzinfo=dt.timezone.utc)
            if ce_dt > post_end:
                post_end = ce_dt
    duration = (post_end - csv_start).total_seconds()
    if duration <= 0:
        return NOMINAL_SAMPLE_HZ
    rate = df_n / duration
    # Clamp to a sane range (avoid mis-pairing producing absurd rates).
    return max(0.5, min(rate, 20.0))


def _load_one_csv(csv_path: str, sample_hz: float = NOMINAL_SAMPLE_HZ) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    start = _parse_csv_ts(csv_path)
    df["__row_idx"] = np.arange(len(df))
    df["__time"] = pd.to_datetime(
        start.timestamp() + df["__row_idx"] / sample_hz, unit="s", utc=True)
    return df


def _attack_record(manifest_path: str, attack_id: str) -> dict:
    with open(manifest_path) as f:
        d = json.load(f)
    for a in d.get("attacks", []):
        if a["id"] == attack_id:
            # parse timestamps
            out = dict(a)
            out["start_utc"] = dt.datetime.fromisoformat(a["start_utc"]).replace(tzinfo=dt.timezone.utc)
            out["end_utc"] = dt.datetime.fromisoformat(a["end_utc"]).replace(tzinfo=dt.timezone.utc)
            ce = a.get("corruption_end_utc") or a["end_utc"]
            out["corruption_end_utc"] = dt.datetime.fromisoformat(ce).replace(tzinfo=dt.timezone.utc)
            return out
    raise SystemExit(f"attack_id {attack_id!r} not in {manifest_path}; "
                     f"available: {[a['id'] for a in d.get('attacks', [])]}")


def _slice_by_time(df: pd.DataFrame, start: dt.datetime,
                   end: dt.datetime) -> pd.DataFrame:
    times = df["__time"].dt.tz_convert("UTC")
    mask = (times >= start) & (times <= end)
    return df[mask]


def _slice_stats(series: pd.Series) -> dict:
    """Numeric summary of one column-slice."""
    s = pd.to_numeric(series.replace({"[0]": np.nan, "": np.nan}), errors="coerce")
    nonnan = s.dropna()
    if nonnan.empty:
        return {"n": len(series), "nonzero": 0, "min": None, "max": None,
                "first": series.iloc[0] if len(series) else None,
                "last": series.iloc[-1] if len(series) else None}
    return {
        "n": len(series),
        "nonzero": int((nonnan != 0).sum()),
        "min": float(nonnan.min()),
        "max": float(nonnan.max()),
        "first": float(nonnan.iloc[0]),
        "last": float(nonnan.iloc[-1]),
    }


def _is_array_col(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(5).tolist()
    return any(s.startswith("[") and "," in s for s in sample)


def validate(manifest_path: str, attack_id: str, columns: list[str],
             csv_dir: str = DEFAULT_CSV_DIR, verbose: bool = True,
             pre_seconds: float = 10.0) -> dict:
    """Return a verdict dict + per-column slice summaries for one attack.

    `pre_seconds` controls the pre-window length. Default 10 s — narrow enough
    that prior attacks/scenarios don't bleed into the baseline, wide enough
    that dual-buffered counters show at least 2-3 cycles. The corruption
    window is unbounded (attack_start → corruption_end), so a slow-acting
    counter advance will still be visible there even if the attack-window
    proper missed it (sub-frame timing slop)."""
    csv_path = _find_paired_csv(manifest_path, csv_dir)
    sample_hz = _infer_sample_rate(csv_path, manifest_path)
    df = _load_one_csv(csv_path, sample_hz=sample_hz)
    a = _attack_record(manifest_path, attack_id)
    pre = _slice_by_time(df,
                         a["start_utc"] - dt.timedelta(seconds=pre_seconds),
                         a["start_utc"])
    window = _slice_by_time(df, a["start_utc"], a["end_utc"])
    corr = _slice_by_time(df, a["start_utc"], a["corruption_end_utc"])
    post = _slice_by_time(df, a["corruption_end_utc"],
                         a["corruption_end_utc"] + dt.timedelta(seconds=60))

    slices = {"pre": pre, "attack_window": window,
              "corruption_window": corr, "post": post}

    if verbose:
        print(f"\n=== {attack_id} validation ===")
        print(f"  manifest: {os.path.basename(manifest_path)}")
        print(f"  CSV: {os.path.basename(csv_path)} ({len(df)} rows, "
              f"sample_hz={sample_hz:.2f})")
        print(f"  attack window: {a['start_utc']} → {a['end_utc']}")
        print(f"  corruption window: {a['start_utc']} → {a['corruption_end_utc']}")
        print(f"  slice sizes: pre={len(pre)} attack={len(window)} "
              f"corr={len(corr)} post={len(post)}")
        if len(corr) == 0:
            print(f"  WARNING: zero rows in corruption window — CSV may end before "
                  f"corruption_end ({a['corruption_end_utc']}); last CSV time = "
                  f"{df['__time'].iloc[-1]}")

    column_results: dict[str, dict] = {}
    for col in columns:
        if col not in df.columns:
            column_results[col] = {"status": "MISSING_COLUMN"}
            if verbose:
                print(f"\n  [{col}] NOT IN CSV")
            continue
        if _is_array_col(df[col]):
            column_results[col] = _validate_array_column(df, col, slices, verbose)
        else:
            column_results[col] = _validate_scalar_column(df, col, slices, verbose)

    perturbed = sum(1 for r in column_results.values() if r.get("status") == "PERTURBED")
    nochange = sum(1 for r in column_results.values() if r.get("status") == "NO_CHANGE")
    missing = sum(1 for r in column_results.values() if r.get("status") == "MISSING_COLUMN")
    declared = len(columns)

    if missing == declared:
        verdict = "INCONCLUSIVE — all declared columns absent from CSV"
    elif perturbed == 0:
        verdict = "FAIL — no declared column perturbed in window"
    elif perturbed == declared - missing:
        verdict = "PASS — every observable column perturbed"
    else:
        verdict = (f"PARTIAL — {perturbed}/{declared - missing} observable "
                   f"columns perturbed; {nochange} flat, {missing} not in CSV")
    if verbose:
        print(f"\n  VERDICT: {verdict}")
    return {"verdict": verdict, "columns": column_results,
            "csv": os.path.basename(csv_path)}


def _validate_scalar_column(df: pd.DataFrame, col: str,
                            slices: dict, verbose: bool) -> dict:
    stats = {k: _slice_stats(s[col]) for k, s in slices.items()}

    # Dual-buffer-aware perturbation: a column is PERTURBED if the corruption
    # window introduces ANY numeric value not seen in the pre window. Catches
    # monotonic counters (e.g., CommandCounter 0→1) and discrete state changes
    # (e.g., ClockStateFlags X→Y), and is robust to the dual-buffer 0/N flip
    # that makes last-value comparison unreliable. Also catches the "value
    # jump" case where pre_max > corr_max (RESET to lower value).
    def _values_set(sub: pd.DataFrame) -> set[float]:
        s = pd.to_numeric(sub[col].replace({"[0]": np.nan, "": np.nan}),
                          errors="coerce").dropna()
        return set(float(v) for v in s.unique())

    pre_vals = _values_set(slices["pre"])
    corr_vals = _values_set(slices["corruption_window"])
    window_vals = _values_set(slices["attack_window"])
    post_vals = _values_set(slices["post"])
    novel_in_corr = corr_vals - pre_vals
    novel_in_window = window_vals - pre_vals
    lost_in_corr = pre_vals - corr_vals  # value seen in pre but never in corr

    perturbed = bool(novel_in_corr or novel_in_window or lost_in_corr)
    status = "PERTURBED" if perturbed else "NO_CHANGE"
    if verbose:
        print(f"\n  [{col}]  ({status})")
        for label, st in stats.items():
            print(f"    {label:>17}: n={st['n']:>3} first={st['first']!s:>12} "
                  f"last={st['last']!s:>12} min={st['min']!s:>12} max={st['max']!s:>12}")
        if novel_in_window:
            print(f"    novel in attack-window: {sorted(novel_in_window)[:5]}")
        if novel_in_corr - novel_in_window:
            print(f"    novel in corruption-window only: "
                  f"{sorted(novel_in_corr - novel_in_window)[:5]}")
        if lost_in_corr:
            print(f"    pre-values absent from corruption-window: "
                  f"{sorted(lost_in_corr)[:5]}")
    return {"status": status, "slices": stats,
            "novel_in_corr": sorted(novel_in_corr)[:5]}


def _validate_array_column(df: pd.DataFrame, col: str,
                           slices: dict, verbose: bool) -> dict:
    def _vals(sub: pd.DataFrame) -> set[str]:
        return set(sub[col].astype(str).dropna().unique().tolist())
    pre_vals = _vals(slices["pre"])
    window_vals = _vals(slices["attack_window"]) | _vals(slices["corruption_window"])
    post_vals = _vals(slices["post"])
    new_in_window = window_vals - pre_vals
    perturbed = bool(new_in_window)
    status = "PERTURBED" if perturbed else "NO_CHANGE"
    if verbose:
        def _head(s, n=3):
            return sorted(s)[:n]
        print(f"\n  [{col}]  array-col ({status})")
        print(f"    pre unique (head):     {_head(pre_vals)}")
        print(f"    window unique (head):  {_head(window_vals)}")
        print(f"    new-in-window (head):  {_head(new_in_window)}")
        print(f"    post unique (head):    {_head(post_vals)}")
    return {"status": status, "new_in_window": sorted(new_in_window)[:5]}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--manifest", required=True,
                   help="Path to manifest_*.json containing the attack record")
    p.add_argument("--attack-id", required=True,
                   help="SPARTA technique id as recorded in the manifest (e.g. IMP-0001)")
    p.add_argument("--columns", nargs="+", required=True,
                   help="Declared-footprint column names (CSV header strings)")
    p.add_argument("--csv-dir", default=DEFAULT_CSV_DIR,
                   help=f"OnAIR CSV directory (default: {DEFAULT_CSV_DIR})")
    p.add_argument("--quiet", action="store_true",
                   help="Only print the verdict line + JSON summary")
    args = p.parse_args()

    result = validate(args.manifest, args.attack_id, args.columns,
                      csv_dir=args.csv_dir, verbose=not args.quiet)
    if args.quiet:
        print(json.dumps({"attack_id": args.attack_id,
                          "verdict": result["verdict"],
                          "csv": result["csv"]}))


if __name__ == "__main__":
    main()
