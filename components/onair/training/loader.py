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
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_CSV_DIR = "data/onair/csv"
# Each CSV is self-describing: its first row is the header. The number of
# data columns is derived per-file from that header; mis-aligned data rows
# (a row whose len() != header len()) flag the file as unloadable. We
# previously hard-coded 273 here, but the writer now supports column
# exclusion (csv_output_plugin's ExcludeColumns) so the legitimate count
# varies by deployment + can drift across major schema edits.
_BYTE_REPR = re.compile(r"\bb'")
# csv_out_2026-04-30T20-31-10-172666_pid8.csv
_CSV_TS = re.compile(r"csv_out_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d+)_pid")
_FILE_PID = re.compile(r"_pid(\d+)\.csv$")
# iforest_out_2026-05-09T18-22-04-123456_pid8.csv
_IFOREST_GLOB = "iforest_out_*_pid*.csv"

# AINOS3-126: the per-frame arrival time the blended adapter stamps into every
# row, ISO-8601 UTC, in the same form an attack manifest's start_utc uses.
#
# ⚠ Prefer it over _synthesize_row_times ALWAYS. That fallback rebuilds row
# times as `file_start + row_idx / rate` with the rate inferred by
# _compute_step_rates from the gap to the NEXT FILE's start — a gap that
# includes the ~2 min `make stop` + `launch-quiet` between runs, so the rate is
# systematically under-estimated and the error accumulates down the file.
# Measured across the 113 rebuild_2026-09-10 runs: median 56.7 s of drift by
# end-of-file, worst 187.5 s, against attack windows of a few minutes. Rows were
# therefore labelled attack-vs-nominal against a clock that could be a minute
# out.
#
# ⚠ The in-stream clocks cannot substitute: CFE_TIME.SecondsMET ticks once per
# 4.000 s (24.9 frames), every other monotonic counter shares that cadence, and
# on INTERLEAVED data MET steps backwards on 48.2 % of rows.
RECV_TIME_COLUMN = "OnAIR.FrameRecvUTC"
_IFOREST_TS = re.compile(r"iforest_out_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d+)_pid")

# v4: ADCS mode labeling. ADCS_GNC.Mode stores the integer-valued mode the FSW
# reports (0=PASSIVE, 1=BDOT, 2=SUNSAFE, 3=INERTIAL); anything that does not
# parse to one of those (the `[0]` placeholder for "never received", empty
# strings, etc.) is bucketed as MODE_UNKNOWN. Trainers wanting per-ADCS-mode
# IFs should filter on `__adcs_mode in {MODE_PASSIVE,…INERTIAL}` to exclude
# MODE_UNKNOWN rows.
ADCS_MODE_COLUMN = "ADCS_GNC.Mode"
_ADCS_MODE_NAMES = {
    0: "MODE_PASSIVE",
    1: "MODE_BDOT",
    2: "MODE_SUNSAFE",
    3: "MODE_INERTIAL",
}


@dataclass
class LoadStats:
    files_total: int
    files_kept: int
    files_skipped_leaks: int
    files_skipped_alignment: int
    rows: int
    rows_skipped_warmup: int = 0
    files_skipped_schema: int = 0
    schema_columns: int = 0
    schema_variants: dict[int, int] = field(default_factory=dict)
    # Which clock produced __time. "recorded" = the per-frame column the
    # adapter stamps; "synthesized" = the file_start + row_idx/rate estimate.
    # Never left unset, because the two differ by a median of 57 s.
    row_time_source: str = ""
    files_row_time_recorded: int = 0
    files_row_time_synthesized: int = 0


def _file_is_clean(path: str) -> tuple[bool, str]:
    with open(path) as f:
        contents = f.read()
    if _BYTE_REPR.search(contents):
        return False, "byte_repr_leak"
    with open(path) as f:
        r = csv.reader(f)
        header = next(r, None)
        if header is None:
            return False, "empty_file"
        expected = len(header)
        for row in r:
            if len(row) != expected:
                return False, "row_misalignment"
    return True, "ok"


