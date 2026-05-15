# GSC-19165-1, "The On-Board Artificial Intelligence Research (OnAIR) Platform"
# Licensed under the NASA Open Source Agreement version 1.3

"""Tests for `attach_iforest_scores`.

Exercises the row-level join between csv_out_*.csv (loaded through `load()`)
and sibling iforest_out_*_pid<N>.csv side-files. The pid + cumulative-row-idx
mapping is the only piece of glue that can quietly desync if either plugin's
indexing changes."""

import csv
import os

import numpy as np
import pandas as pd
import pytest

from loader import (
    _derive_adcs_mode,
    _mode_transient_mask,
    attach_iforest_scores,
    load,
)


def _write_csv_out(path, headers, rows):
    """Write a csv_out_*.csv-shaped file with the given header + rows."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)


def _write_side_file(path, rows):
    """Write a fake iforest_out_*_pid<N>.csv side-file."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["frame_idx", "scenario", "score", "threshold",
             "is_anomaly", "alert", "cleared"]
        )
        for r in rows:
            w.writerow(r)


@pytest.fixture
def synthetic_dir(tmp_path, monkeypatch):
    """Build a CSV directory with two pid8 files (3+2 rows) + matching side-file.

    `_file_is_clean` derives the expected column count from each file's
    header row, so a 3-wide synthetic fixture self-validates without any
    monkey-patching needed."""
    headers = ["a", "b", "c"]

    f1 = tmp_path / "csv_out_2026-05-09T10-00-00-000000_pid8.csv"
    _write_csv_out(f1, headers, [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
    ])
    f2 = tmp_path / "csv_out_2026-05-09T10-01-00-000000_pid8.csv"
    _write_csv_out(f2, headers, [
        ["10", "11", "12"],
        ["13", "14", "15"],
    ])

    # Side-file ts MUST precede the first csv_out — the IF plugin __init__
    # records its filename before csv_output's first rotation lands on disk.
    # 5 frames matching the cumulative index 0..4 across both csvs.
    side = tmp_path / "iforest_out_2026-05-09T09-59-59-999999_pid8.csv"
    _write_side_file(side, [
        [0, "nominal_ops", "0.10", "0.00", 0, 0, 0],
        [1, "nominal_ops", "-0.05", "0.00", 1, 1, 0],   # alert
        [2, "nominal_ops", "-0.04", "0.00", 1, 0, 0],   # still anomaly
        [3, "nominal_ops", "0.02", "0.00", 0, 0, 1],    # cleared
        [4, "nominal_ops", "0.05", "0.00", 0, 0, 0],
    ])
    return tmp_path


def test_attach_joins_by_pid_and_cumulative_idx(synthetic_dir):
    df, _ = load(str(synthetic_dir))
    assert len(df) == 5

    out = attach_iforest_scores(df, str(synthetic_dir))

    # Original df is untouched (function copies internally).
    assert "if_score" not in df.columns

    # Cumulative idx 0..4 maps row-by-row to the side-file. The second csv_out
    # (rows 4-5 by file timestamp) must pick up frame_idx 3 and 4.
    np.testing.assert_array_equal(
        out["if_score"].to_numpy(),
        np.array([0.10, -0.05, -0.04, 0.02, 0.05]),
    )
    np.testing.assert_array_equal(
        out["if_is_anomaly"].to_numpy(),
        np.array([0, 1, 1, 0, 0]),
    )
    # Alert/clear edges land on the right rows.
    assert list(out["if_alert"]) == [0, 1, 0, 0, 0]
    assert list(out["if_cleared"]) == [0, 0, 0, 1, 0]
    assert list(out["if_scenario"]) == ["nominal_ops"] * 5


def test_attach_survives_warmup_skip(synthetic_dir):
    """Dropping warmup rows changes __row_idx start but not the cumulative join."""
    df, _ = load(str(synthetic_dir), skip_warmup_rows=2)
    # File 1 (3 rows) keeps __row_idx 2..2; File 2 (2 rows) drops entirely.
    assert len(df) == 1
    assert df["__row_idx"].iloc[0] == 2

    out = attach_iforest_scores(df, str(synthetic_dir))
    # Cumulative idx for the surviving row = 0 (offset for file1) + 2 = 2.
    assert out["if_score"].iloc[0] == pytest.approx(-0.04)
    assert out["if_is_anomaly"].iloc[0] == 1


