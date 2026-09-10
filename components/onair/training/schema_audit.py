#!/usr/bin/env python3
"""Inventory the RECORDED telemetry schema and find columns that never carry data.

WHY THIS EXISTS
---------------
`AINOS3-124` freezes the recorded schema before the `AINOS3-100` corpus rebuild,
on the same argument the label freeze used for classes: folding a column into a
collection that has not started is free, redoing one that has is not.

A freeze needs two things this script produces:

  1. **The recorded schema, stated exactly.** Not "the MIDs we subscribe" — the
     columns that actually land in the CSV, which is the subscribed set from
     `nos3_security_tlm.json` MINUS the `ExcludeColumns` prune in
     `nos3_security.ini`. Those two files are edited independently and neither
     one alone is the answer.
  2. **A fingerprint over that set**, so a corpus manifest can pin it. The CSV
     sidecar's `schema_sha256` is NOT that fingerprint — it hashes the tlm
     metadata FILE, so it moves on comment churn and, the defect that matters
     here, does NOT move when the prune moves. `recorded_schema_sha256` (added
     to the sidecar for this ticket) is the one to pin, and this script computes
     the same value from config so the two can be cross-checked.

SUBSCRIBED != RECORDED != WORKING
---------------------------------
`AINOS3-95` found columns that were subscribed and recorded and still carried no
information (CAM/SYN were dead; the derived CFE_TBL columns were constant 0). So
this script also audits a real CSV for the third property.

The operational definition of a silent column on this pipeline: the sbn_adapter
emits the literal string `[0]` for a field whose MID did not arrive in that
frame. A column that is `[0]` in EVERY frame of a session never received a
packet at all — that is a subscription that costs a column and a slot against
the 48-MID pipe cap and returns nothing.

⚠ A LOW sentinel fraction is normal and healthy, not a defect: any MID slower
than the ~5 Hz frame rate shows sentinel frames between arrivals, and OnAIR's
first frames are all sentinel while subscriptions settle. Only the 100 % case is
a finding.

⚠ Silent does NOT imply droppable. `AINOS3-108` traced four silent MIDs to four
different causes: device-disabled (`ST_DEV` — the star tracker boots disabled,
so this is a configuration question owned by `AINOS3-86`/`AINOS3-91`, NOT a dead
MID), command-produced with no scheduler entry (`CFE_SB_SUBS`, `SBN`), and
event-driven (`RADIO_DEV`). This script finds them; a human dispositions them.

USAGE
-----
    # what the config says the recorded schema is, + its fingerprint
    python3 training/schema_audit.py --from-config

    # what a session actually recorded, + which columns never carried data
    python3 training/schema_audit.py --csv data/onair/csv/csv_out_*.csv

    # both, cross-checked, written as the frozen manifest
    python3 training/schema_audit.py --csv <file> --emit-manifest schema_manifest.json

Exit 1 if `--require-no-new-silent` is given and a column outside the known
dispositioned set is silent (the `AINOS3-108 AC6` regression check).
"""
import argparse
import configparser
import csv
import hashlib
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ONAIR = os.path.join(HERE, "..")

SENTINEL = "[0]"

# Columns already dispositioned as silent by AINOS3-108, with their cause. A
# column here being silent is EXPECTED and does not fail --require-no-new-silent.
KNOWN_SILENT = {
    "CFE_SB_SUBS": "command-produced (CFE_SB_SEND_PREV_SUBS_CC), 0 scheduler entries",
    "SBN": "command-produced, 0 scheduler entries; one MID carries 5 payload variants",
    "RADIO_DEV": "event-driven from the radio proxy task; redundant with RADIO_HK",
    "ST_DEV": "star tracker boots DISABLED (ST.DeviceEnabled = 0) — configuration, "
              "not a dead MID; owned by AINOS3-86 / AINOS3-91",
}

