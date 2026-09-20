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


def measurement_window(csv_path, attacks, pre_seconds, post_seconds, hz, n_frames):
    """Frame range of the RECORDED SAMPLE, anchored on the attack window.

    ⚠ The CSV is not the sample, and neither is the scenario block. OnAIR starts
    recording at stack launch, so a session file contains FSW boot; and for
    INERTIAL the scenario block itself opens BEFORE the capture wait runs inside
    it, so it also contains 1-12 min of deliberately uncontrolled flight while
    the vehicle tumbles toward a star-tracker window. Neither is part of the run's
    data.

    What the run declares as its sample is `pre_seconds` of nominal baseline, the
    attack, and `post_seconds` after it. Anchoring on the attack window — the one
    timestamp recorded exactly — gives precisely that span.

    Measured 2026-09-12, qValid by decile for three rejected runs:
        [8, 0, 28, 61, 100, 100, 100, 100, 100, 100]
    The first 3-4 deciles are acquisition. Scoring capture over the whole file
    rated those runs 67-70% and rejected them, while every frame of their
    declared sample — including all attack frames — was 100% controlled.

    ⚠ This narrows WHAT is measured, not the 90% bar it is measured against.
    """
    real = [a for a in (attacks or []) if "[prereq]" not in (a.get("id") or "")]
    if not real or not hz:
        return None
    base = os.path.basename(csv_path)
    try:
        ts = base.split("csv_out_")[1].rsplit("_pid", 1)[0]
        t0 = datetime.datetime.strptime(ts, "%Y-%m-%dT%H-%M-%S-%f")
    except Exception:
        return None
    starts = []
    for a in real:
        v = a.get("start_utc")
        if v:
            try:
                starts.append(datetime.datetime.fromisoformat(v.replace("Z", "")))
            except ValueError:
                pass
    if not starts:
        return None
    i_att = int((min(starts) - t0).total_seconds() * hz)
    lo = max(i_att - int((pre_seconds or 240) * hz), 0)
    return (lo, n_frames - 1)


def scan_csv(csv_path, check_capture=False):
    """ONE streaming pass: row count, MET span, last mode switch, capture fraction.

    ⚠ Streams. An earlier version did `rows = [r for r in DictReader]`, which
    materialises a whole session CSV as dicts — these files run 50-700 MB and a
    470-column dict row is far larger than its text, so a single call could take
    tens of GB and a corpus walk could take the machine down. The 2026-09-10
    collection driver was killed for low memory while this tool was in the loop.
    Nothing here needs random access: counts and extents are accumulators, and
    the alert-eligible fraction is index arithmetic once the extents are known.
    """
    n = 0
    met_lo = met_hi = None
    switches = []          # every ADCS mode-change index, in order
    prev_mode = None
    qv_flags = bytearray()      # 0 = sentinel, 1 = qValid false, 2 = qValid true
    try:
        with open(csv_path, newline="") as fh:
            rd = csv.DictReader(fh)
            fields = rd.fieldnames or []
            has_q = "ADCS_GNC.qValid" in fields
            has_mode = "ADCS_GNC.Mode" in fields
            has_met = "CFE_TIME.SecondsMET" in fields
            for r in rd:
                i = n
                n += 1
                if has_met:
                    v = r.get("CFE_TIME.SecondsMET", SENTINEL)
                    if v not in (SENTINEL, ""):
                        try:
                            f = float(v)
                            met_lo = f if met_lo is None or f < met_lo else met_lo
                            met_hi = f if met_hi is None or f > met_hi else met_hi
                        except ValueError:
                            pass
                if has_mode:
                    v = r.get("ADCS_GNC.Mode", SENTINEL)
                    if v != SENTINEL:
                        if prev_mode is not None and v != prev_mode:
                            switches.append(i)
                        prev_mode = v
                if check_capture and has_q:
                    v = r.get("ADCS_GNC.qValid", SENTINEL)
                    # One byte per frame (~40 KB for a full session) so the
                    # measurement window can be applied once hz is derived —
                    # hz needs the FULL-file row count, so it cannot be scoped
                    # during the pass.
                    qv_flags.append(0 if v == SENTINEL else (2 if v == "1" else 1))
                elif check_capture:
                    qv_flags.append(0)
    except FileNotFoundError:
        return None
    # AINOS3-92: derive the rate; MET is non-monotonic so use the max-min span.
    hz = None
    if met_lo is not None and met_hi is not None:
        span = met_hi - met_lo
        if span >= 60.0 and n > 1:
            cand = n / span
            hz = cand if 1.0 <= cand <= 20.0 else None
    return {
        "n": n,
        "hz": hz,
        "switches": switches,
        "mode_switch_count": len(switches),
        "qv_flags": qv_flags,
    }


