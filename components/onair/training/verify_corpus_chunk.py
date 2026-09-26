#!/usr/bin/env python3
"""Per-run acceptance checks for an AINOS3-100 collection, as chunks land.

⚠ Runs the checks that have actually caught defects in this project, not a
generic smoke test. Each column below exists because something silently went
wrong once:

  cols        a schema drift means the run cannot pool with the corpus
              (recorded_schema_sha256 moved 470 -> 471 -> 472 this sprint)
  recvUTC     blank OnAIR.FrameRecvUTC sends labelling back to
              file_start + row_idx/rate — median 57 s of drift, enough to
              label attack frames nominal (AINOS3-126)
  atk frames  an attack that "ran" (exit 0) but moved nothing produces
              nominal frames labelled as an attack — the worst corpus defect,
              and invisible from the run's own output (AINOS3-100 AC8)
  prereq      a chained prereq that exits instantly leaves the main attack
              without its precondition; EX-0008.01/.02 failed this way across
              the whole 2026-09-10 collection
  hold        a run whose mode did not stick is not the mode it claims.
              ⚠ Scored PRE-ATTACK only — some techniques change the mode as
              their entire footprint (EX-0012.08), and scoring across the
              attack marks a successful one as broken.
  equiv       deinterleave_csv(raw) == native blend (AINOS3-126 AC2)

Usage:
    python3 verify_corpus_chunk.py --base data/onair/corpus/rebuild_2026-09-21
    python3 verify_corpus_chunk.py --base <dir> --chunk chunk_05_ex_0008_01
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
from verify_blend_equivalence import compare  # noqa: E402

MODE_VALUE = {"PASSIVE": "0", "BDOT": "1", "SUNSAFE": "2", "INERTIAL": "3"}
_TS = re.compile(r"csv_out_(\d{4}-\d{2}-\d{2}T[\d-]+)_pid(\d+)\.csv$")


def _stamp(path):
    m = _TS.search(os.path.basename(path))
    return (dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H-%M-%S-%f"), m.group(2)) if m else (None, None)


def pair_blended(raw_name, blended_dir):
    """⚠ pid alone does NOT identify a run — OnAIR is pid 11 in its container
    for most of the corpus. Pair on (pid, nearest start timestamp)."""
    key, pid = _stamp(raw_name)
    if key is None:
        return None
    cands = glob.glob(os.path.join(blended_dir, f"csv_out_*_pid{pid}.csv"))
    scored = [(abs((_stamp(c)[0] - key).total_seconds()), c) for c in cands if _stamp(c)[0]]
    scored.sort()
    return scored[0][1] if scored and scored[0][0] <= 2.0 else None


def check_run(rec, raw_dir, blended_dir, manifest_dir, max_rows):
    out = {"technique": rec["_technique"], "mode": rec["_mode"],
           "exit": rec.get("exit_code"), "problems": []}
    raw = os.path.join(raw_dir, rec["csv"])
    bl = pair_blended(rec["csv"], blended_dir)
    if not os.path.exists(raw):
        out["problems"].append("raw csv missing")
        return out
    if not bl:
        out["problems"].append("no blended pair")
        return out

    with open(bl) as fh:
        rd = csv.DictReader(fh)
        hdr = rd.fieldnames or []
        rows = list(rd)
    out["cols"] = len(hdr)
    out["frames"] = len(rows)
    if not rows:
        out["problems"].append("empty")
        return out

    recv = [r.get("OnAIR.FrameRecvUTC") or "" for r in rows]
    out["recv_pct"] = round(sum(1 for x in recv if x) / len(rows) * 100)
    out["sim_pct"] = round(sum(1 for r in rows if r.get("OnAIR.SimTimeUTC")) / len(rows) * 100)
    if out["recv_pct"] < 100:
        out["problems"].append(f"FrameRecvUTC only {out['recv_pct']}%")

    t = [dt.datetime.fromisoformat(x) for x in recv if x]
    mf = json.load(open(os.path.join(manifest_dir, rec["manifest"])))
    spans, main_start = {}, None
    for a in mf.get("attacks", []):
        s = dt.datetime.fromisoformat(a["start_utc"]).replace(tzinfo=dt.timezone.utc)
        e = dt.datetime.fromisoformat(a["end_utc"]).replace(tzinfo=dt.timezone.utc)
        idx = [i for i, x in enumerate(t) if s <= x <= e]
        spans[a["id"]] = (idx[0], idx[-1]) if idx else None
        if a.get("exit_code") not in (0, None):
            out["problems"].append(f"{a['id']} exit={a.get('exit_code')}")
        if "[prereq]" not in a["id"]:
            main_start = s
    for aid, sp in spans.items():
        tag = "prereq" if "[prereq]" in aid else "attack"
        out[tag] = f"{sp[0]}..{sp[1]}" if sp else "NONE"
        if sp is None:
            out["problems"].append(f"no frames in {tag} window ({aid})")

    if main_start:
        # ⚠ Measure the hold over the PRE-ATTACK window only. Several techniques
        # change the ADCS mode as their whole point — EX-0012.08 at level 2 is
        # "switch to target mode, dwell, no restore" — so scoring the hold
        # across the attack window marks a SUCCESSFUL attack as a broken run.
        # Observed: EX-0012.08/INERTIAL flagged at 98 % because 82 PASSIVE
        # frames appeared after the attack, which is the attack working.
        pre = rec.get("pre_seconds") or 150
        samp = [r for r, tt in zip(rows, t)
                if main_start - dt.timedelta(seconds=pre) <= tt < main_start]
        want = MODE_VALUE[rec["_mode"]]
        held = sum(1 for r in samp if r.get("ADCS_GNC.Mode") == want) / max(1, len(samp))
        out["hold_pct"] = round(held * 100)
        if held < 0.99:
            out["problems"].append(f"mode held only {out['hold_pct']}%")
        if rec["_mode"] == "INERTIAL":
            # ⚠ Capture, unlike the mode hold, IS scored across the declared
            # sample: a run that loses control DURING the attack is exactly
            # what AINOS3-100 AC7's 90 % gate exists to reject. EX-0012.07 is
            # the known exception — its thruster burn breaks the hold by
            # physics (29 % qValid after the attack vs 84 % before), which is
            # that technique's signature, not a defect.
            full = [r for r, tt in zip(rows, t)
                    if tt >= main_start - dt.timedelta(seconds=pre)]
            qv = [r.get("ADCS_GNC.qValid") for r in full]
            ctrl = sum(1 for v in qv if v == "1") / max(1, len(qv))
            out["capture_pct"] = round(ctrl * 100)
            # AINOS3-100 AC7 gate. EX-0012.07 legitimately fails it: the
            # thruster burn breaks the hold by physics, which is that
            # technique's own signature.
            if ctrl < 0.90:
                out["problems"].append(f"capture {out['capture_pct']}% (<90% gate)")

    r = compare(raw, bl, max_rows=max_rows)
    out["equiv"] = "PASS" if r["ok"] else "FAIL"
    if not r["ok"]:
        out["problems"].append(f"blend equivalence FAILED ({r.get('diff_cells')} cells)")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True)
    p.add_argument("--chunk", default=None, help="substring filter")
    p.add_argument("--raw-dir", default="data/onair/csv")
    p.add_argument("--blended-dir", default="data/onair/csv_blended")
    p.add_argument("--manifest-dir", default="data/onair/scenarios")
    p.add_argument("--max-rows", type=int, default=5000)
    a = p.parse_args()

    base = a.base if os.path.isabs(a.base) else os.path.join(ROOT, a.base)
    # ⚠ Exclude *_remainder_results.json. `run_corpus_chunks` writes a resumed
    # chunk's missing runs there, merges them into the main file, and only
    # deletes the remainder the NEXT time that chunk is processed — so a
    # completed resume leaves it on disk. Globbing *_results.json then counts
    # those runs TWICE. Observed 2026-09-22: 77 runs reported for a 76-run
    # collection, with EX-0014.03/SUNSAFE listed twice.
    res = sorted(f for f in glob.glob(os.path.join(base, "results", "*_results.json"))
                 if not f.endswith("_remainder_results.json"))
    if a.chunk:
        res = [r for r in res if a.chunk in os.path.basename(r)]
    if not res:
        sys.exit(f"no results under {base}/results")

    hdr = (f"{'technique':<12}{'mode':<9}{'cols':>5}{'frames':>7}{'recv':>6}{'sim':>5}"
           f"{'prereq':>12}{'attack':>12}{'hold':>6}{'cap':>5}{'equiv':>7}")
    print(hdr); print("-" * len(hdr))
    bad, n = [], 0
    for rp in res:
        for rec in json.load(open(rp)):
            n += 1
            o = check_run(rec, os.path.join(ROOT, a.raw_dir),
                          os.path.join(ROOT, a.blended_dir),
                          os.path.join(ROOT, a.manifest_dir), a.max_rows)
            print(f"{o['technique']:<12}{o['mode']:<9}{o.get('cols','-'):>5}"
                  f"{o.get('frames','-'):>7}{str(o.get('recv_pct','-'))+'%':>6}"
                  f"{str(o.get('sim_pct','-'))+'%':>5}{o.get('prereq','-'):>12}"
                  f"{o.get('attack','-'):>12}{str(o.get('hold_pct','-'))+'%':>6}"
                  f"{str(o.get('capture_pct','-')):>5}{o.get('equiv','-'):>7}")
            if o["problems"]:
                bad.append(o)
                for pr in o["problems"]:
                    print(f"    ⚠ {pr}")
    print(f"\n{n - len(bad)}/{n} runs clean")
    if bad:
        print("⚠ runs with problems: " + ", ".join(
            f"{o['technique']}/{o['mode']}" for o in bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
