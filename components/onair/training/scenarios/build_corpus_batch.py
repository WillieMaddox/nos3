#!/usr/bin/env python3
"""Generate the AINOS3-100 corpus-rebuild batch from the FROZEN label set.

WHY THIS EXISTS
---------------
`AINOS3-100 AC6` requires the collection to consume
`data/onair/models/label_set.json` rather than an ad-hoc attack list. The
previous corpus was collected from a hand-maintained list, which is how classes
nobody intended to train on ended up in it. Generating the batch from the frozen
set makes that structurally impossible:

  * only `confirmed` + `deferred` techniques are emitted;
  * the 6 `dropped` classes (the 5 `IMP-*` and `EX-0012.04 [prereq]`) cannot be
    re-minted — they are filtered here and the filter is asserted;
  * `[prereq]` ids are never emitted as techniques. Chain prerequisites still
    RUN, they just do not get their own technique label (the `AINOS3-122 AC4`
    finding);
  * `nominal` is not an attack and is not emitted — it comes from the pre-attack
    windows of every run.

⚠ INERTIAL COSTS MORE THAN THE OTHER MODES (AINOS3-86)
------------------------------------------------------
An INERTIAL run cannot simply command the mode. The star tracker is
Earth-occluded for ~40 % of every orbit, `qValid` gates the control law, and a
hold entered while blinded diverges rather than captures. `single_mode_hold_INERTIAL`
now damps in SUNSAFE and commands the orbit-normal attitude, but it must then
WAIT for the exclusion window — up to ~35 min. Budget INERTIAL runs accordingly,
and verify each one with `inertial_capture.py` before its data counts.

USAGE
    python3 build_corpus_batch.py --modes SUNSAFE --instances 5 --out batch.json
    python3 build_corpus_batch.py --modes SUNSAFE INERTIAL --instances 5 --cost-only
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LABEL_SET = os.path.join(ROOT, "data", "onair", "models", "label_set.json")

# Measured stack-restart overhead between runs, from the gaps across the 40
# archived 2026-08-15 manifests (make stop + make launch-quiet + FSW/CSV wait).
# The in-run cost is NOT a constant — it is pre + attack + dwell + post — so it
# is computed per entry rather than hardcoded. Those manifests averaged 14.3 min
# end-to-end at pre=600/post=300; shorter windows are proportionally cheaper.
MIN_RESTART = 2.0
# AINOS3-86: mean additional wait for the star-tracker exclusion window, assuming
# a uniformly random orbit phase at mode entry (~40 % of a 92 min orbit blinded).
MIN_PER_RUN_INERTIAL_EXTRA = 17.0

DROPPED_GUARD = {"IMP-0001", "IMP-0002", "IMP-0003", "IMP-0005", "IMP-0006",
                 "EX-0012.04 [prereq]"}

_LEVEL_RE = re.compile(r"--attack-level.*?choices\s*=\s*(\[[^\]]*\]|range\([^)]*\))", re.S)


def valid_levels(script_path):
    """The --attack-level values a given attack script actually accepts.

    ⚠ Do NOT hardcode a level across the batch. The scripts do not share a
    level range — they variously accept [1], [1,2], [1,2,3] and [1,2,3,4] — and
    argparse REJECTS an out-of-range choice. Caught by the 2026-09-10 pilot:
    a hardcoded level 4 made `de_0003_01` exit with "invalid choice: 4" while
    the surrounding scenario blocks ran to completion, so the run produced a
    full-length CSV with **no attack in it**. At batch scale that silently
    yields nominal frames labelled as attacks — the single worst failure mode
    for a corpus, and invisible from the run's own output.
    """
    if not os.path.exists(script_path):
        return None
    with open(script_path, encoding="utf-8", errors="replace") as fh:
        m = _LEVEL_RE.search(fh.read())
    if not m:
        return None
    try:
        return sorted(eval(m.group(1)))          # noqa: S307 - our own source
    except Exception:
        return None


def load_catalog():
    spec = importlib.util.spec_from_file_location(
        "run_attack_mod", os.path.join(HERE, "run_attack.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_attack_mod"] = mod
    spec.loader.exec_module(mod)
    return mod.ATTACK_CATALOG


def selected_techniques(label_set_path):
    with open(label_set_path) as fh:
        ls = json.load(fh)
    out = []
    for c in ls["classes"]:
        if c["status"] not in ("confirmed", "deferred"):
            continue
        tid = c["id"]
        if tid == "nominal":
            continue                       # baseline, not an attack
        if "[prereq]" in tid:
            continue                       # AINOS3-122 AC4: never a technique label
        out.append(tid)
    # the guard, asserted rather than trusted
    leaked = DROPPED_GUARD & set(out)
    assert not leaked, f"dropped classes leaked into the batch: {sorted(leaked)}"
    return out, ls


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modes", nargs="+", default=["SUNSAFE"],
                    help="MODE or MODE:INSTANCES, e.g. 'SUNSAFE:5 INERTIAL:1'. "
                         "Per-mode counts matter because INERTIAL costs several "
                         "times more per run (AINOS3-86 exclusion-window wait), so "
                         "a corpus is usually deep in one mode and shallow in another.")
    ap.add_argument("--instances", type=int, default=5,
                    help="default instance count for modes given without ':N'. "
                         "AINOS3-99 recommends 5 (up from 3)")
    ap.add_argument("--pre-seconds", type=int, default=240,
                    help="nominal pre-attack window. Must clear the detector's "
                         "250-frame (~45 s) mode-switch warmup with margin; "
                         ">=180 recommended (AINOS3-77)")
    ap.add_argument("--post-seconds", type=int, default=300)
    ap.add_argument("--label-set", default=LABEL_SET)
    ap.add_argument("--level", type=int, default=None,
                    help="force a level for every run. Default: the MAXIMUM level "
                         "each script accepts, derived per script.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cost-only", action="store_true")
    args = ap.parse_args()

    techs, ls = selected_techniques(args.label_set)
    catalog = load_catalog()

    tech_to_key = {}
    for k, v in catalog.items():
        tech_to_key.setdefault(v.get("id"), []).append(k)
    missing = [t for t in techs if t not in tech_to_key]
    if missing:
        raise SystemExit(f"no attack script for: {missing}")

    VALID_MODES = {"SUNSAFE", "INERTIAL", "BDOT", "PASSIVE"}
    plan = []
    for spec in args.modes:
        mode, _, n = spec.partition(":")
        if mode not in VALID_MODES:
            raise SystemExit(f"unknown mode {mode!r}; valid={sorted(VALID_MODES)}")
        plan.append((mode, int(n) if n else args.instances))

    # Resolve the level per script, and refuse to emit a run that would be
    # rejected by its own argparse.
    levels, unknown = {}, []
    for t in techs:
        key = tech_to_key[t][0]
        path = catalog[key]["path"]
        if not os.path.isabs(path):
            for base in (ROOT, os.path.join(ROOT, "gsw", "attack_scripts", "sparta")):
                if os.path.exists(os.path.join(base, path)):
                    path = os.path.join(base, path)
                    break
        lv = valid_levels(path)
        if lv is None:
            unknown.append(key)
            levels[key] = args.level or 1
            continue
        if args.level is not None:
            if args.level not in lv:
                raise SystemExit(f"--level {args.level} is not accepted by {key} "
                                 f"(valid: {lv})")
            levels[key] = args.level
        else:
            levels[key] = max(lv)
    if unknown:
        print(f"⚠ could not read --attack-level choices for {unknown}; "
              f"defaulting to {args.level or 1}", file=sys.stderr)

    entries = []
    for mode, n_inst in plan:
        for rep in range(1, n_inst + 1):
            for t in techs:
                key = tech_to_key[t][0]
                entries.append({
                    "key": key,
                    "level": levels[key],
                    "chain": False,
                    "during": f"single_mode_hold_{mode}",
                    "pre_seconds": args.pre_seconds,
                    "post_seconds": args.post_seconds,
                    "_technique": t,          # the label_set.json id — the label
                    "_mode": mode,
                    "_rep": rep,
                })

    n_inert = sum(1 for e in entries if e["_mode"] == "INERTIAL")
    mins = 0.0
    for e in entries:
        c = catalog[e["key"]]
        attack_s = c.get("expected_runtime_s", 30) or 30
        dwell_s = c.get("corruption_dwell_s", 0) or 0
        mins += (e["pre_seconds"] + attack_s + dwell_s + e["post_seconds"]) / 60.0
        mins += MIN_RESTART
        if e["_mode"] == "INERTIAL":
            mins += MIN_PER_RUN_INERTIAL_EXTRA
    hours = mins / 60.0

    print(f"label set   : frozen {ls['frozen_at']} ({ls['source_ticket']}), "
          f"{ls['counts']['confirmed']} confirmed + {ls['counts']['deferred']} deferred, "
          f"{ls['counts']['dropped']} dropped and excluded")
    print(f"techniques  : {len(techs)}")
    print(f"modes       : {', '.join(f'{m} x{n}' for m, n in plan)}")
    print(f"runs        : {len(entries)}  ({n_inert} INERTIAL)")
    bylv = {}
    for e in entries:
        bylv.setdefault(e["level"], set()).add(e["key"])
    print(f"levels      : " + ", ".join(f"L{k}x{len(v)} scripts" for k, v in sorted(bylv.items()))
          + "  (max accepted per script)")
    print(f"windows     : pre {args.pre_seconds}s / post {args.post_seconds}s")
    print(f"EST WALLCLOCK: {hours:.1f} h   "
          f"(mean {mins/len(entries):.1f} min/run = pre+attack+dwell+post + "
          f"{MIN_RESTART:.0f} min restart"
          + (f"; +{MIN_PER_RUN_INERTIAL_EXTRA:.0f} min INERTIAL window wait"
             if n_inert else "") + ")")

    if args.cost_only:
        return 0
    if not args.out:
        raise SystemExit("give --out, or use --cost-only")
    with open(args.out, "w") as fh:
        json.dump(entries, fh, indent=1)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