def _header_of(path: str) -> list[str]:
    with open(path) as f:
        return next(csv.reader(f), []) or []


def list_clean_csvs(csv_dir: str, *, schema: list[str] | None = None, strict_schema: bool = False) -> tuple[list[str], LoadStats]:
    """Clean telemetry CSVs in `csv_dir`, restricted to ONE recorded schema.

    ⚠ THE SCHEMA GUARD, and why it is not optional.

    `load()` concatenates with `pd.concat`, which OUTER-joins: a file recorded
    under an older MID list silently contributes NaN for every column it lacks,
    and `build_features` then coerces those to 0.0. The result is not an error
    and not an exclusion — it is fabricated telemetry, a spacecraft reporting
    hundreds of fields as exactly zero, mixed into training data.

    Nothing caught this before. `_file_is_clean` checks byte-repr leaks and
    row alignment WITHIN a file; no check ever compared headers BETWEEN files.
    Measured on `data/onair/csv` (2026-09-19): 487 telemetry logs spanning
    **11 distinct schemas** — 250, 256, 359, 360, 396, 442, 451, 452, 455, 470
    (schema-v1) and 479 columns — with only 148 at schema-v1.

    By default the majority schema wins and the rest are skipped and COUNTED, so
    a heterogeneous directory degrades to a warning instead of silent corruption.
    Pass `schema` to pin an explicit column list (the honest choice when a caller
    knows which recording generation it wants), or `strict_schema=True` to raise
    rather than skip.
    """
    # Limit to telemetry rotations; sibling iforest_out_*.csv side-files share
    # the directory and would otherwise be flagged as "row_misalignment".
    paths = sorted(glob.glob(os.path.join(csv_dir, "csv_out_*.csv")))
    clean: list[str] = []
    skip_leaks = 0
    skip_align = 0
    for p in paths:
        ok, why = _file_is_clean(p)
        if not ok:
            if why == "byte_repr_leak":
                skip_leaks += 1
            else:
                skip_align += 1
            continue
        clean.append(p)

    headers = {p: _header_of(p) for p in clean}
    variants: dict[int, int] = {}
    for h in headers.values():
        variants[len(h)] = variants.get(len(h), 0) + 1

    if schema is None and clean:
        # Majority by file count; ties broken by the wider (newer) schema.
        by_key: dict[tuple, int] = {}
        for h in headers.values():
            by_key[tuple(h)] = by_key.get(tuple(h), 0) + 1
        schema = list(max(by_key, key=lambda k: (by_key[k], len(k))))

    kept, skip_schema, rows_kept = [], 0, 0
    for p in clean:
        if schema is not None and headers[p] != list(schema):
            skip_schema += 1
            if strict_schema:
                raise ValueError(
                    f"{os.path.basename(p)} has {len(headers[p])} columns but the "
                    f"expected schema has {len(schema)}. Mixing recording "
                    f"generations fabricates zero-valued telemetry; quarantine the "
                    f"file or load one generation at a time.")
            continue
        kept.append(p)
        with open(p) as f:
            rows_kept += sum(1 for _ in f) - 1

    if skip_schema:
        print(f"  ⚠ schema guard: kept {len(kept)} file(s) at "
              f"{len(schema or [])} columns; skipped {skip_schema} recorded under "
              f"a different MID list (widths seen: "
              f"{dict(sorted(variants.items()))})")

    stats = LoadStats(
        files_total=len(paths),
        files_kept=len(kept),
        files_skipped_leaks=skip_leaks,
        files_skipped_alignment=skip_align,
        rows=rows_kept,
        files_skipped_schema=skip_schema,
        schema_columns=len(schema or []),
        schema_variants=dict(sorted(variants.items())),
    )
    return kept, stats


