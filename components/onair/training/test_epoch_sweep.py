"""AINOS3-130 — the sweep harness must not silently measure nothing.

⚠ Three sweeps have now been voided by a config write that did nothing while
the results table looked entirely plausible:

  1. wrong FILE  — wrote cfg/InOut, the sim reads cfg/build/InOut
  2. wrong LABEL — a capture timeout recorded as a capture time (three reps at
                   exactly 559 s; identical values were the only symptom)
  3. wrong KNOB  — epoch does not move orbital phase; Orb_LEO.txt initialises
                   from Keplerian elements at sim start

So the load-bearing tests here are the READBACK GATES, not the arithmetic.
"""
import datetime as dt
import itertools
import os
import shutil
import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("sbn_python_client", MagicMock())
sys.modules.setdefault("message_headers", MagicMock())
# ⚠ Lives in training/, NOT in scenarios/. That directory contains a local
# `cmd.py` which shadows the stdlib `cmd` module; with it on sys.path at
# pytest's configure time, pytest's own `import pdb` dies with
# "module 'cmd' has no attribute 'Cmd'". Inserting the path here — at
# collection, after configure — keeps the shadowing contained.
_SCN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")
sys.path.insert(0, _SCN)

# ⚠ ...and by now pytest has already imported the STDLIB `cmd`, so a plain
# `from cmd import Commander` inside epoch_sweep would resolve to the wrong
# module. Bind the local one explicitly. Both halves of this dance are needed:
# path-first breaks pytest, stdlib-first breaks the import under test.
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("cmd", os.path.join(_SCN, "cmd.py"))
_cmd = importlib.util.module_from_spec(_spec)
sys.modules["cmd"] = _cmd
_spec.loader.exec_module(_cmd)

import epoch_sweep as es  # noqa: E402

