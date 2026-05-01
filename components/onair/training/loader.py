"""Load OnAIR security CSVs into a single pandas DataFrame.

The CSV writer in `csv_output_plugin.py` rotates every 1000 rows. Headers are
identical across files (same OnAIR config + tlm.json). Rows received before the
bytes-decoding fix have `b'X'` reprs and embedded-comma misalignment; those
files are skipped.

Manifest-aware loading (`load_with_labels`) tags each row with the scenario
that produced it, by mapping CSV-filename timestamps to the time windows in
the orchestrator's manifest_*.json.
"""

from __future__ import annotations

import csv
import datetime as dt
import glob
import json
import os
import re
from dataclasses import dataclass

import pandas as pd

DEFAULT_CSV_DIR = "fsw/build/exe/cpu1/data/onair/csv"
EXPECTED_COLS = 273
_BYTE_REPR = re.compile(r"\bb'")
# csv_out_2026-04-30T20-31-10-172666_pid8.csv
_CSV_TS = re.compile(r"csv_out_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d+)_pid")


@dataclass
class LoadStats:
    files_total: int
    files_kept: int
    files_skipped_leaks: int
    files_skipped_alignment: int
    rows: int


def _file_is_clean(path: str) -> tuple[bool, str]:
    with open(path) as f:
        contents = f.read()
    if _BYTE_REPR.search(contents):
        return False, "byte_repr_leak"
    with open(path) as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if len(row) != EXPECTED_COLS:
                return False, "row_misalignment"
    return True, "ok"


def list_clean_csvs(csv_dir: str) -> tuple[list[str], LoadStats]:
    paths = sorted(glob.glob(os.path.join(csv_dir, "*.csv")))
    kept: list[str] = []
    skip_leaks = 0
    skip_align = 0
    rows_kept = 0
    for p in paths:
        ok, why = _file_is_clean(p)
        if not ok:
            if why == "byte_repr_leak":
                skip_leaks += 1
            else:
                skip_align += 1
            continue
        kept.append(p)
        with open(p) as f:
            rows_kept += sum(1 for _ in f) - 1
    stats = LoadStats(
        files_total=len(paths),
        files_kept=len(kept),
        files_skipped_leaks=skip_leaks,
        files_skipped_alignment=skip_align,
        rows=rows_kept,
    )
    return kept, stats


def load(csv_dir: str = DEFAULT_CSV_DIR) -> tuple[pd.DataFrame, LoadStats]:
    """Concatenate all clean CSVs.

    Adds two bookkeeping columns prefixed with `__` so feature engineering can
    skip them:
        __file_id  - source file basename, used to mask deltas at file boundaries
        __row_idx  - row index within the source file
    """
    files, stats = list_clean_csvs(csv_dir)
    if not files:
        raise FileNotFoundError(f"No clean CSVs found under {csv_dir}")

    frames = []
    for path in files:
        df = pd.read_csv(path, dtype=str, na_filter=False, low_memory=False)
        df.insert(0, "__row_idx", range(len(df)))
        df.insert(0, "__file_id", os.path.basename(path))
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    return out, stats


def _parse_csv_filename_ts(path: str) -> dt.datetime | None:
    """Extract the file-rotation start time from a csv_out_<ts>_pid<N>.csv name.

    The CSV plugin uses `datetime.now().strftime('%Y-%m-%dT%H-%M-%S-%f')`
    inside the FSW container, which runs in UTC by default. We treat the
    parsed timestamp as UTC.
    """
    m = _CSV_TS.search(os.path.basename(path))
    if not m:
        return None
    raw = m.group(1)
    # Format: 2026-04-30T20-31-10-172666 → split off the micros
    head, micro = raw.rsplit("-", 1)
    try:
        when = dt.datetime.strptime(head, "%Y-%m-%dT%H-%M-%S")
        when = when.replace(microsecond=int(micro)).replace(tzinfo=dt.timezone.utc)
        return when
    except ValueError:
        return None


def _load_manifest(manifest_path: str) -> list[dict]:
    """Read one orchestrator manifest and return its scenario windows."""
    with open(manifest_path) as f:
        m = json.load(f)
    out = []
    for s in m.get("scenarios", []):
        try:
            start = dt.datetime.fromisoformat(s["start_utc"]).replace(tzinfo=dt.timezone.utc)
            end = dt.datetime.fromisoformat(s["end_utc"]).replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            continue
        out.append({"name": s["name"], "start": start, "end": end})
    return out


