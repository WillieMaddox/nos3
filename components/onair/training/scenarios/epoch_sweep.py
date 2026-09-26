#!/usr/bin/env python3
"""Measure time-to-tracker-capture and eclipse fraction vs simulation epoch.

AINOS3-130 (sim-epoch-sweep). Harness for AC1-AC3, AC7 and the AC8 kill switch.

⚠ Every run this project has collected launches from ONE instant —
`cfg/InOut/Inp_Sim.txt`, `10 20 2025 / 17 43 20.00`. Two things follow that
nobody has checked:

  * The INERTIAL capture wait may be an artifact of that single geometry.
    Measured 2026-09-21: SUNSAFE 457.7 s vs INERTIAL 1087.8 s, a +10.5 min
    penalty spent waiting for the boresight to clear the Earth exclusion cone.
    Across 95 planned INERTIAL runs that is ~16.6 h.
  * The corpus has ZERO eclipse variation. SunValid / Fss.valid / Css.valid all
    track orbital lighting, and every run samples the same phase.

⚠ Reducing initial body rates is NOT the lever. `SC_NOS3.txt` already sets
`Ang Vel = 0 0 0`, and `run_attack.py:243-292` records that damping made capture
WORSE — it parks the vehicle near the orbital rate in an LVLH lock that left 26
runs at 0-49.8 % capture. Fast tumble is the mechanism that ACHIEVES capture.
The lever is WHERE IN THE ORBIT the run starts.

Method: step the epoch across one orbital period, launch, hold INERTIAL, and
record when capture is achieved — reusing `inertial_capture.py`'s definition
(sustained qValid AND a controller producing varying torque), not a qValid
threshold, because a boundary flicker is not capture.

    python3 epoch_sweep.py --steps 8 --period-min 95 --out sweep.json
    python3 epoch_sweep.py --steps 3 --period-min 95 --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import math
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
# ⚠ cfg/build/InOut, NOT cfg/InOut. `cfg/build/launch.sh:97` does
#     cp -r $BASE_DIR/cfg/build/InOut $USER_NOS3_DIR/42/NOS3InOut
# on every launch, and `cfg/InOut` is only copied into `cfg/build` by
# `make config`. Editing the source therefore changes NOTHING about the next
# launch — measured 2026-09-21: an 8-epoch sweep wrote cfg/InOut and all eight
# runs started at 17:43:2x, the unchanged build value. The sweep looked
# plausible (capture times 498/437/285/225 s) and was pure run-to-run variance.
# Caught only because AINOS3-130 AC6 requires checking the RECORDED epoch.
INP_SIM = os.path.join(ROOT, "cfg", "build", "InOut", "Inp_Sim.txt")
ORB_LEO = os.path.join(ROOT, "cfg", "build", "InOut", "Orb_LEO.txt")

# ⚠ EPOCH IS NOT THE ORBITAL-PHASE LEVER. `Orb_LEO.txt` initialises the orbit
# from Keplerian elements with `True Anomaly = 0`, applied at sim start, so
# EVERY launch puts the satellite at the same point in its orbit no matter what
# the clock says. Shifting the epoch moves the Sun and the Earth's rotation, not
# the spacecraft's phase — measured 2026-09-21: a full 95 min epoch sweep gave
# eclipse fraction 0.0000 at all 7 points and capture times with no relation to
# offset (1/7 captured, the rest timed out), which is the known 2.2x
# fixed-phase noise.
#
#   True Anomaly  -> where in the orbit the run starts   (the capture lever)
#   RAAN          -> the orbit plane vs the Sun          (the eclipse lever)
SWEEP_FIELDS = {
    "anomaly": (ORB_LEO, "true anomaly", 360.0, "deg"),
    "raan":    (ORB_LEO, "right ascension of ascending node", 360.0, "deg"),
    "epoch":   (INP_SIM, None, None, None),
}
CSV_DIR = os.path.join(ROOT, "data", "onair", "csv_blended")

sys.path.insert(0, HERE)
import inertial_capture as ic  # noqa: E402
import run_attack as ra  # noqa: E402
from cmd import Commander  # noqa: E402


def log(msg):
    print(f"[{dt.datetime.now(dt.timezone.utc):%H:%M:%SZ}] {msg}", flush=True)


def read_scalar(path, needle):
    """First numeric value on the line whose comment contains `needle`."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "!" not in line:
                continue
            val, _, comment = line.partition("!")
            if needle in comment.lower():
                try:
                    return float(val.split()[0])
                except (ValueError, IndexError):
                    return None
    return None


