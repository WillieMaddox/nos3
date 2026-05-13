#!/usr/bin/env python3
"""Orchestrate the iforest routing dry-run baseline capture.

Workflow (per `project_iforest_live_deployment` follow-up #3):

  1. Back up the deployed `nos3_security.ini` + calibration JSON.
  2. Stage a calibration JSON COPY (`<cal>.dryrun-test`); flip the
     deployed ini's `CalibrationPath` at it so any incidental write
     (recalibration would skip in dry-run anyway, but defense-in-depth)
     cannot corrupt the production calibration.
  3. Patch the deployed ini: `RuntimeRouting=true`, `RoutingDryRun=true`,
     plus a faster `RoutingDryRunReportEvery` so the operator gets a
     histogram update every ~40 s instead of every 3 min.
  4. `docker restart sc01-onair`; wait for the plugin's
     `[iforest] routing ENABLED (DRY-RUN)` init line so we know the new
     config is live.
  5. Run `run_baseline.py` to actively exercise representative scenarios.
     Dry-run only learns from modes the stack actually visits — passive
     observation on a stack camped in one mode is wasted wall-clock.
  6. After the baseline returns, dump the final histogram from
     `docker logs sc01-onair` and print a `RoutingModeMap` template the
     operator fills in by hand. The mode-value → scenario semantics are
     mission-specific; this script will NOT auto-guess.
  7. Print restore commands. By default the dry-run config is LEFT IN
     PLACE so the operator can iterate (run more scenarios, observe
     more modes) before reverting. Pass `--restore-on-exit` to auto-
     revert at the end.

What this script does NOT do:
  - Flip `RoutingDryRun=false`. That's a manual, deliberate edit after
    the operator has reviewed the histogram and populated the map.
  - Touch the production calibration JSON. The test copy is independent.
  - Run any attack scripts. Dry-run is observe-only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
DEPLOYED_INI = os.path.join(
    REPO_ROOT, "fsw/build/exe/cpu1/cf/onair/nos3_security.ini")
DEFAULT_CALIBRATION = os.path.join(
    REPO_ROOT, "data/onair/models/iforest_per_scenario_v3_multiuptime.calibration.json")
DEFAULT_PICKLE = os.path.join(
    REPO_ROOT, "data/onair/models/iforest_per_scenario_v3_multiuptime.pkl")
RUN_BASELINE = os.path.join(os.path.dirname(__file__), "run_baseline.py")

INI_BAK_SUFFIX = ".dryrun-backup"
CAL_TEST_SUFFIX = ".dryrun-test"

_RECAL_TEST_PATH_REL = (
    "../../../../data/onair/models/"
    "iforest_per_scenario_v3_multiuptime.calibration.json.dryrun-test"
)

DRY_RUN_LOG_RE = re.compile(
    r"\[iforest\]\[route\]\[dry-run\] frame=(\d+) "
    r"observed N=(\d+) \(in-map: ([^)]+)\) top: (.+)"
)
PLUGIN_READY_RE = re.compile(r"\[iforest\] routing ENABLED \(DRY-RUN\)")


def _say(msg: str) -> None:
    """Stamped step indicator so operator can correlate with docker logs."""
    print(f"[dryrun-routing {dt.datetime.now(dt.timezone.utc):%H:%M:%SZ}] {msg}",
          flush=True)


def precheck() -> None:
    """Sanity checks before we touch anything."""
    if not os.path.exists(DEPLOYED_INI):
        raise SystemExit(
            f"deployed ini not found at {DEPLOYED_INI} — has the stack been "
            f"built? Try `make launch-quiet` first.")
    if not os.path.exists(DEFAULT_CALIBRATION):
        raise SystemExit(
            f"calibration JSON not found at {DEFAULT_CALIBRATION}.")
    if not os.path.exists(DEFAULT_PICKLE):
        raise SystemExit(
            f"model pickle not found at {DEFAULT_PICKLE}.")
    if not os.path.exists(RUN_BASELINE):
        raise SystemExit(
            f"run_baseline.py not found at {RUN_BASELINE}.")
    # Block re-runs that would clobber existing backups.
    if os.path.exists(DEPLOYED_INI + INI_BAK_SUFFIX):
        raise SystemExit(
            f"backup already exists at {DEPLOYED_INI + INI_BAK_SUFFIX}. "
            f"Restore it first:\n"
            f"  cp '{DEPLOYED_INI + INI_BAK_SUFFIX}' '{DEPLOYED_INI}'\n"
            f"  rm '{DEPLOYED_INI + INI_BAK_SUFFIX}'\n"
            f"Then re-run this script.")
    # Confirm sc01-onair is up so we don't waste setup work.
    try:
        out = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.State.Running}}", "sc01-onair"],
            text=True, stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"docker inspect sc01-onair failed: {e.output.strip()}. "
            f"Bring the stack up with `make launch-quiet`.")
    if out != "true":
        raise SystemExit(
            f"sc01-onair is not running (state={out!r}). "
            f"`make launch-quiet` first.")


def list_pickle_scenarios() -> tuple[list[str], str]:
    """Read the pickle's `models` keys + the `label_column` it was trained on.

    `label_column` distinguishes v3 (scenario-keyed) from v4 (mode-keyed)
    pickles. v3 pickles predate the field; `art.get("label_column", "__scenario")`
    keeps them working without changes.
    """
    import pickle  # imported here to keep precheck fast on broken pickles
    with open(DEFAULT_PICKLE, "rb") as f:
        art = pickle.load(f)
    keys = sorted(art.get("models", {}).keys())
    label_column = art.get("label_column", "__scenario")
    return keys, label_column


def backup_and_patch_ini(report_every: int) -> None:
    """Stage backups + flip the deployed ini into dry-run mode.

    Edits are intentionally line-based on the existing file so any custom
    operator overrides outside the routing block survive unchanged.
    """
    shutil.copy(DEPLOYED_INI, DEPLOYED_INI + INI_BAK_SUFFIX)
    shutil.copy(DEFAULT_CALIBRATION, DEFAULT_CALIBRATION + CAL_TEST_SUFFIX)
    _say(f"backups: {DEPLOYED_INI + INI_BAK_SUFFIX} + "
         f"{DEFAULT_CALIBRATION + CAL_TEST_SUFFIX}")

    with open(DEPLOYED_INI) as f:
        text = f.read()

    # The shipped ini comments these out under [ISOLATION_FOREST]. Replace
    # the commented sentinels with active assignments; idempotency relies
    # on the precheck refusing to run when a backup already exists.
    # Patterns require whitespace around `=` so they only match the
    # template lines (`# Key = value`) and skip prose-style comments
    # like `# RoutingDryRun=true is the safe path...`.
    replacements = [
        (r"^CalibrationPath\s*=.*$",
         f"CalibrationPath = {_RECAL_TEST_PATH_REL}"),
        (r"^#\s+RuntimeRouting\s+=.*$", "RuntimeRouting = true"),
        (r"^#\s+RoutingDryRun\s+=.*$", "RoutingDryRun = true"),
        (r"^#\s+RoutingDryRunReportEvery\s+=.*$",
         f"RoutingDryRunReportEvery = {report_every}"),
    ]
    new_text = text
    for pat, repl in replacements:
        new_text, n = re.subn(pat, repl, new_text, flags=re.MULTILINE)
        if n == 0:
            # Defensive: if the ini was hand-edited and the commented
            # template line is gone, the routing knobs would silently
            # stay defaulted. Loud error instead.
            raise SystemExit(
                f"deployed ini missing the expected template line for "
                f"pattern {pat!r}; refusing to patch. Restore from "
                f"{DEPLOYED_INI + INI_BAK_SUFFIX} and inspect the file.")

    with open(DEPLOYED_INI, "w") as f:
        f.write(new_text)
    _say("ini patched: RuntimeRouting=true RoutingDryRun=true "
         f"RoutingDryRunReportEvery={report_every}")


def restart_onair(wait_timeout_s: int = 180) -> None:
    """Restart sc01-onair and block until the new plugin init line lands.

    A docker restart returns quickly, but the OnAIR driver does its
    sklearn install + 20 s SBN handshake before importing the plugin —
    so the operationally meaningful "ready" signal is the init line in
    the container's stdout, not the container's running state.
    """
    _say("docker restart sc01-onair")
    subprocess.run(["docker", "restart", "sc01-onair"],
                   check=True, capture_output=True)
    deadline = time.monotonic() + wait_timeout_s
    while time.monotonic() < deadline:
        try:
            logs = subprocess.check_output(
                ["docker", "logs", "--since", "5m", "sc01-onair"],
                text=True, stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError:
            time.sleep(2); continue
        if PLUGIN_READY_RE.search(logs):
            _say("plugin reported routing ENABLED (DRY-RUN)")
            return
        time.sleep(3)
    raise SystemExit(
        f"plugin did not announce DRY-RUN within {wait_timeout_s}s. "
        f"Check `docker logs sc01-onair` for an init failure.")


def run_baseline(scale: float, only: list[str] | None, extra_args: list[str]) -> int:
    """Invoke run_baseline.py as a subprocess.

    Returning the exit code lets the caller distinguish a baseline that
    completed (exit 0) from one that crashed midway — in the latter case
    the dry-run histogram still has the data we collected up to the
    crash and is worth reporting.
    """
    cmd = [
        sys.executable, RUN_BASELINE,
        "--auto-discover",
        "--scale", str(scale),
    ]
    if only:
        cmd += ["--only", *only]
    cmd += extra_args
    _say(f"launching baseline: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT)
    _say(f"baseline returned exit={proc.returncode}")
    return proc.returncode


def fetch_histogram() -> tuple[Counter[str], list[tuple]]:
    """Parse the most recent dry-run log line per session start.

    The plugin emits the histogram every N frames as a running total; the
    LAST line is the cumulative tally for the session. Earlier lines are
    just progress updates and are skipped here, but returned so the
    caller can show the growth pattern if a verbose dump is wanted.
    """
    logs = subprocess.check_output(
        ["docker", "logs", "--since", "1h", "sc01-onair"],
        text=True, stderr=subprocess.STDOUT,
    )
    all_matches: list[tuple] = []
    for line in logs.splitlines():
        m = DRY_RUN_LOG_RE.search(line)
        if not m:
            continue
        frame = int(m.group(1))
        total = int(m.group(2))
        coverage = m.group(3)
        top_str = m.group(4)
        # top is "k:v, k:v, ..." up to top 8; reconstruct the visible
        # tally. The full counter lives inside the plugin process; we
        # only see what got into the log.
        observed: Counter[str] = Counter()
        for chunk in top_str.split(","):
            k, _, v = chunk.strip().partition(":")
            if k and v.isdigit():
                observed[k] = int(v)
        all_matches.append((frame, total, coverage, observed))
    if not all_matches:
        return Counter(), []
    # Take the last (latest) line as the cumulative session histogram.
    _, _, _, latest = all_matches[-1]
    return latest, all_matches


_V4_IDENTITY_MAP = {
    "0": "MODE_PASSIVE",
    "1": "MODE_BDOT",
    "2": "MODE_SUNSAFE",
    "3": "MODE_INERTIAL",
}


def print_suggested_map(
    observed: Counter[str], scenarios: list[str], label_column: str = "__scenario",
) -> None:
    """Emit a JSON skeleton for RoutingModeMap + a guidance block.

    Behaviour depends on which `label_column` the loaded pickle was trained
    on:
    - `__scenario` (v3): operator fills in scenario names by hand from
      mission-specific ADCS mode enum semantics. We refuse to guess — a
      wrong guess silently mis-routes every frame at that mode value with
      up to −0.086 per-frame cost (see project_iforest_quiescent_pathology).
    - `__adcs_mode` (v4): the mapping is identity-by-construction
      (`0 → MODE_PASSIVE`, etc.). We pre-fill the template; operator just
      needs to confirm the observed mode values match the four supported
      modes before pasting.
    """
    print()
    print("=" * 72)
    print("DRY-RUN HISTOGRAM (cumulative observed mode values, latest log line)")
    print("=" * 72)
    total = sum(observed.values())
    if total == 0:
        print("No dry-run histogram lines found in docker logs. Possible causes:")
        print("  - Baseline didn't run long enough to hit a report interval.")
        print("  - Plugin init failed; check `docker logs sc01-onair`.")
        print("  - RoutingSourceHeader was missing from headers.")
        return
    for value, count in observed.most_common():
        pct = 100.0 * count / total if total else 0.0
        print(f"  ADCS_GNC.Mode={value:>4}  {count:>6} frames  ({pct:5.1f}%)")
    print()
    print(f"pickle label_column: {label_column!r}")
    print(f"available pickle scenarios: {scenarios}")
    print()
    if label_column == "__adcs_mode":
        # Identity-by-construction: every observed mode value maps to its
        # canonical MODE_<NAME>. Drop any observed value that isn't a known
        # mode (the operator probably wants to investigate it separately).
        template = {
            value: _V4_IDENTITY_MAP[value]
            for value in observed.keys() if value in _V4_IDENTITY_MAP
        }
        print("Suggested RoutingModeMap (v4 identity-by-construction):")
        unknown = [v for v in observed.keys() if v not in _V4_IDENTITY_MAP]
        if unknown:
            print(f"  WARNING: observed mode values not in identity map: {unknown}")
            print("  Inspect those values; they will fall back to the static scenario.")
    else:
        print("Suggested RoutingModeMap template (FILL IN scenario names):")
        template = {value: "<scenario>" for value in observed.keys()}
    print("  " + json.dumps(template))
    print()
    print("Once you've filled in the map:")
    print(f"  1. Edit {DEPLOYED_INI} — set RoutingModeMap to the JSON above")
    print("     (single line, no spaces inside the JSON object).")
    print("  2. Optional: set RoutingDryRun = false to flip the apply path on.")
    print("  3. docker restart sc01-onair")
    print(
        "  4. Watch: docker logs sc01-onair 2>&1 | grep '\\[iforest\\]\\[route\\]'")
    print()
    print("To restore the original ini + remove the test calibration:")
    print(f"  cp '{DEPLOYED_INI + INI_BAK_SUFFIX}' '{DEPLOYED_INI}'")
    print(f"  rm '{DEPLOYED_INI + INI_BAK_SUFFIX}' "
          f"'{DEFAULT_CALIBRATION + CAL_TEST_SUFFIX}'")
    print("  docker restart sc01-onair")


def restore() -> None:
    """Auto-revert helper for --restore-on-exit."""
    bak = DEPLOYED_INI + INI_BAK_SUFFIX
    test_cal = DEFAULT_CALIBRATION + CAL_TEST_SUFFIX
    if os.path.exists(bak):
        shutil.move(bak, DEPLOYED_INI)
        _say(f"restored ini from {bak}")
    if os.path.exists(test_cal):
        os.remove(test_cal)
        _say(f"removed test calibration {test_cal}")
    _say("docker restart sc01-onair (post-restore)")
    subprocess.run(["docker", "restart", "sc01-onair"],
                   check=True, capture_output=True)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--scale", type=float, default=1.0,
                   help="run_baseline.py scale factor "
                        "(1.0 = full 25 min, 0.2 ≈ 5 min for a fast sanity check)")
    p.add_argument("--only", nargs="+", default=None,
                   help="run_baseline.py --only filter (e.g. nominal_ops maneuvers)")
    p.add_argument("--report-every", type=int, default=200,
                   help="frames between dry-run histogram log lines "
                        "(200 ≈ 40 s; lower = noisier, faster feedback)")
    p.add_argument("--restore-on-exit", action="store_true",
                   help="revert the ini + remove the test calibration when "
                        "the script exits (default: leave dry-run live so "
                        "the operator can iterate)")
    p.add_argument("--skip-baseline", action="store_true",
                   help="set up dry-run + collect whatever is already in the "
                        "log; don't kick off run_baseline.py "
                        "(useful when you want to drive scenarios manually)")
    p.add_argument("--baseline-arg", action="append", default=[],
                   help="extra arg passed through to run_baseline.py "
                        "(repeatable, e.g. --baseline-arg --reset-between)")
    args = p.parse_args()

    _say("precheck")
    precheck()
    scenarios, label_column = list_pickle_scenarios()
    _say(f"pickle scenarios: {scenarios} (label_column={label_column!r})")

    _say("backup + patch deployed ini")
    backup_and_patch_ini(report_every=args.report_every)

    try:
        restart_onair()

        if args.skip_baseline:
            _say("--skip-baseline: not invoking run_baseline.py; "
                 "exercise scenarios manually then re-run with "
                 "--skip-baseline + your map populated")
        else:
            rc = run_baseline(
                scale=args.scale, only=args.only,
                extra_args=args.baseline_arg,
            )
            if rc != 0:
                _say(f"run_baseline.py exited non-zero ({rc}); "
                     "reporting whatever histogram was captured")

        observed, _ = fetch_histogram()
        print_suggested_map(observed, scenarios, label_column=label_column)
    finally:
        if args.restore_on_exit:
            _say("--restore-on-exit: reverting")
            restore()
        else:
            _say("dry-run config LEFT IN PLACE. Restore commands above. "
                 "Re-run this script with --skip-baseline to refresh "
                 "the histogram, or pass --restore-on-exit next time.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
