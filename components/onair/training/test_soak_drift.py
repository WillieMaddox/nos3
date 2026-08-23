"""Tests for the sample-rate derivation in `analyze_soak_drift` (AINOS3-92).

The tool shipped for four sprints with a hardcoded 4.2 Hz against a measured
~5.5, which overstated every uptime bin by ~32%. These cover the three paths
that replaced it: derive, override, and loud fallback.
"""
import importlib.util
import os
import sys

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "analyze_soak_drift",
    os.path.join(os.path.dirname(__file__), "analyze_soak_drift.py"))
asd = importlib.util.module_from_spec(_SPEC)
sys.modules["analyze_soak_drift"] = asd
_SPEC.loader.exec_module(asd)


def _session(tmp_path, ts="2026-08-23T10-00-00-000000", pid=7, n=1000, hz=5.5,
             main_ts=None, met_col="CFE_TIME.SecondsMET"):
    """Write a matched iforest_out_/csv_out_ pair with a MET clock at `hz`."""
    side = tmp_path / f"iforest_out_{ts}_pid{pid}.csv"
    side.write_text("frame_idx,scenario,score,threshold,is_anomaly,alert,cleared\n"
                    + "".join(f"{i},MODE_SUNSAFE,0.01,0.0,0,0,0\n" for i in range(n)))
    main = tmp_path / f"csv_out_{main_ts or ts}_pid{pid}.csv"
    main.write_text(f"{met_col},CFE_TIME.SubsecsMET\n"
                    + "".join(f"{int(i / hz)},0\n" for i in range(n)))
    return str(side)


def test_derives_the_rate_from_met(tmp_path):
    side = _session(tmp_path, n=2000, hz=5.5)
    hz, why = asd.derive_hz(side)
    assert hz == pytest.approx(5.5, rel=0.02)
    assert "CFE_TIME.SecondsMET" in why


def test_derivation_is_not_the_old_hardcoded_default(tmp_path):
    """Regression guard: the bug was a constant that ignored the data."""
    side = _session(tmp_path, n=2000, hz=5.5)
    hz, _ = asd.derive_hz(side)
    assert abs(hz - 4.2) > 1.0


def test_pairing_tolerates_the_sub_second_open_skew(tmp_path):
    """OnAIR opens the side-file and the main CSV ~0.5s apart in one session."""
    side = _session(tmp_path, ts="2026-08-23T10-00-00-000000",
                    main_ts="2026-08-23T10-00-00-500000", n=2000)
    assert asd.find_paired_main_csv(side) is not None


def test_no_pair_is_not_derivable(tmp_path):
    side = tmp_path / "iforest_out_2026-08-23T10-00-00-000000_pid9.csv"
    side.write_text("frame_idx,scenario\n0,MODE_SUNSAFE\n")
    hz, why = asd.derive_hz(str(side))
    assert hz is None and "no paired" in why


def test_short_span_is_rejected_rather_than_trusted(tmp_path):
    side = _session(tmp_path, n=100, hz=5.5)          # ~18s of MET
    hz, why = asd.derive_hz(side)
    assert hz is None and "too short" in why


def test_missing_met_column_is_rejected(tmp_path):
    side = _session(tmp_path, n=2000, met_col="CFE_TIME.SecondsSTCF")
    hz, why = asd.derive_hz(side)
    assert hz is None and "SecondsMET" in why


def test_insane_rate_is_rejected(tmp_path):
    side = _session(tmp_path, n=15000, hz=200.0)   # 200 Hz over 75s of MET
    hz, why = asd.derive_hz(side)
    assert hz is None and "sane band" in why


def test_resolve_falls_back_loudly_when_underivable(tmp_path, capsys):
    side = tmp_path / "iforest_out_2026-08-23T10-00-00-000000_pid9.csv"
    side.write_text("frame_idx,scenario\n0,MODE_SUNSAFE\n")
    hz, why = asd.resolve_hz(str(side), None)
    assert hz == asd.FALLBACK_HZ
    assert "WARNING" in capsys.readouterr().err
    assert "fallback" in why


def test_resolve_warns_when_the_override_contradicts_the_data(tmp_path, capsys):
    side = _session(tmp_path, n=2000, hz=5.5)
    hz, why = asd.resolve_hz(side, 4.2)
    assert hz == 4.2                                   # override always wins
    err = capsys.readouterr().err
    assert "WARNING" in err and "disagrees" in err
    assert "override" in why


def test_resolve_is_quiet_when_the_override_agrees(tmp_path, capsys):
    side = _session(tmp_path, n=2000, hz=5.5)
    hz, _ = asd.resolve_hz(side, 5.4)
    assert hz == 5.4
    assert capsys.readouterr().err == ""
