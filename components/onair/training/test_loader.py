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

from loader import attach_iforest_scores, load


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

    EXPECTED_COLS in loader is 273 — `_file_is_clean` enforces that. We
    monkey-patch it down to the synthetic width so a tiny fixture is workable
    without standing up the full telemetry schema."""
    monkeypatch.setattr("loader.EXPECTED_COLS", 3)
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

    # Side-file: 5 frames matching the cumulative index 0..4 across both csvs.
    side = tmp_path / "iforest_out_2026-05-09T10-00-00-000001_pid8.csv"
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
    monkeypatch.setattr("loader.EXPECTED_COLS", 2)
    f1 = tmp_path / "csv_out_2026-05-09T10-00-00-000000_pid8.csv"
    _write_csv_out(f1, ["a", "b"], [["1", "2"], ["3", "4"]])

    df, _ = load(str(tmp_path))
    out = attach_iforest_scores(df, str(tmp_path))

    # Function returned df unchanged (no side-files to merge).
    assert "if_score" not in out.columns
    assert out is df


def test_attach_pid_mismatch_keeps_defaults(tmp_path, monkeypatch):
    """A side-file from a different OnAIR run (different pid) must not bleed
    into rows it doesn't own."""
    monkeypatch.setattr("loader.EXPECTED_COLS", 2)
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