# ── The schema-vNext deferred register (AINOS3-124 AC6) ──────────────────────
# Every column-changing item adjudicated defer-at-the-freeze, with the TRIGGER
# that should bring it back. Mirrors the deferred-class register (the `status`
# column of label_set.json): a deferred column is revisited, not forgotten.
# ⚠ A freeze is only honest if what it left out is written down. This list is
# that record — edit it here, not in a sprint plan.
SCHEMA_VNEXT = [
    {
        "item": "unsubscribe CFE_SB_SUBS 0x080D / SBN 0x08DC / RADIO_DEV 0x0931",
        "ticket": "AINOS3-108",
        "effect": "removes 9 columns from the SUBSCRIBED schema; reclaims 3 of 48 pipe slots",
        "why_deferred": "the deployed IF binds features by column NAME and holds all 9 in "
                        "its scalar_columns; unsubscribing crash-loops OnAIR on frame 1. "
                        "They are already PRUNED, so the corpus is clean either way.",
        "trigger": "the next IF retrain — fitted on the post-freeze corpus, it will not ask "
                   "for them",
    },
    {
        "item": "HS health-and-safety app columns",
        "ticket": "AINOS3-112",
        "effect": "adds columns",
        "why_deferred": "NO-GO at the freeze — HS would service a no-op watchdog stub, so "
                        "the observable value is uncertain (AINOS3-74: no WDT packet on this "
                        "platform)",
        "trigger": "a real watchdog observable existing, or HS being re-scoped to something "
                   "that moves in nominal flight",
    },
    {
        "item": "MM / MD memory apps",
        "ticket": "AINOS3-113",
        "effect": "adds columns",
        "why_deferred": "NO-GO at the freeze — MM adds a SUPPORTED attacker memory-write "
                        "path, so it is an attack-surface trade-off, not an automatic build",
        "trigger": "an explicit decision to accept that trade for the memory-tamper "
                   "techniques it would open",
    },
    {
        "item": "cFE diagnostic packets (4, routed but never scheduled)",
        "ticket": "AINOS3-120",
        "effect": "adds columns",
        "why_deferred": "needs FSW scheduler-table work plus index-walking logic; Low "
                        "priority and not deliverable inside the freeze window",
        "trigger": "AINOS3-120 being sprinted; headroom exists at 40/48",
    },
    {
        "item": "CAM_HK / imagery payload columns",
        "ticket": "AINOS3-102",
        "effect": "adds columns",
        "why_deferred": "the imagery payload is switched off in this NOS3 build — arducam "
                        "sits below the startup-script `!` terminator AND CAM_EXP has no "
                        "TransmitMsg, so subscribing it would record nothing (AINOS3-102 "
                        "AC4 decided: do not subscribe)",
        "trigger": "the CAM publish path being written — config alone is not enough",
    },
]


def recorded_schema_sha256(columns):
    """Same construction as csv_output_plugin._recorded_schema_sha256.

    Newline-joined so a column rename cannot collide with a reordering.
    """
    return hashlib.sha256("\n".join(columns).encode("utf-8")).hexdigest()


def schema_from_config(tlm_path, ini_path):
    """The recorded column set implied by the two config files, in CSV order."""
    with open(tlm_path) as f:
        order = json.load(f)["order"]
    cp = configparser.ConfigParser()
    cp.read(ini_path)
    raw = cp.get("CSV_OUTPUT", "ExcludeColumns", fallback="")
    excluded = {c.strip() for c in raw.split(",") if c.strip()}
    kept = [c for c in order if c not in excluded]
    return kept, sorted(excluded), order


def audit_csv(path, max_frames=None):
    """Read a recorded session: header, frame count, per-column sentinel counts."""
    with open(path, newline="") as f:
        rd = csv.reader(f)
        header = next(rd)
        n = len(header)
        sentinel = [0] * n
        frames = 0
        ragged = 0
        for row in rd:
            if len(row) != n:
                ragged += 1          # a torn final row while the file is live
                continue
            frames += 1
            for i, v in enumerate(row):
                if v == SENTINEL:
                    sentinel[i] += 1
            if max_frames and frames >= max_frames:
                break
    return header, frames, sentinel, ragged