def _resolve_manifest_paths(manifest: str | list[str]) -> list[str]:
    """Accept a path (file or directory) or a list of paths; return file paths.

    Directory inputs are globbed for `manifest_*.json`, excluding `*_dryrun*.json`.
    """
    if isinstance(manifest, list):
        return list(manifest)
    if os.path.isdir(manifest):
        all_paths = sorted(glob.glob(os.path.join(manifest, "manifest_*.json")))
        return [p for p in all_paths if "_dryrun" not in os.path.basename(p)]
    return [manifest]


def _load_manifests(manifest: str | list[str]) -> list[dict]:
    """Merge scenario windows from one or more manifest files."""
    out: list[dict] = []
    for path in _resolve_manifest_paths(manifest):
        out.extend(_load_manifest(path))
    return out


def _scenario_for_file(file_ts: dt.datetime, scenarios: list[dict]) -> str | None:
    """Return the scenario name whose time window contains file_ts, else None."""
    for s in scenarios:
        if s["start"] <= file_ts <= s["end"]:
            return s["name"]
    return None


def load_with_labels(
    csv_dir: str = DEFAULT_CSV_DIR,
    manifest: str | list[str] = None,
    *,
    drop_unlabeled: bool = True,
) -> tuple[pd.DataFrame, LoadStats]:
    """Load CSVs and attach a `__scenario` column based on the manifest(s).

    `manifest` accepts:
      - path to a single manifest_*.json
      - path to a directory (globs `manifest_*.json`, skips `*_dryrun*`)
      - a list of paths

    A file's start time (parsed from its filename) determines its scenario.
    Files outside any scenario window get `__scenario = "unlabeled"`.

    With `drop_unlabeled=True` (default), unlabeled rows are filtered out — the
    cFS state during uncontrolled time is operationally ambiguous (autonomous
    SCH ticks, residual transients from prior runs, etc.), so calling it
    "nominal" injects a label-by-assumption into training.
    """
    if not manifest:
        raise ValueError("manifest is required for load_with_labels")
    scenarios = _load_manifests(manifest)
    df, stats = load(csv_dir)

    # File-level scenario assignment
    file_to_scenario: dict[str, str] = {}
    for fp in df["__file_id"].unique():
        ts = _parse_csv_filename_ts(fp)
        name = _scenario_for_file(ts, scenarios) if ts else None
        file_to_scenario[fp] = name or "unlabeled"

    df["__scenario"] = df["__file_id"].map(file_to_scenario)
    if drop_unlabeled:
        before = len(df)
        df = df[df["__scenario"] != "unlabeled"].reset_index(drop=True)
        stats = LoadStats(
            files_total=stats.files_total,
            files_kept=df["__file_id"].nunique(),
            files_skipped_leaks=stats.files_skipped_leaks,
            files_skipped_alignment=stats.files_skipped_alignment,
            rows=len(df),
        )
        print(f"  dropped {before - len(df)} unlabeled rows; kept {len(df)} labeled rows")
    return df, stats


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--csv-dir", default=DEFAULT_CSV_DIR)
    p.add_argument("--manifest", default=None,
                   help="Manifest JSON, a directory of manifests, or a comma-separated list. "
                        "Tags each row with __scenario.")
    p.add_argument("--keep-unlabeled", action="store_true",
                   help="Keep rows outside scenario windows (default: drop them)")
    args = p.parse_args()
    if args.manifest:
        manifest = args.manifest.split(",") if "," in args.manifest else args.manifest
        df, stats = load_with_labels(args.csv_dir, manifest,
                                     drop_unlabeled=not args.keep_unlabeled)
    else:
        df, stats = load(args.csv_dir)
    print(f"loaded {stats.files_kept}/{stats.files_total} files, {stats.rows} rows")
    print(f"  skipped: leaks={stats.files_skipped_leaks} align={stats.files_skipped_alignment}")
    print(f"  shape: {df.shape}")
    print(f"  columns (first 8): {list(df.columns[:8])}")
    if "__scenario" in df.columns:
        print("  scenario distribution:")
        for name, n in df["__scenario"].value_counts().items():
            print(f"    {name}: {n} rows")
