#!/usr/bin/env python3
"""AINOS3-100 AC8 — assert each run's attack actually MOVED what it should.

⚠ The gap this closes. `AC2`'s manifest gate gives a run a clean bill on label,
schema, sidecar, subprocess exit and controlled fraction. None of those confirm
the telemetry a technique is *supposed* to move actually moved. The 2026-09-10
corpus was handed to `AINOS3-101` and trained on with that unverified, and the
worst case — an attack that never fired, producing nominal frames labelled as an
attack — is invisible from the run's own output. The 2026-09-10 pilot caught one
only by accident.

⚠ A generic novel-value check cannot substitute, which is why this reads a
per-technique table instead. Measured 2026-09-19: the three probe-only
techniques score 39/45/49 novel columns, squarely inside the range of real
attacks, because free-running fields generate novel values continuously.

The table (`components/onair/attack_footprints.json`) is anchored on what each
script COMMANDS, not on what the corpus shows — deriving the expectation from
the data it validates would be circular.

Usage:
    python3 check_footprints.py --results <corpus>/_all_results.json
    python3 check_footprints.py --results ... --json out.json
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
TABLE = os.path.join(ROOT, "components", "onair", "attack_footprints.json")
_TS = re.compile(r"csv_out_(\d{4}-\d{2}-\d{2}T[\d-]+)_pid(\d+)\.csv$")


def _pair(raw_name, blended_dir):
    m = _TS.search(os.path.basename(raw_name))
    if not m:
        return None
    key = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H-%M-%S-%f")
    best, bd = None, 9e9
    for c in glob.glob(os.path.join(blended_dir, f"csv_out_*_pid{m.group(2)}.csv")):
        mm = _TS.search(os.path.basename(c))
        d = abs((dt.datetime.strptime(mm.group(1), "%Y-%m-%dT%H-%M-%S-%f") - key).total_seconds())
        if d < bd:
            best, bd = c, d
    return best if bd <= 2.0 else None


def _nums(rows, field):
    out = []
    for r in rows:
        v = r.get(field)
        if v in (None, "", "[0]"):
            continue
        try:
            out.append(float(v))
        except ValueError:
            return None            # non-numeric column: fall back to `change`
    return out


def moved(rows_pre, rows_win, field, direction):
    """Did `field` move as `direction` says, during the window?"""
    pre, win = _nums(rows_pre, field), _nums(rows_win, field)
    if pre is None or win is None:            # non-numeric → value-set change
        a = {r.get(field) for r in rows_pre}
        b = {r.get(field) for r in rows_win}
        return bool(b - a)
    if not win:
        return False
    if direction == "increase":
        return max(win) > (max(pre) if pre else min(win) - 1)
    if direction == "reset":
        # ⚠ a reset goes DOWN. Compare the window's own trajectory, not just
        # against the baseline: the counter typically climbs THEN zeroes.
        return any(win[i] < win[i - 1] for i in range(1, len(win))) or \
               (bool(pre) and min(win) < min(pre))
    if direction == "change":
        return (set(win) - set(pre)) != set() or \
               any(win[i] != win[i - 1] for i in range(1, len(win)))
    raise SystemExit(f"unknown direction {direction!r}")


def check_run(rec, table, raw_dir, blended_dir, manifest_dir, pre_frames=600, post_frames=120):
    tech = rec["_technique"]
    spec = table["techniques"].get(tech)
    out = {"technique": tech, "mode": rec["_mode"], "ok": False, "why": ""}
    if not spec:
        out["why"] = "no footprint entry in the table"
        return out
    bl = _pair(rec["csv"], blended_dir)
    if not bl:
        out["why"] = "no blended pair"
        return out
    with open(bl) as fh:
        rows = list(csv.DictReader(fh))
    t = [dt.datetime.fromisoformat(r["OnAIR.FrameRecvUTC"]) for r in rows
         if r.get("OnAIR.FrameRecvUTC")]
    if len(t) != len(rows):
        out["why"] = "OnAIR.FrameRecvUTC incomplete"
        return out
    mf = json.load(open(os.path.join(manifest_dir, rec["manifest"])))
    atk = [a for a in mf.get("attacks", []) if "[prereq]" not in a["id"]]
    if not atk:
        out["why"] = "no non-prereq attack in manifest"
        return out
    a = atk[0]
    s = dt.datetime.fromisoformat(a["start_utc"]).replace(tzinfo=dt.timezone.utc)
    e = dt.datetime.fromisoformat(
        a.get("corruption_end_utc") or a["end_utc"]).replace(tzinfo=dt.timezone.utc)
    i0 = next((i for i, x in enumerate(t) if x >= s), None)
    if i0 is None:
        out["why"] = "attack window not in telemetry"
        return out
    i1 = max((i for i, x in enumerate(t) if x <= e), default=i0)
    pre = rows[max(0, i0 - pre_frames):i0]
    win = rows[i0:min(len(rows), i1 + post_frames)]
    hits = [f"{c['field']}:{c['direction']}" for c in spec["any_of"]
            if moved(pre, win, c["field"], c["direction"])]
    out["ok"] = bool(hits)
    out["hits"] = hits
    out["why"] = ("; ".join(hits) if hits else
                  "NONE of " + ", ".join(f"{c['field']}:{c['direction']}"
                                         for c in spec["any_of"]))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", required=True)
    p.add_argument("--table", default=TABLE)
    p.add_argument("--blended-dir", default=os.path.join(ROOT, "data", "onair", "csv_blended"))
    p.add_argument("--raw-dir", default=os.path.join(ROOT, "data", "onair", "csv"))
    p.add_argument("--manifest-dir", default=os.path.join(ROOT, "data", "onair", "scenarios"))
    p.add_argument("--json", default=None)
    a = p.parse_args()

    table = json.load(open(a.table))
    runs = json.load(open(a.results))
    missing = {r["_technique"] for r in runs} - set(table["techniques"])
    if missing:
        print(f"⚠ techniques with NO table entry: {sorted(missing)}")

    res, bad = [], []
    print(f"{'technique':<12}{'mode':<9}{'footprint':<8} evidence")
    for rec in runs:
        o = check_run(rec, table, a.raw_dir, a.blended_dir, a.manifest_dir)
        res.append(o)
        if not o["ok"]:
            bad.append(o)
        print(f"{o['technique']:<12}{o['mode']:<9}{'OK' if o['ok'] else '⚠ FAIL':<8} {o['why'][:70]}")
    print(f"\n{len(res) - len(bad)}/{len(res)} runs show their expected footprint")
    if bad:
        print("⚠ runs WITHOUT their footprint — these must not enter the corpus:")
        for o in bad:
            print(f"    {o['technique']}/{o['mode']}: {o['why']}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=2)
        print(f"wrote {a.json}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