def write_scalar(path, needle, value):
    """Rewrite that one value, preserving the rest of the file verbatim."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "!" in line:
                val, bang, comment = line.partition("!")
                if needle in comment.lower():
                    new = f"{value:.4f}"
                    line = new.ljust(max(len(val), len(new) + 2)) + bang + comment
            out.append(line)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(out)


def first_position(csv_path):
    """First GPS ECEF fix — where the run actually STARTED in its orbit.

    ⚠ The phase-sweep equivalent of the AC6 epoch readback, and it exists for
    the same reason: two sweeps have now been voided by a config write that
    silently did nothing (wrong file, then wrong knob). If two sweep points
    report the same starting position, the knob is not connected.
    """
    import csv as _csv
    try:
        with open(csv_path) as fh:
            for row in _csv.DictReader(fh):
                try:
                    v = tuple(float(row[f"NOVATEL.Novatel_oem615.ECEF{a}"]) for a in "XYZ")
                except (KeyError, ValueError, TypeError):
                    continue
                if any(v):
                    return v
    except OSError:
        pass
    return None


def read_epoch(path=None):
    # ⚠ Resolved at CALL time, not def time. `path=INP_SIM` binds the module
    # value when the function is defined, so a test that monkeypatches
    # es.INP_SIM still writes the REAL config — which is exactly what happened
    # on 2026-09-21: a sandboxed test silently rewrote
    # cfg/build/InOut/Inp_Sim.txt to 21:01:15.
    path = path or INP_SIM
    date_parts = time_parts = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "!" not in line:
                continue
            val, _, comment = line.partition("!")
            c = comment.lower()
            if "date" in c and "utc" in c:
                date_parts = [int(float(x)) for x in val.split()[:3]]
            elif "time" in c and "utc" in c:
                time_parts = [float(x) for x in val.split()[:3]]
    mo, dy, yr = date_parts
    hh, mm, ss = time_parts
    return dt.datetime(yr, mo, dy, int(hh), int(mm), int(ss), tzinfo=dt.timezone.utc)


def write_epoch(when: dt.datetime, path=None):
    path = path or INP_SIM
    """Rewrite only the date/time lines, preserving everything else verbatim."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "!" in line:
                val, bang, comment = line.partition("!")
                c = comment.lower()
                # ⚠ Always keep whitespace before the `!`. ljust alone
                # collapses it when the new value is longer than the old
                # ("17 43 20  " -> "18 30 50.00!"), and 42's reader may be
                # column-sensitive.
                def _fit(new, old):
                    return new.ljust(max(len(old), len(new) + 2))
                if "date" in c and "utc" in c:
                    line = _fit(f"{when.month:02d} {when.day:02d} {when.year}", val) + bang + comment
                elif "time" in c and "utc" in c:
                    line = _fit(f"{when.hour:02d} {when.minute:02d} {when.second:05.2f}", val) + bang + comment
            out.append(line)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(out)


def stack(cmd, timeout=600):
    return subprocess.run(["make", cmd], cwd=ROOT, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT).returncode


def newest_blended(before: set):
    import glob
    for _ in range(120):
        now = set(glob.glob(os.path.join(CSV_DIR, "csv_out_*.csv")))
        fresh = now - before
        if fresh:
            return sorted(fresh)[-1]
        time.sleep(2)
    return None


def first_sim_time(csv_path):
    """The first OnAIR.SimTimeUTC in the file — the epoch the run REALLY began at.

    ⚠ This is the AC6 check, and it is not ceremony. The 2026-09-21 sweep wrote
    the wrong copy of Inp_Sim.txt, so every run silently started at the same
    epoch while the results table showed a plausible spread. Nothing else in
    the pipeline would have caught it.
    """
    import csv as _csv
    try:
        with open(csv_path) as fh:
            for row in _csv.DictReader(fh):
                v = row.get("OnAIR.SimTimeUTC")
                if v:
                    return v
    except OSError:
        pass
    return None


