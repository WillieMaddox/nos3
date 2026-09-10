#!/usr/bin/env python3
"""Build the AINOS3-100 corpus manifest — the artifact whose absence made four
AINOS3-80 metrics permanently `[unverifiable]`.

WHY THIS EXISTS (AINOS3-100 AC2)
--------------------------------
A corpus is only as citable as its provenance. Four published AINOS3-80 metrics
could not be verified after the fact because nothing recorded WHICH runs, WHICH
schema, or WHICH build produced the data behind them. This manifest is the
record that makes a number traceable back to the frames it came from:

  * per run: technique (the frozen `label_set.json` id), ADCS mode, instance,
    scenario, attack window, CSV file, frame counts;
  * the RECORDED schema every run was collected against, pinned by
    `recorded_schema_sha256` — the fingerprint that actually moves when the
    prune moves (AINOS3-124), not the tlm-file hash;
  * the FSW build and container identity;
  * ⚠ a per-run SCHEMA CONSISTENCY verdict. A run whose sidecar disagrees with
    the frozen manifest is a REJECTED run, not a footnote — mixing schemas
    silently is precisely how a corpus becomes unusable.

⚠ INERTIAL runs additionally require a CAPTURE verdict (AINOS3-86): a run that
merely reports `ST.DeviceEnabled = 1` may have been in free drift the whole
time. `--check-capture` marks any INERTIAL run whose controlled fraction is
below the threshold as suspect.

USAGE
    python3 build_corpus_manifest.py --batch-results pilot_results.json \\
        --schema-manifest components/onair/schema_manifest.json \\
        --out data/onair/corpus/<name>/corpus_manifest.json
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
CSV_DIR = os.path.join(ROOT, "data", "onair", "csv")
SENTINEL = "[0]"


def sidecar_for(csv_path):
    p = csv_path[:-4] + ".meta.json" if csv_path.endswith(".csv") else csv_path + ".meta.json"
    if os.path.exists(p):
        with open(p) as fh:
            return json.load(fh)
    return None


def fsw_build_id():
    """Best-effort FSW build identity: the cFE exe's sha256, short."""
    exe = os.path.join(ROOT, "fsw", "build", "exe", "cpu1", "core-cpu1")
    if not os.path.exists(exe):
        return None
    h = hashlib.sha256()
    with open(exe, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def git_rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


# The deployed IF suppresses alerts for this many frames after every ADCS mode
# change (ModeSwitchWarmupFrames). Attack frames inside it can never raise an
# alert, which is what made 83 % of the previous corpus unusable (AINOS3-77).
MODE_SWITCH_WARMUP_FRAMES = 250


def frame_stats(csv_path, check_capture=False, attacks=(), hz=None):
    """Row count, controlled fraction (INERTIAL), and the AC1 alert-eligible fraction.

    ⚠ `AC1` asks for the **alert-eligible attack frame fraction** against the
    84.4 % pilot figure. "Eligible" means the frame is more than
    MODE_SWITCH_WARMUP_FRAMES past the last ADCS mode change — inside that window
    the detector cannot alert, so an attack frame there is unusable regardless of
    how good the attack was. `single_mode_hold_<MODE>` commands the mode once at
    the start of the pre-window precisely so the attack lands outside it.

    Frames are located by index, not wall clock: the CSV carries no clock, so the
    attack window is mapped through the DERIVED sample rate (AINOS3-92).
    """
    rows = []
    try:
        with open(csv_path, newline="") as fh:
            rd = csv.DictReader(fh)
            fields = rd.fieldnames or []
            has_q = "ADCS_GNC.qValid" in fields
            has_mode = "ADCS_GNC.Mode" in fields
            for r in rd:
                rows.append(r)
    except FileNotFoundError:
        return None, None, None
    n = len(rows)
    if n == 0:
        return 0, None, None

    qv_live = qv_true = 0
    if check_capture and has_q:
        for r in rows:
            v = r.get("ADCS_GNC.qValid", SENTINEL)
            if v != SENTINEL:
                qv_live += 1
                qv_true += int(v == "1")
    frac = (qv_true / qv_live) if qv_live else None

    # last ADCS mode change, by index
    last_switch = 0
    if has_mode:
        prev = None
        for i, r in enumerate(rows):
            v = r.get("ADCS_GNC.Mode", SENTINEL)
            if v == SENTINEL:
                continue
            if prev is not None and v != prev:
                last_switch = i
            prev = v

    eligible = None
    if attacks and hz:
        # CSV start time from the filename timestamp; attack times from the manifest.
        base = os.path.basename(csv_path)
        try:
            ts = base.split("csv_out_")[1].rsplit("_pid", 1)[0]
            t0 = datetime.datetime.strptime(ts, "%Y-%m-%dT%H-%M-%S-%f")
        except Exception:
            return n, frac, None
        tot = elig = 0
        for a in attacks:
            # ⚠ AC6 / AINOS3-122 AC4: a chained prerequisite is logged as
            # "<id> [prereq]" and is deliberately NOT a technique of its own.
            # Its frames are setup, not the labelled attack, so they must not
            # dilute the AC1 alert-eligible fraction.
            if "[prereq]" in (a.get("id") or ""):
                continue
            st = a.get("start_utc")
            en = a.get("corruption_end_utc") or a.get("end_utc")
            if not st or not en:
                continue
            try:
                s_dt = datetime.datetime.fromisoformat(st.replace("Z", ""))
                e_dt = datetime.datetime.fromisoformat(en.replace("Z", ""))
            except ValueError:
                continue
            i0 = int((s_dt - t0).total_seconds() * hz)
            i1 = int((e_dt - t0).total_seconds() * hz)
            i0, i1 = max(i0, 0), min(i1, n - 1)
            if i1 < i0:
                continue
            tot += i1 - i0 + 1
            elig += sum(1 for i in range(i0, i1 + 1)
                        if i - last_switch > MODE_SWITCH_WARMUP_FRAMES)
        eligible = (elig / tot) if tot else None
    return n, frac, eligible


def derive_hz(csv_path):
    """Sample rate from CFE_TIME.SecondsMET (AINOS3-92: derive, never assume).

    MET is ~0.25 Hz-granular and NON-monotonic (OnAIR double buffer), so use the
    max-min span across the file, not consecutive diffs.
    """
    mets, n = [], 0
    try:
        with open(csv_path, newline="") as fh:
            for r in csv.DictReader(fh):
                n += 1
                v = r.get("CFE_TIME.SecondsMET", SENTINEL)
                if v not in (SENTINEL, ""):
                    try:
                        mets.append(float(v))
                    except ValueError:
                        pass
    except FileNotFoundError:
        return None
    if len(mets) < 2:
        return None
    span = max(mets) - min(mets)
    if span < 60.0:
        return None
    hz = n / span
    return hz if 1.0 <= hz <= 20.0 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch-results", required=True,
                    help="the run_attack_batch.py output JSON")
    ap.add_argument("--schema-manifest",
                    default=os.path.join(ROOT, "components", "onair", "schema_manifest.json"))
    ap.add_argument("--label-set",
                    default=os.path.join(ROOT, "data", "onair", "models", "label_set.json"))
    ap.add_argument("--name", default=None, help="corpus name (default: derived from date)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--capture-min", type=float, default=0.90,
                    help="minimum controlled fraction for an INERTIAL run to count")
    args = ap.parse_args()

    with open(args.batch_results) as fh:
        results = json.load(fh)
    if isinstance(results, dict):
        results = results.get("runs", [])
    with open(args.schema_manifest) as fh:
        schema = json.load(fh)
    with open(args.label_set) as fh:
        labels = json.load(fh)
    valid_ids = {c["id"] for c in labels["classes"]
                 if c["status"] in ("confirmed", "deferred")}

    runs, rejected = [], []
    total_frames = 0
    for r in results:
        csv_name = r.get("csv") or r.get("csv_file")
        csv_path = os.path.join(CSV_DIR, os.path.basename(csv_name)) if csv_name else None
        side = sidecar_for(csv_path) if csv_path else None
        mode = r.get("_mode") or r.get("mode")
        tech = r.get("_technique") or r.get("technique")

        problems = []
        if tech and tech not in valid_ids:
            problems.append(f"technique {tech!r} is not a confirmed/deferred label_set id")
        if side is None:
            problems.append("no .meta.json sidecar — schema unverifiable")
        else:
            got = side.get("recorded_schema_sha256")
            if got is None:
                problems.append("sidecar predates recorded_schema_sha256 (csv_output < 1.2)")
            elif got != schema["recorded_schema_sha256"]:
                problems.append(f"schema mismatch: {got[:12]} != frozen "
                                f"{schema['recorded_schema_sha256'][:12]}")

        # ⚠ A run whose ATTACK subprocess failed still produces a full-length
        # CSV — the surrounding scenario blocks run regardless. Caught by the
        # 2026-09-10 pilot: a bad --attack-level made the injection exit with
        # "invalid choice" while the run looked complete, which at batch scale
        # yields NOMINAL frames labelled as an attack. Read the run manifest and
        # reject on the attack's own exit code.
        attacks = []
        mf = r.get("manifest")
        if mf:
            mpath = os.path.join(ROOT, "data", "onair", "scenarios", os.path.basename(mf))
            if os.path.exists(mpath):
                with open(mpath) as fh:
                    attacks = json.load(fh).get("attacks", [])
            else:
                problems.append(f"run manifest {os.path.basename(mf)} not found")
        else:
            problems.append("no run manifest recorded — attack outcome unverifiable")
        if attacks:
            bad = [a for a in attacks if a.get("exit_code") not in (0, None)]
            if bad:
                problems.append("attack subprocess FAILED (exit "
                                + ",".join(str(a.get("exit_code")) for a in bad)
                                + ") — no attack in this CSV")
        elif mf:
            problems.append("run manifest records NO attack window")
        if attacks and not [a for a in attacks if "[prereq]" not in (a.get("id") or "")]:
            problems.append("run manifest records ONLY prereq windows — "
                            "the labelled technique never fired")
        if r.get("exit_code") not in (0, None):
            problems.append(f"run_attack exited {r.get('exit_code')}")

        hz = derive_hz(csv_path) if csv_path else None
        n, frac, eligible = frame_stats(
            csv_path, check_capture=(mode == "INERTIAL"), attacks=attacks, hz=hz) \
            if csv_path else (None, None, None)
        if mode == "INERTIAL" and frac is not None and frac < args.capture_min:
            problems.append(f"INERTIAL capture only {frac:.1%} (< {args.capture_min:.0%}) "
                            f"— free drift, not a controlled hold (AINOS3-86)")

        rec = {
            "technique": tech,
            "mode": mode,
            "instance": r.get("_rep") or r.get("instance"),
            "attack_key": r.get("key"),
            "scenario": r.get("during"),
            "csv": os.path.basename(csv_name) if csv_name else None,
            "manifest": r.get("manifest"),
            "frames": n,
            "pre_seconds": r.get("pre_seconds"),
            "post_seconds": r.get("post_seconds"),
            "exit_code": r.get("exit_code"),
            "prereq_windows": [a.get("id") for a in attacks
                               if "[prereq]" in (a.get("id") or "")],
            "attack_windows": [{"id": a.get("id"), "start_utc": a.get("start_utc"),
                                "end_utc": a.get("end_utc"),
                                "exit_code": a.get("exit_code")} for a in attacks],
            "controlled_fraction": frac,
            "sample_hz": round(hz, 3) if hz else None,
            "alert_eligible_attack_fraction": eligible,
            "problems": problems,
        }
        if problems:
            rejected.append(rec)
        else:
            runs.append(rec)
            total_frames += n or 0

    out = {
        "corpus_name": args.name or f"corpus_{datetime.date.today().isoformat()}",
        "built_at": datetime.datetime.now(datetime.timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_ticket": "AINOS3-100",
        "schema": {
            "label": schema.get("label"),
            "recorded_schema_sha256": schema["recorded_schema_sha256"],
            "column_count": schema["column_count"],
        },
        "label_set": {
            "frozen_at": labels.get("frozen_at"),
            "source_ticket": labels.get("source_ticket"),
        },
        "fsw_build_sha256_16": fsw_build_id(),
        "git_rev": git_rev(),
        "counts": {
            "runs_accepted": len(runs),
            "runs_rejected": len(rejected),
            "frames_accepted": total_frames,
            "techniques": len({r["technique"] for r in runs if r["technique"]}),
            "modes": sorted({r["mode"] for r in runs if r["mode"]}),
            "instances": sorted({r["instance"] for r in runs if r["instance"] is not None}),
        },
        "runs": runs,
        "rejected_runs": rejected,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)

    c = out["counts"]
    print(f"corpus     : {out['corpus_name']}")
    print(f"schema     : {schema.get('label')} "
          f"({schema['column_count']} cols, {schema['recorded_schema_sha256'][:12]}…)")
    print(f"accepted   : {c['runs_accepted']} runs, {c['frames_accepted']} frames, "
          f"{c['techniques']} techniques, modes {c['modes']}, instances {c['instances']}")
    elig = [r["alert_eligible_attack_fraction"] for r in runs
            if r.get("alert_eligible_attack_fraction") is not None]
    if elig:
        mean_e = sum(elig) / len(elig)
        out["counts"]["alert_eligible_attack_fraction_mean"] = mean_e
        print(f"AC1 alert-eligible attack frames: {mean_e:.1%} "
              f"(n={len(elig)} runs; pilot reference 84.4%)")
    if rejected:
        print(f"⚠ REJECTED : {len(rejected)} run(s)")
        for r in rejected:
            print(f"    {r['technique']}/{r['mode']}/inst{r['instance']}: {'; '.join(r['problems'])}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