def load(
    csv_dir: str = DEFAULT_CSV_DIR,
    *,
    skip_warmup_rows: int = 0,
    schema: list[str] | None = None,
    strict_schema: bool = False,
) -> tuple[pd.DataFrame, LoadStats]:
    """Concatenate all clean CSVs.

    Adds two bookkeeping columns prefixed with `__` so feature engineering can
    skip them:
        __file_id  - source file basename, used to mask deltas at file boundaries
        __row_idx  - row index within the *original* source file (before warmup
                     skip). When skip_warmup_rows=30, kept rows have
                     __row_idx in [30..N-1]. This keeps the index aligned with
                     wall-clock interpolation: row_time = file_start + __row_idx
                     / true_step_rate.

    If `skip_warmup_rows > 0`, the first N rows of every CSV file are dropped.
    This removes startup-transient frames where some MIDs have not yet delivered
    their first sample (placeholder values + huge first-arrival deltas). Files
    shorter than N+1 rows are dropped entirely.
    """
    files, stats = list_clean_csvs(csv_dir, schema=schema,
                                   strict_schema=strict_schema)
    if not files:
        raise FileNotFoundError(f"No clean CSVs found under {csv_dir}")

    frames = []
    rows_dropped = 0
    for path in files:
        df = pd.read_csv(path, dtype=str, na_filter=False, low_memory=False)
        n_pre = len(df)
        if skip_warmup_rows > 0:
            if n_pre <= skip_warmup_rows:
                rows_dropped += n_pre
                continue
            rows_dropped += skip_warmup_rows
            df = df.iloc[skip_warmup_rows:].reset_index(drop=True)
        # __row_idx tracks the row's position in the ORIGINAL CSV so per-row
        # time interpolation stays aligned with the true CSV step rate.
        df.insert(0, "__row_idx", range(skip_warmup_rows, n_pre))
        df.insert(0, "__file_id", os.path.basename(path))
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    stats = LoadStats(
        files_total=stats.files_total,
        files_kept=stats.files_kept,
        files_skipped_leaks=stats.files_skipped_leaks,
        files_skipped_alignment=stats.files_skipped_alignment,
        rows=len(out),
        rows_skipped_warmup=rows_dropped,
        files_skipped_schema=stats.files_skipped_schema,
        schema_columns=stats.schema_columns,
        schema_variants=stats.schema_variants,
    )
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


def _load_attacks(manifest_path: str) -> list[dict]:
    """Read attack windows from one manifest. Empty list if `attacks` absent.

    `corruption_end` extends the cmd-injection window (`start..end`) by the
    attack's catalog dwell — for state-change attacks the detector signal
    persists past the subprocess exit. Older manifests without the field
    fall back to `end_utc`, making __corruption_window == __attack_window
    (preserves old eval behavior).
    """
    with open(manifest_path) as f:
        m = json.load(f)
    out = []
    for a in m.get("attacks", []):
        try:
            start = dt.datetime.fromisoformat(a["start_utc"]).replace(tzinfo=dt.timezone.utc)
            end = dt.datetime.fromisoformat(a["end_utc"]).replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            continue
        try:
            corr_end_raw = a.get("corruption_end_utc") or a["end_utc"]
            corruption_end = dt.datetime.fromisoformat(corr_end_raw).replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            corruption_end = end
        out.append({
            "id": a.get("id", "unknown"),
            "script": a.get("script", ""),
            "level": a.get("level", 0),
            "start": start, "end": end,
            "corruption_end": corruption_end,
        })
    return out


def _load_attacks_all(manifest: str | list[str]) -> list[dict]:
    out: list[dict] = []
    for path in _resolve_manifest_paths(manifest):
        out.extend(_load_attacks(path))
    return out