def group_of(column):
    return column.split(".")[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="a recorded session CSV to audit")
    ap.add_argument("--tlm", default=os.path.join(ONAIR, "nos3_security_tlm.json"))
    ap.add_argument("--ini", default=os.path.join(ONAIR, "nos3_security.ini"))
    ap.add_argument("--from-config", action="store_true",
                    help="report the config-derived recorded schema")
    ap.add_argument("--max-frames", type=int, default=None,
                    help="stop after N frames (a full 670 MB session takes ~35 s)")
    ap.add_argument("--emit-manifest", help="write the frozen schema manifest here")
    ap.add_argument("--label", default=None, help="manifest version label, e.g. schema-v1")
    ap.add_argument("--require-no-new-silent", action="store_true",
                    help="exit 1 if a column outside KNOWN_SILENT is 100%% sentinel")
    args = ap.parse_args()

    if not args.csv and not args.from_config:
        ap.error("give --csv, --from-config, or both")

    cfg_cols = cfg_excluded = None
    if args.from_config or args.emit_manifest:
        cfg_cols, cfg_excluded, order = schema_from_config(args.tlm, args.ini)
        print(f"config-derived recorded schema: {len(cfg_cols)} columns "
              f"({len(order)} subscribed - {len(cfg_excluded)} pruned)")
        print(f"  recorded_schema_sha256 = {recorded_schema_sha256(cfg_cols)}")

    silent = []
    header = frames = None
    if args.csv:
        header, frames, sentinel, ragged = audit_csv(args.csv, args.max_frames)
        print(f"\nrecorded session: {os.path.basename(args.csv)}")
        print(f"  {len(header)} columns x {frames} frames"
              + (f"  ({ragged} ragged rows skipped)" if ragged else ""))
        print(f"  recorded_schema_sha256 = {recorded_schema_sha256(header)}")
        if frames == 0:
            print("  ⚠ no complete frames — is the file still being opened?")
            return 0

        silent = [header[i] for i in range(len(header)) if sentinel[i] == frames]
        by_group = OrderedDict()
        for c in silent:
            by_group.setdefault(group_of(c), []).append(c)

        print(f"\nsilent columns (100 % sentinel across all {frames} frames): {len(silent)}")
        for g, cols in by_group.items():
            why = KNOWN_SILENT.get(g, "⚠ UNDISPOSITIONED — no recorded cause")
            print(f"  {g:14s} {len(cols):2d} col(s)  — {why}")

        if cfg_cols is not None and header != cfg_cols:
            only_cfg = [c for c in cfg_cols if c not in set(header)]
            only_csv = [c for c in header if c not in set(cfg_cols)]
            print("\n⚠ config and CSV disagree on the recorded schema:")
            if only_cfg:
                print(f"   in config, not in CSV ({len(only_cfg)}): {only_cfg[:8]}")
            if only_csv:
                print(f"   in CSV, not in config ({len(only_csv)}): {only_csv[:8]}")
            print("   (a deployed copy under fsw/build/exe/cpu1/cf/onair/ may be stale)")

    if args.emit_manifest:
        cols = header if header else cfg_cols
        manifest = {
            "label": args.label or "unlabelled",
            "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "recorded_schema_sha256": recorded_schema_sha256(cols),
            "column_count": len(cols),
            "columns": cols,
            "pruned_columns": cfg_excluded,
            "source": {
                "tlm": os.path.relpath(args.tlm, ONAIR),
                "ini": os.path.relpath(args.ini, ONAIR),
                "verified_against_csv": os.path.basename(args.csv) if args.csv else None,
                "frames_verified": frames,
            },
            "silent_columns": silent,
            "silent_column_causes": {g: KNOWN_SILENT[g] for g in
                                     sorted({group_of(c) for c in silent} & set(KNOWN_SILENT))},
            "schema_vnext": SCHEMA_VNEXT,
        }
        with open(args.emit_manifest, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nwrote {args.emit_manifest}  "
              f"({manifest['column_count']} columns, sha {manifest['recorded_schema_sha256'][:12]}…)")
        print(f"  schema-vNext deferred register: {len(SCHEMA_VNEXT)} item(s)")
        for d in SCHEMA_VNEXT:
            print(f"    {d['ticket']:12s} {d['item'][:58]}")

    if args.require_no_new_silent:
        undispositioned = sorted({group_of(c) for c in silent} - set(KNOWN_SILENT))
        if undispositioned:
            print(f"\nFAIL — silent MID group(s) with no recorded cause: {undispositioned}",
                  file=sys.stderr)
            return 1
        print("\nPASS — no surviving subscription became silent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