def controlled_fraction(scan, window=None):
    """qValid rate over the measurement window (or the whole file if unknown)."""
    f = scan.get("qv_flags") or b""
    if not f:
        return None
    lo, hi = (0, len(f) - 1) if not window else (max(window[0], 0), min(window[1], len(f) - 1))
    if hi < lo:
        return None
    seg = f[lo:hi + 1]
    live = sum(1 for x in seg if x)
    if not live:
        return None
    return sum(1 for x in seg if x == 2) / live


def alert_eligible_fraction(scan, csv_path, attacks):
    """Fraction of labelled attack frames outside the detector's blind window.

    ⚠ `AC1`'s metric, against the 84.4 % pilot figure. "Eligible" means more than
    MODE_SWITCH_WARMUP_FRAMES past the last ADCS mode change — inside that window
    the detector cannot alert, so an attack frame there is unusable no matter how
    good the attack. `single_mode_hold_<MODE>` commands the mode once at the start
    of the pre-window precisely so the attack lands clear of it.

    Pure index arithmetic over the extents from `scan_csv` — the rows are not
    revisited.
    """
    if not attacks or not scan or not scan["hz"]:
        return None
    base = os.path.basename(csv_path)
    try:
        ts = base.split("csv_out_")[1].rsplit("_pid", 1)[0]
        t0 = datetime.datetime.strptime(ts, "%Y-%m-%dT%H-%M-%S-%f")
    except Exception:
        return None
    n, hz, switches = scan["n"], scan["hz"], scan["switches"]

    def preceding_switch(idx):
        """Index of the most recent mode change at or before `idx` (0 if none).

        ⚠ Must be per-frame, not "the last switch in the file". An attack that
        FLAPS the mode as part of its own footprint — EX-0012.08 drives
        SUNSAFE<->PASSIVE from frame 1345 — puts switches after some of its own
        attack frames, and using the file's final switch marks those earlier
        frames ineligible when the detector was in fact free to alert on them.
        """
        lo, hi, best = 0, len(switches) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if switches[mid] <= idx:
                best = switches[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return best if best is not None else 0

    tot = elig = 0
    for a in attacks:
        # AC6 / AINOS3-122 AC4: a chained prerequisite is logged "<id> [prereq]"
        # and is setup, not the labelled attack. It must not dilute this.
        if "[prereq]" in (a.get("id") or ""):
            continue
        st, en = a.get("start_utc"), a.get("corruption_end_utc") or a.get("end_utc")
        if not st or not en:
            continue
        try:
            s_dt = datetime.datetime.fromisoformat(st.replace("Z", ""))
            e_dt = datetime.datetime.fromisoformat(en.replace("Z", ""))
        except ValueError:
            continue
        i0 = max(int((s_dt - t0).total_seconds() * hz), 0)
        i1 = min(int((e_dt - t0).total_seconds() * hz), n - 1)
        if i1 < i0:
            continue
        tot += i1 - i0 + 1
        for i in range(i0, i1 + 1):
            if i - preceding_switch(i) > MODE_SWITCH_WARMUP_FRAMES:
                elig += 1
    return (elig / tot) if tot else None


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
    ap.add_argument("--csv-dir", default=CSV_DIR,
                    help="where the run CSVs live (default data/onair/csv). Point "
                         "at a derived corpus such as csv_blended/ to manifest that "
                         "variant; the scenario manifests are shared, so both "
                         "variants label identically.")
    args = ap.parse_args()
    csv_dir = args.csv_dir

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
        csv_path = os.path.join(csv_dir, os.path.basename(csv_name)) if csv_name else None
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
        scenarios = []
        mf = r.get("manifest")
        if mf:
            mpath = os.path.join(ROOT, "data", "onair", "scenarios", os.path.basename(mf))
            if os.path.exists(mpath):
                with open(mpath) as fh:
                    _mj = json.load(fh)
                attacks = _mj.get("attacks", [])
                scenarios = _mj.get("scenarios", [])
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

        scan = scan_csv(csv_path, check_capture=(mode == "INERTIAL")) if csv_path else None
        n = scan["n"] if scan else None
        hz = scan["hz"] if scan else None
        win = measurement_window(csv_path, attacks, r.get("pre_seconds"),
                                 r.get("post_seconds"), hz, scan["n"]) \
            if (scan and hz) else None
        frac = controlled_fraction(scan, win) if scan else None
        eligible = alert_eligible_fraction(scan, csv_path, attacks) if scan else None
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
            "mode_switch_count": scan["mode_switch_count"] if scan else None,
            "alert_eligible_attack_fraction": eligible,
            "problems": problems,
        }
        if problems:
            rejected.append(rec)
        else:
            runs.append(rec)
            total_frames += n or 0

    # ⚠ A corpus must not contain the same (technique, mode, instance) twice —
    # re-chunking after a partial run, or re-running a chunk without clearing its
    # results, silently double-weights that cell in training. Checked, not hoped.
    seen = {}
    duplicates = []
    for r in runs:
        k = (r["technique"], r["mode"], r["instance"])
        if k in seen:
            duplicates.append(k)
        seen[k] = True

    # A rejected run whose key was later collected successfully is SUPERSEDED,
    # not an outstanding gap — label it so a reader is not left to work that out.
    accepted_keys = set(seen)
    for r in rejected:
        r["superseded_by_successful_run"] = (
            (r["technique"], r["mode"], r["instance"]) in accepted_keys)

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
            "runs_rejected_superseded": sum(
                1 for r in rejected if r["superseded_by_successful_run"]),
            "duplicate_run_keys": [list(k) for k in duplicates],
            "frames_accepted": total_frames,
            "techniques": len({r["technique"] for r in runs if r["technique"]}),
            "modes": sorted({r["mode"] for r in runs if r["mode"]}),
            "instances": sorted({r["instance"] for r in runs if r["instance"] is not None}),
        },
        "runs": runs,
        "rejected_runs": rejected,
    }
    # ⚠ Aggregates must be computed BEFORE the write. The AC1 mean and the
    # incomplete-cell list used to be added to `out` inside the reporting block
    # below, which runs after json.dump — so they printed to the terminal and
    # were silently absent from the artifact anyone reads later.
    elig_all = [r["alert_eligible_attack_fraction"] for r in runs
                if r.get("alert_eligible_attack_fraction") is not None]
    if elig_all:
        out["counts"]["alert_eligible_attack_fraction_mean"] = sum(elig_all) / len(elig_all)
        out["counts"]["alert_eligible_attack_fraction_min"] = min(elig_all)
    incomplete = []
    if runs:
        techs_all = sorted({r["technique"] for r in runs if r["technique"]})
        for m_ in sorted({r["mode"] for r in runs if r["mode"]}):
            for i_ in sorted({r["instance"] for r in runs if r["mode"] == m_}):
                have_ = {(r["technique"], r["instance"]) for r in runs if r["mode"] == m_}
                gap_ = [t for t in techs_all if (t, i_) not in have_]
                if gap_:
                    incomplete.append({"mode": m_, "instance": i_, "techniques": gap_})
    out["incomplete_cells"] = incomplete

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)

    c = out["counts"]
    print(f"corpus     : {out['corpus_name']}")
    print(f"schema     : {schema.get('label')} "
          f"({schema['column_count']} cols, {schema['recorded_schema_sha256'][:12]}…)")
    print(f"accepted   : {c['runs_accepted']} runs, {c['frames_accepted']} frames, "
          f"{c['techniques']} techniques, modes {c['modes']}, instances {c['instances']}")
    if elig_all:
        print(f"AC1 alert-eligible attack frames: "
              f"{out['counts']['alert_eligible_attack_fraction_mean']:.1%} mean, "
              f"{out['counts']['alert_eligible_attack_fraction_min']:.1%} min "
              f"(n={len(elig_all)} runs; pilot reference 84.4%)")
    if duplicates:
        print(f"\n⚠⚠ DUPLICATE runs — the same cell is collected more than once, "
              f"which double-weights it in training. FIX BEFORE TRAINING:")
        for k in duplicates:
            print(f"    {k[0]}/{k[1]}/inst{k[2]}")
    if rejected:
        n_sup = sum(1 for r in rejected if r["superseded_by_successful_run"])
        print(f"⚠ REJECTED : {len(rejected)} run(s)"
              + (f" — {n_sup} superseded by a later successful run (not a gap)"
                 if n_sup else ""))
        for r in rejected:
            tag = " [superseded]" if r["superseded_by_successful_run"] else ""
            print(f"    {r['technique']}/{r['mode']}/inst{r['instance']}{tag}: "
                  f"{'; '.join(r['problems'])}")

    # What the corpus still OWES, as a first-class output rather than arithmetic
    # left to the reader.
    if incomplete:
        print(f"\nincomplete instances (partial collection in progress):")
        for g in incomplete:
            print(f"    {g['mode']} inst{g['instance']}: missing {len(g['techniques'])} technique(s)")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