def _compute_step_rates(
    file_records: list[tuple[str, dt.datetime, int]],
    *,
    max_gap_s: float = 1000.0,
    fallback_rate_hz: float = 5.0,
) -> dict[str, float]:
    """Per-file CSV step rate (Hz), inferred from chronological neighbours.

    rate = n_rows / (next_file_start - this_file_start). Files with no
    chronological neighbour within `max_gap_s` use the median of measured
    rates (or `fallback_rate_hz` if nothing was measurable).
    """
    sorted_recs = sorted(file_records, key=lambda r: r[1])
    rates: dict[str, float | None] = {}
    measured: list[float] = []
    for i, (name, ts, n_rows) in enumerate(sorted_recs):
        rate: float | None = None
        if i + 1 < len(sorted_recs) and n_rows > 0:
            gap = (sorted_recs[i + 1][1] - ts).total_seconds()
            if 0 < gap < max_gap_s:
                rate = n_rows / gap
                measured.append(rate)
        rates[name] = rate
    fallback = float(np.median(measured)) if measured else fallback_rate_hz
    return {name: (r if r is not None else fallback) for name, r in rates.items()}


def _synthesize_row_times(df: pd.DataFrame, rate_by_file: dict[str, float]) -> pd.DataFrame:
    """Add a tz-aware UTC `__time` column: file_start + row_idx / file_rate.

    File start is parsed from the filename. Per-row error budget is
    1/(2*rate); at the observed ~5 Hz this is ±100 ms — well below the
    boundary tolerance of multi-second attack windows.
    """
    file_starts: dict[str, dt.datetime] = {}
    for fid in df["__file_id"].unique():
        ts = _parse_csv_filename_ts(fid)
        if ts is None:
            raise ValueError(f"could not parse filename timestamp from {fid!r}")
        file_starts[fid] = ts
    fid_arr = df["__file_id"].to_numpy()
    ridx_arr = df["__row_idx"].to_numpy()
    starts_s = np.array([file_starts[f].timestamp() for f in fid_arr])
    rates_arr = np.array([rate_by_file[f] for f in fid_arr])
    offsets_s = ridx_arr / rates_arr
    df["__time"] = pd.to_datetime(starts_s + offsets_s, unit="s", utc=True)
    return df


def _apply_row_times(df: pd.DataFrame, file_records):
    """Set `__time` from the RECORDED per-frame clock where it exists.

    Falls back to `_synthesize_row_times` per file, so pre-AINOS3-126 corpora
    still load — but the fallback is reported, never silent, because a
    synthesized row time can be a minute out (see RECV_TIME_COLUMN).

    A file counts as recorded only if the column is present AND parses for
    every row of that file; a partially-written column is treated as absent
    rather than mixed, since a half-recorded clock is worse than a consistently
    estimated one.
    """
    counts = {"recorded": 0, "synthesized": 0}
    if RECV_TIME_COLUMN not in df.columns:
        rate_by_file = _compute_step_rates(file_records)
        counts["synthesized"] = df["__file_id"].nunique()
        return _synthesize_row_times(df, rate_by_file), "synthesized", counts

    parsed = pd.to_datetime(df[RECV_TIME_COLUMN], errors="coerce", utc=True, format="ISO8601")
    ok_by_file = parsed.notna().groupby(df["__file_id"]).all()
    good = set(ok_by_file[ok_by_file].index)
    counts["recorded"] = len(good)
    counts["synthesized"] = int(df["__file_id"].nunique()) - len(good)

    if counts["synthesized"] == 0:
        df["__time"] = parsed
        return df, "recorded", counts

    # Mixed corpus: synthesize for the files that lack the column, keep the
    # recorded clock for the ones that have it.
    rate_by_file = _compute_step_rates(file_records)
    df = _synthesize_row_times(df, rate_by_file)
    mask = df["__file_id"].isin(good)
    df.loc[mask, "__time"] = parsed[mask]
    src = "recorded" if counts["synthesized"] == 0 else (
        "mixed" if counts["recorded"] else "synthesized")
    print(f"⚠ row times: {counts['recorded']} file(s) use the recorded "
          f"{RECV_TIME_COLUMN} clock, {counts['synthesized']} fall back to "
          f"file_start + row_idx/rate (median 57 s drift; see AINOS3-126)")
    return df, src, counts


