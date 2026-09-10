#!/usr/bin/env python3
"""Tests for analyze_inertial_fp — the AINOS3-86 AC3 measurement tool.

These pin the two things that would silently corrupt the measurement rather than
fail it, both of which were hit for real while building the tool:

  1. **Session pairing.** pids recycle across launches, so "the newest csv_out
     with a matching pid" can pair a 2026-08-15 side-file with a 2026-09-10 main
     log. Must match on the session TIMESTAMP.
  2. **The qValid gate.** A frame labelled MODE_INERTIAL with qValid=0 is free
     drift, not nominal INERTIAL. Counting it is how 33.6 % came to be published
     as an INERTIAL false-alarm rate.
"""
import csv
import importlib.util
import re
import os
import sys

import pytest

_MOD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_inertial_fp.py")
_spec = importlib.util.spec_from_file_location("analyze_inertial_fp", _MOD)
afp = importlib.util.module_from_spec(_spec)
sys.modules["analyze_inertial_fp"] = afp
_spec.loader.exec_module(afp)


def _write(path, header, rows):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def csv_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(afp, "CSV_DIR", str(tmp_path))
    return tmp_path


def test_pairing_matches_session_timestamp_not_newest_mtime(csv_dir):
    """The bug: same pid, different launches. Newest-by-mtime picks the wrong one."""
    old_side = csv_dir / "iforest_out_2026-08-15T13-57-38-383218_pid11.csv"
    old_main = csv_dir / "csv_out_2026-08-15T13-57-38-900000_pid11.csv"
    new_main = csv_dir / "csv_out_2026-09-10T15-12-34-678439_pid11.csv"
    for p in (old_side, old_main, new_main):
        _write(p, ["a"], [["1"]])
    # make the WRONG one newest, which is exactly the real-world situation
    os.utime(new_main, (10_000_000, 10_000_000))
    os.utime(old_main, (1_000_000, 1_000_000))

    assert afp.pair_main_log(str(old_side)) == str(old_main)


def test_pairing_refuses_when_no_same_session_partner_exists(csv_dir):
    side = csv_dir / "iforest_out_2026-08-15T13-57-38-383218_pid11.csv"
    far = csv_dir / "csv_out_2026-09-10T15-12-34-678439_pid11.csv"
    for p in (side, far):
        _write(p, ["a"], [["1"]])
    with pytest.raises(SystemExit):
        afp.pair_main_log(str(side))


def test_vec_mag_deg_parses_bracketed_arrays_and_survives_sentinel():
    import math
    v = afp.vec_mag_deg("[0.0, 0.0, 0.017453292519943295]")
    assert v == pytest.approx(1.0, abs=1e-6)
    assert afp.vec_mag_deg("[0]") is None or isinstance(afp.vec_mag_deg("[0]"), float)
    assert afp.vec_mag_deg("not a vector") is None


def _run(csv_dir, monkeypatch, side_rows, main_rows, extra_argv=()):
    side = csv_dir / "iforest_out_2026-09-10T15-12-34-107776_pid11.csv"
    main = csv_dir / "csv_out_2026-09-10T15-12-34-678439_pid11.csv"
    _write(side, ["frame_idx", "scenario", "score", "threshold",
                  "is_anomaly", "alert", "cleared"], side_rows)
    _write(main, ["ADCS_GNC.qValid", "ADCS_GNC.wbn"], main_rows)
    argv = ["analyze_inertial_fp.py", "--side-file", str(side), "--skip-min", "0"]
    argv += list(extra_argv)
    monkeypatch.setattr(sys, "argv", argv)
    return afp.main()


def test_loop_open_frames_are_excluded_from_the_controlled_arm(csv_dir, monkeypatch, capsys):
    """10 controlled frames, all clean; 10 loop-open frames, all alerting.

    If the qValid gate were ignored the reported FP would be 50 %.
    """
    side, main = [], []
    for i in range(10):
        side.append([i, "MODE_INERTIAL", "0.1", "-0.0", "0", "0", "0"])
        main.append(["1", "[0.0, 0.0, 0.001]"])
    for i in range(10, 20):
        side.append([i, "MODE_INERTIAL", "-0.9", "-0.0", "1", "1", "0"])
        main.append(["0", "[0.0, 0.0, 0.05]"])
    assert _run(csv_dir, monkeypatch, side, main) == 0
    out = capsys.readouterr().out
    assert re.search(r"operational FP \(alert\)\s+0\.0000%", out)
    assert "PASS" in out
    assert re.search(r"loop OPEN \(qValid=0\)\s+10", out)


def test_end_frame_excludes_the_attack_window(csv_dir, monkeypatch, capsys):
    """Frames inside an attack are true positives; counting them inflates FP."""
    side, main = [], []
    for i in range(10):                      # nominal pre-window, clean
        side.append([i, "MODE_INERTIAL", "0.1", "-0.0", "0", "0", "0"])
        main.append(["1", "[0.0, 0.0, 0.001]"])
    for i in range(10, 20):                  # attack window, alerting correctly
        side.append([i, "MODE_INERTIAL", "-0.9", "-0.0", "1", "1", "0"])
        main.append(["1", "[0.0, 0.0, 0.001]"])

    assert _run(csv_dir, monkeypatch, side, main, ["--end-frame", "9"]) == 0
    assert re.search(r"operational FP \(alert\)\s+0\.0000%", capsys.readouterr().out)

    assert _run(csv_dir, monkeypatch, side, main) == 0
    assert re.search(r"operational FP \(alert\)\s+50\.0000%", capsys.readouterr().out)


def test_session_with_no_controlled_frames_reports_the_loop_open_arm(csv_dir, monkeypatch, capsys):
    """Every session before 2026-09-10 is like this — must report, not crash."""
    side = [[i, "MODE_INERTIAL", "-0.9", "-0.0", "1", "1", "0"] for i in range(10)]
    main = [["0", "[0.0, 0.0, 0.04]"] for _ in range(10)]
    assert _run(csv_dir, monkeypatch, side, main) == 0
    out = capsys.readouterr().out
    assert "NO controlled INERTIAL frames" in out
    assert re.search(r"operational FP\s+100\.0000%", out)