CFG = os.path.join(_SCN, "..", "..", "..", "..", "cfg", "build", "InOut")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point every config path at throwaway copies — never the real tree."""
    for f in ("Orb_LEO.txt", "Inp_Sim.txt"):
        shutil.copy2(os.path.join(CFG, f), tmp_path / f)
    monkeypatch.setattr(es, "SWEEP_FIELDS", {
        "anomaly": (str(tmp_path / "Orb_LEO.txt"), "true anomaly", 360.0, "deg"),
        "raan": (str(tmp_path / "Orb_LEO.txt"),
                 "right ascension of ascending node", 360.0, "deg"),
        "epoch": (str(tmp_path / "Inp_Sim.txt"), None, None, None),
    })
    monkeypatch.setattr(es, "INP_SIM", str(tmp_path / "Inp_Sim.txt"))
    monkeypatch.setattr(es, "stack", lambda cmd, timeout=600: 0)
    return tmp_path


def _runner(positions, capture_at=None):
    """Fake run_mode yielding the given start positions, in order."""
    c = itertools.count()
    def fake(pt, mode, budget, args):
        if mode != "INERTIAL":
            return {"health": {"held_frac": 1.0}}
        i = next(c)
        cap = 240.0 if capture_at is not None and i == capture_at else None
        return {"csv": f"f{i}.csv", "elapsed_s": 400.0, "capture_s": cap,
                "captured": cap is not None, "timed_out": cap is None,
                "capture_gt_s": 390.0, "eclipse_fraction": 0.0, "frames": 2000,
                "recorded_epoch": "2025-10-20T17:43:22+00:00",
                "recorded_position": positions[min(i, len(positions) - 1)]}
    return fake


def _main(monkeypatch, sandbox, argv):
    monkeypatch.setattr(sys, "argv", ["epoch_sweep.py"] + argv)
    return es.main()


def test_no_test_ever_touches_the_real_config(sandbox, monkeypatch):
    """⚠ The guard that was missing on 2026-09-21.

    `write_epoch(when, path=INP_SIM)` bound its default at DEFINITION time, so
    monkeypatching `es.INP_SIM` did nothing and a sandboxed run rewrote the real
    cfg/build/InOut/Inp_Sim.txt to 21:01:15 — silently, while every visible
    result looked fine. Paths are now resolved at call time; this asserts it
    stays that way.
    """
    real = [os.path.abspath(os.path.join(CFG, f))
            for f in ("Inp_Sim.txt", "Orb_LEO.txt")]
    before = {p: open(p, "rb").read() for p in real}
    monkeypatch.setattr(es, "run_mode", _runner([(7000.0 + 900 * i, 0.0, 0.0)
                                                 for i in range(6)]))
    for sweep in ("epoch", "anomaly"):
        _main(monkeypatch, sandbox,
              ["--sweep", sweep, "--steps", "3", "--reps", "1",
               "--out", str(sandbox / f"{sweep}.json")])
    for p in real:
        assert open(p, "rb").read() == before[p], f"TEST MUTATED {p}"
    assert not [f for f in os.listdir(os.path.dirname(real[0]))
                if f.endswith(".sweep-backup")], "stale backup left behind"


# ---------------------------------------------------------------- gates

def test_phase_gate_voids_a_point_that_started_where_another_did(
        sandbox, monkeypatch, capsys):
    """⚠ THE gate. If the knob is not connected, every run starts in the same
    place — which is exactly how failure 3 went undetected for two sweeps."""
    same = [(7000.0, 0.0, 0.0)] * 6
    monkeypatch.setattr(es, "run_mode", _runner(same))
    _main(monkeypatch, sandbox,
          ["--sweep", "anomaly", "--steps", "3", "--reps", "1",
           "--out", str(sandbox / "o.json")])
    out = capsys.readouterr().out
    assert "PHASE NOT APPLIED" in out
    assert out.count("VOID — phase not applied") == 2   # points 2 and 3


def test_phase_gate_passes_when_each_point_starts_somewhere_new(
        sandbox, monkeypatch, capsys):
    moved = [(7000.0 + 900 * i, 900.0 * i, 0.0) for i in range(6)]
    monkeypatch.setattr(es, "run_mode", _runner(moved))
    _main(monkeypatch, sandbox,
          ["--sweep", "anomaly", "--steps", "3", "--reps", "1",
           "--out", str(sandbox / "o.json")])
    assert "PHASE NOT APPLIED" not in capsys.readouterr().out


def test_epoch_gate_voids_a_run_that_started_at_the_wrong_epoch(
        sandbox, monkeypatch, capsys):
    """Failure 1: the write went to a file the sim never reads."""
    monkeypatch.setattr(es, "run_mode", _runner([(7000.0, 0.0, 0.0)]))
    _main(monkeypatch, sandbox,
          ["--sweep", "epoch", "--steps", "3", "--reps", "1",
           "--out", str(sandbox / "o.json")])
    assert "EPOCH NOT APPLIED" in capsys.readouterr().out


# ------------------------------------------------------- config round-trip

def test_writes_the_build_copy_not_the_source():
    """⚠ cfg/build/launch.sh copies cfg/build/InOut into the sim."""
    assert es.INP_SIM.endswith(os.path.join("cfg", "build", "InOut", "Inp_Sim.txt"))
    assert es.ORB_LEO.endswith(os.path.join("cfg", "build", "InOut", "Orb_LEO.txt"))


def test_scalar_round_trip_changes_one_line_only(sandbox):
    p = str(sandbox / "Orb_LEO.txt")
    before = open(p).read().split("\n")
    assert es.read_scalar(p, "true anomaly") == 0.0
    es.write_scalar(p, "true anomaly", 135.0)
    assert es.read_scalar(p, "true anomaly") == 135.0
    after = open(p).read().split("\n")
    assert len(before) == len(after)
    assert sum(1 for a, b in zip(before, after) if a != b) == 1


def test_epoch_round_trip_keeps_whitespace_before_the_bang(sandbox):
    """42 may parse by column; ljust alone collapsed the space when the new
    value was longer than the old."""
    p = str(sandbox / "Inp_Sim.txt")
    es.write_epoch(dt.datetime(2025, 10, 20, 18, 30, 50, tzinfo=dt.timezone.utc), p)
    line = [l for l in open(p) if "Time (UTC)" in l][0]
    assert "  !" in line
    assert es.read_epoch(p).hour == 18


# ------------------------------------------------------------- labelling

def test_sweep_points_render_for_both_types():
    assert es.pt_label(3.5) == "3.5000"
    assert es.pt_label(dt.datetime(2025, 1, 2, tzinfo=dt.timezone.utc)).startswith("2025-01-02")


def test_offsets_wrap_for_phase_and_are_minutes_for_epoch():
    assert es.pt_offset(350.0, 20.0) == 330.0
    assert es.pt_offset(10.0, 350.0) == 20.0          # wraps
    base = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    assert es.pt_offset(base + dt.timedelta(minutes=30), base) == 30.0