def mode_health(csv_path, mode, tail=400):
    """Did `mode` hold, and are body rates bounded? (AC7)

    Deliberately NOT a capture check — only INERTIAL has one. For SUNSAFE and
    BDOT the question is whether the commanded mode stuck and the vehicle
    stayed under control, which is what an eclipse-phase epoch could plausibly
    break.
    """
    import ast as _ast
    import csv as _csv
    import math as _math
    want = {"PASSIVE": "0", "BDOT": "1", "SUNSAFE": "2", "INERTIAL": "3"}[mode]
    rows = []
    with open(csv_path) as fh:
        for r in _csv.DictReader(fh):
            rows.append((r.get("ADCS_GNC.Mode"), r.get("ADCS_GNC.wbn"), r.get("ADCS_GNC.SunValid")))
    # ⚠ Measure the SETTLED part of the hold, not the slew into it. The mode
    # is commanded from whatever the previous mode left, so the first frames
    # carry a transient: the first cut of this reported SUNSAFE at 2.05 deg/s
    # and BDOT at 1.09 deg/s, which is the slew, not the held state.
    rows = rows[-tail:]
    settled = rows[len(rows) // 2:] or rows
    if not rows:
        return {"error": "no frames"}
    held = sum(1 for m, _, _ in rows if m == want) / len(rows)
    mags = []
    for _, w, _ in settled:
        try:
            v = _ast.literal_eval(w)
            mags.append(_math.sqrt(sum(x * x for x in v)) * 57.2958)
        except Exception:
            pass
    sun = [s for _, _, s in rows if s not in (None, "", "[0]")]
    return {
        "held_frac": round(held, 3),
        "rate_deg_s_max": round(max(mags), 4) if mags else None,
        "rate_deg_s_med": round(statistics.median(mags), 4) if mags else None,
        "sunvalid_frac": round(sum(1 for s in sun if s == "1") / len(sun), 3) if sun else None,
    }


def eclipse_fraction(csv_path):
    """Fraction of frames with SunValid == 0, i.e. in eclipse."""
    import csv as _csv
    n = dark = 0
    with open(csv_path) as fh:
        for r in _csv.DictReader(fh):
            v = r.get("ADCS_GNC.SunValid")
            if v in (None, "", "[0]"):
                continue
            n += 1
            dark += (v == "0")
    return (dark / n) if n else None, n


# How close to the budget still counts as "timed out". The scenario polls
# every CAPTURE_POLL_S (30 s), so a genuine capture lands well clear of this.
TIMEOUT_SLACK_S = 20.0


def pt_label(v):
    """Render a sweep point, whichever kind it is.

    ⚠ A sweep point is a datetime for --sweep epoch and a float (degrees) for
    anomaly/raan. Everything downstream — logs, row keys, the JSON — has to
    stop assuming datetime.
    """
    return v.isoformat() if hasattr(v, "isoformat") else f"{v:.4f}"


def pt_offset(v, base):
    """Distance from the baseline point, in minutes (epoch) or degrees (phase)."""
    if hasattr(v, "isoformat"):
        return round((v - base).total_seconds() / 60, 1)
    return round((v - base) % 360.0, 1)


def run_mode(epoch, mode, budget, args):
    """One mode, in its own freshly launched stack, at `epoch`.

    `budget` bounds the INERTIAL capture wait (the kill switch); pass None for
    the modes that have no capture wait.

    Returns a dict; never raises — a failed epoch should not end the sweep.
    """
    import glob
    before = set(glob.glob(os.path.join(CSV_DIR, "csv_out_*.csv")))
    stack("stop")
    if stack("launch-quiet") != 0:
        return {"error": f"{mode}: launch failed"}
    csv_path = newest_blended(before)
    if not csv_path:
        stack("stop")
        return {"error": f"{mode}: no fresh blended CSV"}

    out = {"csv": os.path.basename(csv_path)}
    try:
        host = ra.auto_discover_fsw_host()
        c = Commander(fsw_host=host, dry_run=False)
        _n, _d, scn_fn = ra.find_scenario(f"single_mode_hold_{mode}")
        hold = args.hold_s if mode == "INERTIAL" else args.other_hold_s

        # ⚠ Patch the module constant rather than hand-rolling the wait:
        # make_scenario_single_mode_hold("INERTIAL") also runs
        # configure_inertial (the AINOS3-86 orbit-normal target attitude and
        # the star-tracker enable). Skipping that measures a configuration the
        # corpus never flies.
        prev = ra.CAPTURE_TIMEOUT_S
        if budget is not None:
            ra.CAPTURE_TIMEOUT_S = budget
        t0 = time.monotonic()
        try:
            scn_fn(c, hold)
            out["elapsed_s"] = round(time.monotonic() - t0, 1)
        finally:
            ra.CAPTURE_TIMEOUT_S = prev

        if mode == "INERTIAL":
            # The scenario proceeds past a timeout by design, so ask the
            # telemetry whether capture actually happened.
            try:
                sample = ic.sample(csv_path, tail_frames=400) or {}
                out["sample"] = sample
                verdict_ok = bool(ic.verdict(sample)[0])
            except Exception:                      # noqa: BLE001
                verdict_ok = False

            wait_s = (out["elapsed_s"] - hold) if out.get("elapsed_s") else None

            # ⚠ A tail-sample verdict ALONE is not evidence of capture within
            # budget. After the wait times out the scenario still runs its
            # 150 s hold, and the tracker often captures during it — so the
            # tail reads "captured" for a run that blew the budget, and
            # `elapsed - hold` then reports the CEILING as if it were a
            # measurement. Observed 2026-09-21: three reps all logged exactly
            # 559 s, which is the 9 min timeout plus overhead, not a time.
            # Identical values to the second were the only visible symptom.
            out["timed_out"] = bool(budget is not None and wait_s is not None and wait_s >= budget - TIMEOUT_SLACK_S)
            out["captured"] = verdict_ok and not out["timed_out"]
            out["capture_s"] = round(wait_s, 1) if out["captured"] else None
            if out["timed_out"]:
                # Keep the censored bound; it is data, just not a capture time.
                out["capture_gt_s"] = round(wait_s, 1) if wait_s else None
                out["captured_late_in_hold"] = verdict_ok
        else:
            out["health"] = mode_health(csv_path, mode)

        ecl, nfr = eclipse_fraction(csv_path)
        out["eclipse_fraction"] = round(ecl, 4) if ecl is not None else None
        out["frames"] = nfr
        out["recorded_epoch"] = first_sim_time(csv_path)
        out["recorded_position"] = first_position(csv_path)
    except Exception as exc:                       # noqa: BLE001
        out["error"] = f"{mode}: {exc}"
    finally:
        stack("stop")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sweep", default="anomaly", choices=sorted(SWEEP_FIELDS),
                   help="what to vary. 'anomaly' = True Anomaly, WHERE IN THE "
                        "ORBIT the run starts (the capture lever). 'raan' = the "
                        "orbit plane vs the Sun (the eclipse lever). ⚠ 'epoch' "
                        "is kept only to reproduce the 2026-09-21 null: it does "
                        "NOT move orbital phase, because Orb_LEO.txt "
                        "initialises from Keplerian elements at sim start.")
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--reps", type=int, default=3,
                   help="INERTIAL runs per epoch. ⚠ Capture time varies 2.2x at "
                        "a FIXED epoch (225-498 s, measured 2026-09-21), so a "
                        "single run cannot separate a better orbital phase from "
                        "a lucky draw. Epochs are ranked on the MEDIAN.")
    p.add_argument("--skip-first", action="store_true",
                   help="do not re-run plan[0] (the unchanged epoch); seed it "
                        "from --prior-capture-s instead")
    p.add_argument("--prior-capture-s", default="225,285,437,498",
                   help="known capture times for plan[0], comma-separated. "
                        "⚠ Default is the 2026-09-21 sweep, whose epoch writes "
                        "never took effect — so all 8 of its runs sampled THIS "
                        "epoch. 4 captured; the other 4 were aborted at the "
                        "running best and are CENSORED (slower than 225-285 s, "
                        "unknown by how much), so this median is biased LOW.")
    p.add_argument("--prior-censored", type=int, default=4,
                   help="how many prior runs were aborted rather than measured")
    p.add_argument("--min-separation-km", type=float, default=50.0,
                   help="two sweep points starting closer than this are treated "
                        "as the SAME orbital phase, and the later one is voided")
    p.add_argument("--abort-factor", type=float, default=1.5,
                   help="per-run capture budget = best median x this. Above 1 so "
                        "a rep that is merely unlucky is not mistaken for a bad "
                        "epoch.")
    p.add_argument("--period-min", type=float, default=95.0,
                   help="orbital period; epochs are stepped evenly across it")
    p.add_argument("--timeout-min", type=float, default=45.0)
    p.add_argument("--other-hold-s", type=int, default=90,
                   help="SUNSAFE/BDOT hold per epoch for the AC7 health check")
    p.add_argument("--baseline-s", type=float, default=630.0,
                   help="opening ceiling for the kill switch;every epoch after "
                        "that must beat the running best. ⚠ The 630 s default "
                        "is an UPPER BOUND, not a capture measurement — it is "
                        "the INERTIAL-minus-SUNSAFE wallclock delta from the "
                        "2026-09-21 smoke test, which also contains the pre "
                        "block. Epoch 0 (the unchanged config) is the real "
                        "status-quo figure.")
    p.add_argument("--hold-s", type=int, default=150,
                   help="INERTIAL hold duration AFTER capture, matching the "
                        "collection's --pre-seconds so the timing is comparable")
    p.add_argument("--out", default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="print the epoch plan and exit; touches nothing")
    args = p.parse_args()

    path, needle, span, unit = SWEEP_FIELDS[args.sweep]
    if args.sweep == "epoch":
        base = read_epoch()
        step = dt.timedelta(minutes=args.period_min / args.steps)
        plan = [base + i * step for i in range(args.steps)]
        labels = [pt_label(e) for e in plan]
        print(f"baseline epoch : {pt_label(base)}  ({path})")
        print("⚠ epoch does NOT move orbital phase — see SWEEP_FIELDS. This "
              "mode reproduces a known null.")
    else:
        base = read_scalar(path, needle) or 0.0
        step = span / args.steps
        plan = [(base + i * step) % span for i in range(args.steps)]
        labels = [f"{v:.1f} {unit}" for v in plan]
        print(f"baseline {args.sweep:<7}: {base:.4f} {unit}  ({path})")
    print(f"plan           : {args.steps} points across {span or args.period_min:.0f} {unit or 'min'}")
    for i, l in enumerate(labels):
        print(f"   {i}: {l}")
    per_rep_min = 8.0          # launch + capture + hold, measured 2026-09-21
    per_mode_min = 2.5
    to_run = args.steps - (1 if args.skip_first else 0)
    est = to_run * args.reps * per_rep_min + to_run * 2 * per_mode_min
    print(f"reps           : {args.reps} per epoch, ranked on the MEDIAN")
    if args.skip_first:
        prior = [float(x) for x in args.prior_capture_s.split(",") if x.strip()]
        med = statistics.median(prior) if prior else None
        print(f"epoch 0        : SKIPPED, seeded from {len(prior)} prior run(s) "
              f"median {med:.0f}s "
              f"⚠ {args.prior_censored} censored, so biased LOW")
    print(f"epochs to run  : {to_run} of {args.steps}")
    print(f"config written : {path}")
    print(f"                 field: {needle or 'Date/Time (UTC)'}")
    print(f"                 (cfg/build/launch.sh copies cfg/build/InOut into "
          f"the sim; cfg/InOut is only the source `make config` builds from)")
    print(f"rough cost     : ~{est/60:.1f} h worst case; less as the kill switch "
          f"tightens (budget = best median x {args.abort_factor})")
    if args.dry_run:
        return 0

    # ⚠ Always restore the operator's config, including on Ctrl-C or a crash.
    backup = path + ".sweep-backup"
    shutil.copy2(path, backup)
    log(f"backed up {os.path.basename(path)} -> {os.path.basename(backup)}")

    results = []
    best = float(args.baseline_s)
    best_epoch = f"{pt_label(base)} (baseline)"

    if args.skip_first and plan:
        prior = [float(x) for x in args.prior_capture_s.split(",") if x.strip()]
        med = statistics.median(prior) if prior else None
        skipped = plan.pop(0)
        results.append({
            "epoch": pt_label(skipped),
            "offset_min": 0.0,
            "reps": len(prior) + args.prior_censored,
            "capture_times_s": prior,
            "capture_s": med,
            "capture_min_s": min(prior) if prior else None,
            "capture_max_s": max(prior) if prior else None,
            "captured": bool(prior),
            "source": "prior measurement, not re-run",
            # ⚠ Carried so the write-up cannot quietly treat this median as
            # like-for-like with the freshly measured epochs.
            "censored_reps": args.prior_censored,
            "median_biased_low": args.prior_censored > 0,
        })
        if med is not None:
            best = med
            best_epoch = f"{pt_label(skipped)} (prior)"
            log(f"epoch 0 skipped: seeded from {len(prior)} prior run(s), median {med:.0f}s (⚠ {args.prior_censored} censored — biased LOW)")
    try:
        for i, epoch in enumerate(plan, 1):
            log(f"=== {i}/{len(plan)}  {args.sweep} {pt_label(epoch)} ===")
            # Budget for THIS epoch: never spend longer than the winner.
            budget = min(best * args.abort_factor, args.timeout_min * 60.0)
            if args.sweep == "epoch":
                write_epoch(epoch)
            else:
                write_scalar(path, needle, epoch)

            # ⚠ EACH MODE GETS ITS OWN FRESH LAUNCH, at the same epoch.
            #
            # Not tidiness — sharing one stack across the three modes measures
            # something the corpus never does, in three separate ways:
            #   1. The collection does `make stop` + `make launch-quiet` before
            #      EVERY run, so a shared stack is not the configuration under
            #      test.
            #   2. `configure_inertial` ENABLES the star tracker, which boots
            #      disabled. SUNSAFE and BDOT would then be measured with ST on
            #      — a state no collection run ever flies.
            #   3. The INERTIAL capture wait burns ~5 min of SIM time, so by the
            #      time SUNSAFE started it was no longer at the epoch being
            #      tested. That defeats the entire question.
            reps = []
            for k in range(1, args.reps + 1):
                cap = run_mode(epoch, "INERTIAL", budget, args)
                reps.append(cap)
                got = cap.get("capture_s")
                log(f"  rep {k}/{args.reps}: "
                    + (f"{got:.0f}s" if got is not None else
                       f"TIMEOUT >{(cap.get('capture_gt_s') or budget):.0f}s"
                       + (" (captured late, during the hold)"
                          if cap.get("captured_late_in_hold") else ""))
                    + (f"  epoch_recorded={cap.get('recorded_epoch')}" if k == 1 else ""))

            times = [c["capture_s"] for c in reps if c.get("capture_s") is not None]
            # ⚠ Ranked on the MEDIAN, not the minimum: with a 2.2x spread at a
            # fixed epoch, ranking on best-of-N crowns whichever epoch drew the
            # luckiest sample.
            med = statistics.median(times) if times else None
            captured = len(times) * 2 >= args.reps        # majority captured
            first = reps[0]
            row = {
                "epoch": pt_label(epoch),
                "offset_min": pt_offset(epoch, base),
                "reps": args.reps,
                "capture_times_s": times,
                "capture_s": med,
                "capture_min_s": min(times) if times else None,
                "capture_max_s": max(times) if times else None,
                "captured": captured,
                "recorded_epoch": first.get("recorded_epoch"),
                "recorded_position": first.get("recorded_position"),
                "setpoint": pt_label(epoch),
                "eclipse_fraction": first.get("eclipse_fraction"),
                "frames": first.get("frames"),
                "csv": first.get("csv"),
                "error": first.get("error"),
            }

            # ⚠ AC6 gate: if the run did not actually START at the configured
            # epoch, the whole row is meaningless. Say so loudly rather than
            # ranking it.
            # ⚠ PHASE GATE. Two sweeps have already been voided by a config
            # write that silently did nothing — the wrong file, then the wrong
            # knob — and in both cases the results table looked entirely
            # plausible. If this point started where an earlier one did, the
            # knob is not connected to the sim.
            pos = row.get("recorded_position")
            if args.sweep != "epoch" and pos:
                for prev in results:
                    q = prev.get("recorded_position")
                    if not q:
                        continue
                    sep = math.dist(pos, q)
                    if sep < args.min_separation_km:
                        row["captured"] = False
                        row["phase_not_applied"] = True
                        log(f"  ⚠ PHASE NOT APPLIED: started {sep:.0f} km from setpoint {prev.get('setpoint')} — row void")
                        break

            rec = row["recorded_epoch"]
            if args.sweep == "epoch" and rec and rec[:13] != pt_label(epoch)[:13]:
                row["captured"] = False
                row["epoch_not_applied"] = True
                log(f"  ⚠ EPOCH NOT APPLIED: configured {pt_label(epoch)[:19]}, recorded {rec[:19]} — row void")
            elif captured and med is not None and med < best:
                log(f"  ⭐ NEW BEST median {med:.0f}s over {len(times)}/{args.reps} reps {times} (was {'%.0fs' % best if best < float('inf') else 'unbounded'})")
                best = med
                best_epoch = pt_label(epoch)
            elif not captured:
                log(f"  disqualified: only {len(times)}/{args.reps} reps captured within {budget/60:.1f} min")

            # AC7: an epoch tuned for INERTIAL must not break the modes that
            # carry the other 3/4 of the corpus — and SUNSAFE is also what damps
            # the vehicle before an INERTIAL hold.
            # ⚠ Skipped for a disqualified epoch: 2 x (launch + hold) of stack
            # time answering a question about an epoch we will not use.
            other = {}
            if not row["captured"]:
                other = {"skipped": "INERTIAL capture aborted; epoch disqualified"}
                log("  SUNSAFE/BDOT: skipped (epoch disqualified)")
            else:
                for mode in ("SUNSAFE", "BDOT"):
                    r = run_mode(epoch, mode, None, args)
                    other[mode] = r.get("health") or {"error": r.get("error")}
                    log(f"  {mode}: {other[mode]}")
            row["other_modes"] = other
            results.append(row)


    finally:
        shutil.copy2(backup, path)
        os.remove(backup)
        log(f"restored {os.path.basename(path)} to {pt_label(base)}")

    ok = [r for r in results if r.get("captured")]
    print("\n=== RESULT ===")
    print(f"{'offset':>8} {'epoch':<21} {'median':>8} {'min':>7} {'max':>7} {'reps':>6} {'eclipse':>8}")
    for r in results:
        if r.get("source"):
            med = f"{r['capture_s']:.0f}s" if r.get("capture_s") else "-"
            print(f"{r.get('offset_min', 0):>8} {r['epoch'][:19]:<21} {med:>8} "
                  f"{r['capture_min_s']:>6.0f}s {r['capture_max_s']:>6.0f}s "
                  f"{len(r['capture_times_s'])}/{r['reps']:<4} "
                  f"  ⚠ prior, {r['censored_reps']} censored (median low)")
            continue
        if r.get("epoch_not_applied") or r.get("phase_not_applied"):
            why = "epoch" if r.get("epoch_not_applied") else "phase"
            print(f"{r.get('offset_min', 0):>8} {str(r.get('setpoint'))[:19]:<21} {'VOID — ' + why + ' not applied':>40}")
            continue
        med = f"{r['capture_s']:.0f}s" if r.get("capture_s") else "DISQ"
        lo = f"{r['capture_min_s']:.0f}s" if r.get("capture_min_s") else "-"
        hi = f"{r['capture_max_s']:.0f}s" if r.get("capture_max_s") else "-"
        n = f"{len(r.get('capture_times_s') or [])}/{r.get('reps')}"
        print(f"{r.get('offset_min', 0):>8} {r['epoch'][:19]:<21} {med:>8} {lo:>7} {hi:>7} {n:>6} {str(r.get('eclipse_fraction')):>8}")
    if ok:
        win = min(ok, key=lambda r: r["capture_s"])
        print(f"\nfastest capture: {win['capture_s']:.0f}s at {win['epoch']} (baseline was {args.baseline_s:.0f}s)")
        print(f"⚠ epochs marked TIMEOUT were ABORTED at the running best, not run to completion — they are 'slower than {best:.0f}s', not 'never captured'.")
    else:
        print("\n⚠ NO epoch achieved capture — that is a result, not a failure. Record it.")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"sweep": args.sweep, "baseline": pt_label(base),
                       "results": results}, fh, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