def _tag_attack_rows(df: pd.DataFrame, attacks: list[dict]) -> pd.DataFrame:
    """Set `__attack_id`, `__attack_window`, and `__corruption_window`.

    `__attack_window` covers the cmd-injection phase (attack.start..attack.end).
    `__corruption_window` is a superset covering attack.start..corruption_end —
    for state-change attacks the detector signal persists past subprocess exit
    and the dwell extends the labeled window. With dwell=0 (drain-class or
    pre-corruption-dwell manifests), the two windows are identical.
    """
    n = len(df)
    if n == 0 or not attacks:
        df["__attack_id"] = ""
        df["__attack_window"] = False
        df["__corruption_window"] = False
        return df
    times = df["__time"].to_numpy()
    times_ns = pd.to_datetime(times, utc=True).tz_convert(None).to_numpy()
    ids = np.full(n, "", dtype=object)
    flag = np.zeros(n, dtype=bool)
    corr = np.zeros(n, dtype=bool)
    # Convert manifest start/end to numpy datetime64 for vectorised compare.
    for a in attacks:
        s = np.datetime64(a["start"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        e = np.datetime64(a["end"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        ce = np.datetime64(a["corruption_end"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        in_win = (times_ns >= s) & (times_ns <= e)
        in_corr = (times_ns >= s) & (times_ns <= ce)
        ids[in_corr] = a["id"]  # tag every row inside the broader window
        flag[in_win] = True
        corr[in_corr] = True
    df["__attack_id"] = ids
    df["__attack_window"] = flag
    df["__corruption_window"] = corr
    return df


def _derive_adcs_mode(df: pd.DataFrame) -> pd.Series:
    """Map `ADCS_GNC.Mode` → MODE_PASSIVE/BDOT/SUNSAFE/INERTIAL/MODE_UNKNOWN.

    The CSV column stores either a numeric string (e.g. `'2'`) or the `'[0]'`
    placeholder for "never received yet". Anything that does not parse to
    one of {0,1,2,3} → MODE_UNKNOWN. Returns a string Series aligned with
    `df.index`; falls back to all-MODE_UNKNOWN if the column is absent so
    diagnostic loaders don't blow up on incompatible CSV schemas.
    """
    if ADCS_MODE_COLUMN not in df.columns:
        return pd.Series(["MODE_UNKNOWN"] * len(df), index=df.index)
    nums = pd.to_numeric(df[ADCS_MODE_COLUMN].astype(str), errors="coerce")
    return nums.map(_ADCS_MODE_NAMES).fillna("MODE_UNKNOWN")


def _mode_transient_mask(
    modes: np.ndarray, file_ids: np.ndarray, skip_frames: int,
) -> np.ndarray:
    """True for rows within `skip_frames` of a mode-change inside the same file.

    File boundaries are not treated as mode transitions — the file-ID mismatch
    is itself a discontinuity that `build_features` already masks against. The
    inner loop is O(n) but n ≤ ~200K rows for the full corpus, so vectorising
    isn't worth the additional complexity here.
    """
    n = len(modes)
    out = np.zeros(n, dtype=bool)
    if skip_frames <= 0 or n < 2:
        return out
    active = 0
    for i in range(1, n):
        if file_ids[i] != file_ids[i - 1]:
            active = 0
            continue
        if modes[i] != modes[i - 1]:
            active = skip_frames
        if active > 0:
            out[i] = True
            active -= 1
    return out


def load_with_labels(
    csv_dir: str = DEFAULT_CSV_DIR,
    manifest: str | list[str] = None,
    *,
    drop_unlabeled: bool = True,
    skip_warmup_rows: int = 0,
    mode_transient_skip: int = 0,
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

    Adds `__adcs_mode` (MODE_PASSIVE/BDOT/SUNSAFE/INERTIAL/MODE_UNKNOWN) from
    each row's `ADCS_GNC.Mode`. v4 per-ADCS-mode IF training groups on this
    column instead of `__scenario`. With `mode_transient_skip > 0`, rows
    within that many frames of a mode change (per file) are filtered out —
    these rows show the FSW state-propagation transient and contaminate
    per-mode training the same way SBN first-arrival deltas contaminate
    warmup (mirrors the `skip_warmup_rows` rationale).
    """
    if not manifest:
        raise ValueError("manifest is required for load_with_labels")
    scenarios = _load_manifests(manifest)
    attacks = _load_attacks_all(manifest)
    df, stats = load(csv_dir, skip_warmup_rows=skip_warmup_rows)

    # Step rate per file from chronological neighbours; uses pre-skip row
    # count (max __row_idx + 1) so the rate reflects the true CSV cadence
    # regardless of warmup trim. Files with no neighbour fall back to median.
    # Computed across ALL files (not just labeled ones) because a labeled
    # file's neighbour might itself be unlabeled but still inform its rate.
    file_records: list[tuple[str, dt.datetime, int]] = []
    pre_skip_counts = df.groupby("__file_id")["__row_idx"].max() + 1
    for fid, n_pre in pre_skip_counts.items():
        ts = _parse_csv_filename_ts(fid)
        if ts is None:
            continue
        file_records.append((fid, ts, int(n_pre)))
    df, stats.row_time_source, per_file = _apply_row_times(df, file_records)
    stats.files_row_time_recorded = per_file["recorded"]
    stats.files_row_time_synthesized = per_file["synthesized"]
    df = _tag_attack_rows(df, attacks)

    # Per-row scenario assignment from __time. File-level assignment is
    # fragile: if a file rotates mid-scenario its file_start may fall
    # outside the window, dropping all its rows; conversely, a file whose
    # file_start is in a window can extend far past the window's end and
    # contaminate the labeled set. Per-row matching against scenario and
    # attack windows is correct in both cases.
    times_ns = df["__time"].dt.tz_convert(None).to_numpy()
    scn_arr = np.full(len(df), "unlabeled", dtype=object)
    for w in scenarios:
        s = np.datetime64(w["start"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        e = np.datetime64(w["end"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        mask = (times_ns >= s) & (times_ns <= e)
        scn_arr[mask] = w["name"]
    # Attack windows: tag with the attack's `during_scenario` so attack
    # rows route through the correct per-scenario IF at scoring time.
    for a in attacks:
        s = np.datetime64(a["start"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        e = np.datetime64(a["end"].astimezone(dt.timezone.utc).replace(tzinfo=None))
        mask = (times_ns >= s) & (times_ns <= e)
        # `during_scenario` was added to attack records by run_attack.py;
        # older manifests without it leave attack rows tagged "unlabeled"
        # and they get dropped — fall back to the row's existing scenario
        # tag (if any) before defaulting to unlabeled.
        scn_arr[mask] = "_keep_existing_"
    # Resolve placeholder: if a row was tagged "_keep_existing_" but has
    # no scenario assigned via the attack record, look up `during_scenario`
    # from the originating attack manifest.
    if attacks:
        attack_id_arr = df["__attack_id"].to_numpy()
        for a in attacks:
            ds = None
            for path in _resolve_manifest_paths(manifest):
                with open(path) as f:
                    m = json.load(f)
                for amanif in m.get("attacks", []):
                    if amanif.get("id") == a["id"]:
                        ds = amanif.get("during_scenario")
                        break
                if ds:
                    break
            if not ds:
                ds = "unlabeled"
            mask = (attack_id_arr == a["id"]) & (scn_arr == "_keep_existing_")
            scn_arr[mask] = ds

    df["__scenario"] = scn_arr
    df["__adcs_mode"] = _derive_adcs_mode(df).to_numpy()

    if mode_transient_skip > 0:
        transient = _mode_transient_mask(
            df["__adcs_mode"].to_numpy(),
            df["__file_id"].to_numpy(),
            mode_transient_skip,
        )
        n_transient = int(transient.sum())
        if n_transient:
            df = df[~transient].reset_index(drop=True)
            print(f"  dropped {n_transient} mode-transient rows "
                  f"(skip_frames={mode_transient_skip})")

    if drop_unlabeled:
        before = len(df)
        df = df[df["__scenario"] != "unlabeled"].reset_index(drop=True)
        stats = LoadStats(
            files_total=stats.files_total,
            files_kept=df["__file_id"].nunique(),
            files_skipped_leaks=stats.files_skipped_leaks,
            files_skipped_alignment=stats.files_skipped_alignment,
            rows=len(df),
            rows_skipped_warmup=stats.rows_skipped_warmup,
        )
        print(f"  dropped {before - len(df)} rows outside any scenario/attack window; "
              f"kept {len(df)} labeled rows")
    if skip_warmup_rows > 0:
        print(f"  dropped {stats.rows_skipped_warmup} warmup rows (first {skip_warmup_rows} of each file)")

    n_attack_rows = int(df["__attack_window"].sum())
    if attacks:
        print(f"  attack windows: {len(attacks)} from manifests; "
              f"tagged {n_attack_rows} rows as __attack_window=True")
    return df, stats


def _file_pid(file_id: str) -> int | None:
    m = _FILE_PID.search(file_id)
    return int(m.group(1)) if m else None


def _parse_iforest_filename_ts(path: str) -> dt.datetime | None:
    """Extract the IF plugin's init timestamp from an iforest_out_<ts>_pid<N>.csv name."""
    m = _IFOREST_TS.search(os.path.basename(path))
    if not m:
        return None
    raw = m.group(1)
    head, micro = raw.rsplit("-", 1)
    try:
        when = dt.datetime.strptime(head, "%Y-%m-%dT%H-%M-%S")
        return when.replace(microsecond=int(micro)).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def attach_iforest_scores(
    df: pd.DataFrame, csv_dir: str = DEFAULT_CSV_DIR,
) -> pd.DataFrame:
    """Merge sibling `iforest_out_*.csv` columns into a loaded telemetry frame.

    The IF plugin writes one side-file per OnAIR process. The container PID
    namespace deterministically assigns the same pid (e.g. 11) to every
    OnAIR launch, so multiple sessions in one directory share a pid — pid
    alone is not a session key. Each csv_out is therefore routed to the
    side-file whose timestamp is the **latest one ≤ the csv_out's
    timestamp** (same pid). Cumulative offsets accumulate per side-file,
    so two same-pid sessions in one dir join independently.

    Join semantics:
      - `pid` is parsed from `__file_id` (e.g. `csv_out_..._pid8.csv` → 8).
      - For each csv_out file, pick `assigned_side` = max(ts) over
        side-files with same pid and ts ≤ csv_out's ts.
      - `cumulative_frame_idx = sum(prior_file_lengths_with_same_assigned_side)
        + __row_idx`. Prior-file length uses `max(__row_idx) + 1` (the
        original row count), so `load(skip_warmup_rows=N)` does not desync.

    Adds columns: `if_score` (float), `if_threshold` (float), `if_is_anomaly`
    (int 0/1), `if_alert` (int 0/1), `if_cleared` (int 0/1), `if_scenario`
    (str). Rows with no matching side-file row keep NaN/0/'' (e.g. side-file
    writer was disabled for that run, csv_out predates every side-file, or
    file lost a tail flush).

    Returns the input `df` unchanged when no side-files are found.
    """
    side_paths = sorted(glob.glob(os.path.join(csv_dir, _IFOREST_GLOB)))
    if not side_paths:
        return df

    side_records: list[tuple[dt.datetime, int, str]] = []
    for sp in side_paths:
        ts = _parse_iforest_filename_ts(sp)
        m = _FILE_PID.search(sp)
        if ts is None or not m:
            continue
        side_records.append((ts, int(m.group(1)), sp))
    if not side_records:
        return df
    sides_by_pid: dict[int, list[tuple[dt.datetime, str]]] = {}
    for ts, pid, sp in side_records:
        sides_by_pid.setdefault(pid, []).append((ts, sp))
    for pid in sides_by_pid:
        sides_by_pid[pid].sort()

    out = df.copy()
    out["if_score"] = np.nan
    out["if_threshold"] = np.nan
    out["if_is_anomaly"] = 0
    out["if_alert"] = 0
    out["if_cleared"] = 0
    out["if_scenario"] = ""

    # Build per-file metadata: (ts, fid, pid, n_orig). n_orig preserves the
    # original (pre-warmup-skip) row count via max(__row_idx)+1.
    file_meta: list[tuple[dt.datetime, str, int, int]] = []
    grp = df.groupby("__file_id")["__row_idx"]
    for fid, mx in grp.max().items():
        pid = _file_pid(fid)
        ts = _parse_csv_filename_ts(fid)
        if pid is None or ts is None:
            continue
        file_meta.append((ts, fid, pid, int(mx) + 1))

    # Walk csv_outs chronologically; assign each to the most-recent side-file
    # whose ts ≤ csv_out's ts (same pid), and accumulate offsets per side-file
    # so each session brackets its own contiguous frame index space.
    file_side: dict[str, str | None] = {}
    file_offset: dict[str, int] = {}
    offset_acc: dict[str, int] = {}
    for ts, fid, pid, n_orig in sorted(file_meta):
        sides_list = sides_by_pid.get(pid, [])
        assigned: str | None = None
        for s_ts, sp in sides_list:
            if s_ts <= ts:
                assigned = sp
            else:
                break
        file_side[fid] = assigned
        if assigned is None:
            continue
        file_offset[fid] = offset_acc.get(assigned, 0)
        offset_acc[assigned] = offset_acc.get(assigned, 0) + n_orig

    fid_arr = out["__file_id"].to_numpy()
    ridx_arr = out["__row_idx"].to_numpy()
    side_per_row = np.array([file_side.get(f) for f in fid_arr], dtype=object)
    cum_per_row = np.array(
        [file_offset.get(f, 0) + r for f, r in zip(fid_arr, ridx_arr)]
    )

    for _ts, _pid, sp in side_records:
        mask = side_per_row == sp
        if not mask.any():
            continue
        sdf_indexed = pd.read_csv(sp).set_index("frame_idx")
        cum_subset = cum_per_row[mask]
        matched = sdf_indexed.reindex(cum_subset)
        idx = np.where(mask)[0]
        out.iloc[idx, out.columns.get_loc("if_score")] = matched["score"].to_numpy()
        out.iloc[idx, out.columns.get_loc("if_threshold")] = matched["threshold"].to_numpy()
        out.iloc[idx, out.columns.get_loc("if_is_anomaly")] = (
            matched["is_anomaly"].fillna(0).astype(int).to_numpy()
        )
        out.iloc[idx, out.columns.get_loc("if_alert")] = (
            matched["alert"].fillna(0).astype(int).to_numpy()
        )
        out.iloc[idx, out.columns.get_loc("if_cleared")] = (
            matched["cleared"].fillna(0).astype(int).to_numpy()
        )
        out.iloc[idx, out.columns.get_loc("if_scenario")] = (
            matched["scenario"].fillna("").to_numpy()
        )
    return out


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
    if "__adcs_mode" in df.columns:
        print("  adcs mode distribution:")
        for name, n in df["__adcs_mode"].value_counts().items():
            print(f"    {name}: {n} rows")