def test_attach_no_side_files_returns_input(tmp_path, monkeypatch):
    f1 = tmp_path / "csv_out_2026-05-09T10-00-00-000000_pid8.csv"
    _write_csv_out(f1, ["a", "b"], [["1", "2"], ["3", "4"]])

    df, _ = load(str(tmp_path))
    out = attach_iforest_scores(df, str(tmp_path))

    # Function returned df unchanged (no side-files to merge).
    assert "if_score" not in out.columns
    assert out is df


def test_attach_two_sessions_same_pid_join_independently(tmp_path, monkeypatch):
    """OnAIR's container PID namespace assigns the same pid (e.g. 11) to every
    new launch, so consecutive sessions in one csv_dir share the side-file pid.
    Cumulative offsets must accumulate per side-file, not per pid, or the
    second session's rows would be looked up under the first session's
    frame indices — yielding wrong scores or out-of-range NaNs."""
    headers = ["a", "b"]

    # Session 1: pid 11, 3 csv_out rows + side-file with frame_idx 0..2.
    s1_csv = tmp_path / "csv_out_2026-05-10T08-00-00-000000_pid11.csv"
    _write_csv_out(s1_csv, headers, [["1", "2"], ["3", "4"], ["5", "6"]])
    s1_side = tmp_path / "iforest_out_2026-05-10T07-59-59-999000_pid11.csv"
    _write_side_file(s1_side, [
        [0, "nominal_ops", "0.10", "0.00", 0, 0, 0],
        [1, "nominal_ops", "0.20", "0.00", 0, 0, 0],
        [2, "nominal_ops", "0.30", "0.00", 0, 0, 0],
    ])

    # Session 2: SAME pid 11, started later. 2 csv_out rows + side-file with
    # frame_idx 0..1. If the join were per-pid (the old behavior), session 2's
    # row 0 would look up cumulative_idx 3 in either side-file — missing the
    # session-1 side (only goes to 2) and absent from the session-2 side.
    s2_csv = tmp_path / "csv_out_2026-05-10T09-00-00-000000_pid11.csv"
    _write_csv_out(s2_csv, headers, [["7", "8"], ["9", "10"]])
    s2_side = tmp_path / "iforest_out_2026-05-10T08-59-59-999000_pid11.csv"
    _write_side_file(s2_side, [
        [0, "quiescent", "-0.10", "0.00", 1, 1, 0],
        [1, "quiescent", "0.05", "0.00", 0, 0, 1],
    ])

    df, _ = load(str(tmp_path))
    assert len(df) == 5
    out = attach_iforest_scores(df, str(tmp_path))

    # Session 1 rows route through session-1 side-file scores.
    np.testing.assert_array_equal(
        out["if_score"].to_numpy()[:3],
        np.array([0.10, 0.20, 0.30]),
    )
    assert list(out["if_scenario"].iloc[:3]) == ["nominal_ops"] * 3

    # Session 2 rows route through session-2 side-file scores — NOT continuing
    # from cumulative_idx 3 into a missing slot.
    np.testing.assert_array_equal(
        out["if_score"].to_numpy()[3:],
        np.array([-0.10, 0.05]),
    )
    assert list(out["if_scenario"].iloc[3:]) == ["quiescent", "quiescent"]
    assert list(out["if_alert"].iloc[3:]) == [1, 0]
    assert list(out["if_cleared"].iloc[3:]) == [0, 1]


