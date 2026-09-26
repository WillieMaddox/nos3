"""build_corpus_batch.restore_levels — a counter RESET is a restore too.

⚠ Why this exists. EX-0012.04/INERTIAL missed the AC8 footprint check 2/2 in the
2026-09-21 corpus and the miss was first read as an INERTIAL-specific rejection.
A live reproduction (2026-09-23) showed the FSW behaves identically in every mode
(LOAD of an unstaged file rejected, ACTIVATE rejected, CFE_TBL.Command*Counter
0->1/0->2) — the miss was the level-4 `cleanup(reset_counters=True)` wiping those
counters ~3 s after ACTIVATE, leaving an observable window (~2.8 s) shorter than
the CFE_TBL HK cadence (~4 s). That is a ~30 %/run sampling coin flip in ANY mode.

The fix makes `restore_levels` treat `cleanup(reset_counters=True)` as a restore,
so .03/.04/.05 collect at level 3 (LOAD+ACTIVATE, NO reset) where the counters
persist all run and are always sampled. These tests pin that behaviour AND its
boundary: benign cleanups (no reset_counters) must keep their top level, and the
existing `*_restore` scripts must be unchanged.
"""
import os
import sys

import pytest

_SCN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")
sys.path.insert(0, _SCN)

import build_corpus_batch as b  # noqa: E402

_SPARTA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
    "gsw", "attack_scripts", "sparta",
)


def _write(tmp_path, body):
    p = tmp_path / "atk.py"
    p.write_text(
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--attack-level', type=int, default=1, choices=[1, 2, 3, 4])\n"
        "class A:\n"
        "    def run(self):\n" + body
    )
    return str(p)


# ---- unit: the two erasing shapes and the benign one -----------------------

def test_reset_cleanup_is_flagged(tmp_path):
    """`cleanup(reset_counters=True)` at >=4 erases the footprint -> restore."""
    path = _write(tmp_path,
                  "        if self.attack_level >= 3:\n"
                  "            self.phase3_activate()\n"
                  "        if self.attack_level >= 4:\n"
                  "            self.phase5_cleanup(reset_counters=True)\n")
    assert b.restore_levels(path, [1, 2, 3, 4]) == {4}


def test_benign_cleanup_is_not_flagged(tmp_path):
    """A cleanup with no reset_counters (socket close, file removal) is kept."""
    path = _write(tmp_path,
                  "        if self.attack_level >= 4:\n"
                  "            self.phase_cleanup()\n")
    assert b.restore_levels(path, [1, 2, 3, 4]) == set()


def test_reset_counters_false_is_not_flagged(tmp_path):
    """Explicit reset_counters=False does not erase counters -> not a restore."""
    path = _write(tmp_path,
                  "        if self.attack_level >= 4:\n"
                  "            self.phase5_cleanup(reset_counters=False)\n")
    assert b.restore_levels(path, [1, 2, 3, 4]) == set()


def test_restore_phase_still_flagged(tmp_path):
    """The original `*_restore` shape keeps working (regression guard)."""
    path = _write(tmp_path,
                  "        if self.attack_level >= 4:\n"
                  "            self.phase4_restore(reset_counters=True)\n"
                  "        elif self.attack_level == 3:\n"
                  "            self.phase4_restore(reset_counters=False)\n")
    assert b.restore_levels(path, [1, 2, 3, 4]) == {3, 4}


# ---- integration: the real catalog scripts ---------------------------------

@pytest.mark.parametrize("rel", [
    "execution/ex_0012_modify_on_board_values/ex_0012_03_memory_write.py",
    "execution/ex_0012_modify_on_board_values/ex_0012_04_app_subscriber_tables.py",
    "execution/ex_0012_modify_on_board_values/ex_0012_05_scheduling_algorithm.py",
])
def test_real_table_scripts_collect_at_level_3(rel):
    """.03/.04/.05 must now collect at 3, not the reset-erased 4."""
    path = os.path.join(_SPARTA, rel)
    if not os.path.exists(path):
        pytest.skip(f"missing {rel}")
    levels = b.valid_levels(path)
    keep = [x for x in levels if x not in b.restore_levels(path, levels)]
    assert max(keep) == 3


@pytest.mark.parametrize("rel,top", [
    # benign cleanups keep their top level
    ("execution/ex_0010_file_operations/ex_0010_01_ransomware.py", 4),
    ("execution/ex_0011_exploit_safe_mode.py", 4),
    # value-restore scripts drop to the pure-attack level 2 (unchanged)
    ("execution/ex_0014_spoofing/ex_0014_03_sensor_data.py", 2),
    ("execution/ex_0012_modify_on_board_values/ex_0012_08_adcs_subsystem.py", 2),
])
def test_non_reset_scripts_unchanged(rel, top):
    path = os.path.join(_SPARTA, rel)
    if not os.path.exists(path):
        pytest.skip(f"missing {rel}")
    levels = b.valid_levels(path)
    keep = [x for x in levels if x not in b.restore_levels(path, levels)]
    assert max(keep) == top