def test_attach_csv_predating_all_side_files_gets_defaults(tmp_path, monkeypatch):
    """A csv_out whose ts is before every same-pid side-file (e.g. an orphan
    from a session whose side-file was deleted) must get default NaN/0/''
    rather than be mis-attributed to a later session."""
    # csv_out with ts 08:00; only side-file is at 09:00 (later).
    csv1 = tmp_path / "csv_out_2026-05-10T08-00-00-000000_pid11.csv"
    _write_csv_out(csv1, ["a", "b"], [["1", "2"], ["3", "4"]])
    side = tmp_path / "iforest_out_2026-05-10T09-00-00-000000_pid11.csv"
    _write_side_file(side, [[0, "nominal_ops", "0.5", "0.0", 0, 0, 0]])

    df, _ = load(str(tmp_path))
    out = attach_iforest_scores(df, str(tmp_path))

    # Orphan csv_out → no IF data. No mis-attribution into later session.
    assert out["if_score"].isna().all()
    assert (out["if_is_anomaly"] == 0).all()


def test_derive_adcs_mode_maps_known_values():
    df = pd.DataFrame({"ADCS_GNC.Mode": ["0", "1", "2", "3", "[0]", "", "nan", "9"]})
    modes = _derive_adcs_mode(df)
    assert list(modes) == [
        "MODE_PASSIVE", "MODE_BDOT", "MODE_SUNSAFE", "MODE_INERTIAL",
        "MODE_UNKNOWN",  # placeholder
        "MODE_UNKNOWN",  # empty string
        "MODE_UNKNOWN",  # 'nan' literal
        "MODE_UNKNOWN",  # out-of-range int
    ]


def test_derive_adcs_mode_missing_column_returns_unknown():
    df = pd.DataFrame({"some_other_col": ["a", "b", "c"]})
    modes = _derive_adcs_mode(df)
    assert list(modes) == ["MODE_UNKNOWN"] * 3


def test_mode_transient_mask_marks_post_change_frames():
    # File A: PASSIVE PASSIVE BDOT BDOT BDOT  → change at idx 2, next 2 are transient
    # File B: BDOT INERTIAL INERTIAL          → change at idx 1, next 2 transient
    # Cross-file boundary (A→B) NOT counted as a mode change.
    modes = np.array([
        "MODE_PASSIVE", "MODE_PASSIVE", "MODE_BDOT", "MODE_BDOT", "MODE_BDOT",
        "MODE_BDOT", "MODE_INERTIAL", "MODE_INERTIAL",
    ])
    fids = np.array(["A", "A", "A", "A", "A", "B", "B", "B"])
    mask = _mode_transient_mask(modes, fids, skip_frames=2)
    # idx 2: change inside A → True; idx 3: still within window → True; idx 4: outside.
    # idx 5: cross-file (A→B) → not a change, False.
    # idx 6: change in B → True; idx 7: within window → True.
    assert list(mask) == [
        False, False, True, True, False, False, True, True,
    ]


def test_mode_transient_mask_skip_zero_returns_all_false():
    modes = np.array(["MODE_PASSIVE", "MODE_BDOT", "MODE_INERTIAL"])
    fids = np.array(["A", "A", "A"])
    mask = _mode_transient_mask(modes, fids, skip_frames=0)
    assert not mask.any()


def test_attach_pid_mismatch_keeps_defaults(tmp_path, monkeypatch):
    """A side-file from a different OnAIR run (different pid) must not bleed
    into rows it doesn't own."""
    f1 = tmp_path / "csv_out_2026-05-09T10-00-00-000000_pid8.csv"
    _write_csv_out(f1, ["a", "b"], [["1", "2"], ["3", "4"]])
    # Side-file from a different run, pid=99
    side = tmp_path / "iforest_out_2026-05-09T09-00-00-000000_pid99.csv"
    _write_side_file(side, [
        [0, "nominal_ops", "-0.5", "0.0", 1, 1, 0],
        [1, "nominal_ops", "-0.5", "0.0", 1, 0, 0],
    ])

    df, _ = load(str(tmp_path))
    out = attach_iforest_scores(df, str(tmp_path))

    # All defaults; no mis-attributed scores.
    assert out["if_score"].isna().all()
    assert (out["if_is_anomaly"] == 0).all()
    assert (out["if_scenario"] == "").all()
